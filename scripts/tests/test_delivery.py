"""Delivery checks with fakes only; no Azure, Docker, Entra or Foundry calls."""
import importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


smoke = module('smoke_dev')
deploy = module('deploy_dev')


def valid_app():
    env = [{'name': name, 'value': 'managed_identity' if name == 'STORAGE_AUTH_MODE' else 'configured'} for name in smoke.REQUIRED]
    next(e for e in env if e['name'] == 'FRONTEND_ORIGIN')['value'] = 'https://frontend.test'
    env.append({'name': 'FOUNDRY_API_KEY', 'secretRef': 'foundry-api-key'})
    return {'properties': {'provisioningState': 'Succeeded', 'template': {'containers': [{'env': env}]},
                           'configuration': {'secrets': [{'name': 'foundry-api-key'}], 'ingress': {'allowInsecure': False}}}}


def test_native_secret_reference_and_public_config():
    smoke.check_config(valid_app(), 'https://frontend.test')


@pytest.mark.parametrize('failure', ['missing_env', 'plain_secret', 'missing_secret', 'wrong_origin', 'incomplete'])
def test_config_rejects_incomplete_or_unsafe_deployment(failure):
    app = valid_app()
    properties = app['properties']
    env = properties['template']['containers'][0]['env']
    if failure == 'missing_env':
        env[:] = [e for e in env if e['name'] != 'ENTRA_API_AUDIENCE']
    elif failure == 'plain_secret':
        env[-1]['value'] = 'fake-not-a-secret'
    elif failure == 'missing_secret':
        properties['configuration']['secrets'] = []
    elif failure == 'wrong_origin':
        next(e for e in env if e['name'] == 'FRONTEND_ORIGIN')['value'] = 'https://wrong.test'
    else:
        properties['provisioningState'] = 'Failed'
    with pytest.raises(AssertionError):
        smoke.check_config(app, 'https://frontend.test')


def fake_http(url, method='GET', headers=None, body=None):
    if method == 'OPTIONS':
        allowed = headers['Origin'] == 'https://frontend.test'
        return (200, {'Access-Control-Allow-Origin': headers['Origin']}, b'') if allowed else (400, {}, b'')
    if method == 'POST':
        assert not headers.get('Authorization')
        return 401, {'WWW-Authenticate': 'Bearer'}, b''
    if url.endswith('/health/version'):
        return 200, {}, b'{"status":"ok","commit":"abc","environment":"dev"}'
    if url.endswith('/health'):
        return 200, {}, b'{"status":"ok"}'
    if url.endswith('.js'):
        return 200, {'Content-Type': 'text/javascript'}, b'// app'
    return 200, {}, b'<div id="root"></div><script type="module" src="/assets/app.js"></script>'


def test_smoke_never_authenticates_or_calls_foundry(monkeypatch):
    calls = Mock(side_effect=fake_http)
    monkeypatch.setattr(smoke, 'request', calls)
    smoke.check_http('https://backend.test', 'https://frontend.test', 'abc')
    assert all(call.args[0].startswith(('https://backend.test', 'https://frontend.test')) for call in calls.call_args_list)


@pytest.mark.parametrize('failure', ['wrong_commit', 'cors_open', 'bundle_missing', 'no_auth'])
def test_smoke_detects_failed_release(monkeypatch, failure):
    def failed(url, method='GET', headers=None, body=None):
        result = fake_http(url, method, headers, body)
        if failure == 'cors_open' and method == 'OPTIONS':
            return 200, {'Access-Control-Allow-Origin': headers['Origin']}, b''
        if failure == 'bundle_missing' and url.endswith('.js'):
            return 404, {}, b''
        if failure == 'no_auth' and method == 'POST':
            return 200, {}, b''
        return result
    monkeypatch.setattr(smoke, 'request', failed)
    with pytest.raises(AssertionError):
        smoke.check_http('https://backend.test', 'https://frontend.test', 'wrong' if failure == 'wrong_commit' else 'abc')


def test_deployment_requires_explicit_execution_flag(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['deploy_dev.py'])
    command = Mock()
    monkeypatch.setattr(deploy, 'run', command)
    with pytest.raises(SystemExit):
        deploy.main()
    command.assert_not_called()


def test_private_command_errors_are_sanitized(monkeypatch):
    monkeypatch.setattr(deploy.subprocess, 'run', Mock(return_value=Mock(returncode=1, stderr='fake-private-value')))
    with pytest.raises(RuntimeError, match='Protected command failed') as error:
        deploy.run('az', 'deployment', private=True)
    assert 'fake-private-value' not in str(error.value)


@pytest.mark.parametrize('wrong_subscription', [False, True])
def test_delivery_uses_digest_and_temporary_secret_file_without_secret_arguments(monkeypatch, wrong_subscription):
    import json
    import os
    import urllib.error

    fake_key = 'fake-unit-test-key'
    monkeypatch.setattr(sys, 'argv', ['deploy_dev.py', '--execute'])
    for name, value in {'BUILD_SOURCEVERSION': 'a' * 40, 'BUILD_BUILDID': '123', 'FOUNDRY_API_KEY': fake_key,
                        'SWA_DEPLOYMENT_TOKEN': 'fake-swa-token', 'VITE_ENTRA_CLIENT_ID': 'public-client',
                        'VITE_ENTRA_AUTHORITY': 'https://authority.test', 'VITE_ENTRA_API_SCOPE': 'api://scope/chat',
                        'OPENTHREAD_AZURE_SUBSCRIPTION_ID': 'test-subscription',
                        'OPENTHREAD_DEV_RESOURCE_GROUP': 'test-resource-group',
                        'OPENTHREAD_CONTAINER_APP_NAME': 'test-container-app',
                        'OPENTHREAD_ACR_NAME': 'test-registry',
                        'OPENTHREAD_CONTAINER_APPS_ENVIRONMENT_NAME': 'test-environment',
                        'OPENTHREAD_STORAGE_ACCOUNT_NAME': 'teststorage',
                        'ENTRA_AUTHORITY': 'https://authority.test/v2.0',
                        'ENTRA_API_AUDIENCE': 'test-api-client',
                        'ENTRA_REQUIRED_SCOPE': 'chat',
                        'FOUNDRY_ENDPOINT': 'https://test-resource.openai.azure.com',
                        'FOUNDRY_DEPLOYMENT': 'test-chat',
                        'OPENTHREAD_FRONTEND_ORIGIN': 'https://frontend.test'}.items():
        monkeypatch.setenv(name, value)
    params = {name: {'value': 'public'} for name in ('staticWebAppName', 'containerAppsEnvironmentName', 'containerRegistryBaseName')}
    compiled = {'parametersJson': json.dumps({'parameters': params})}
    compile_command = Mock(return_value=Mock(stdout=json.dumps(compiled)))
    monkeypatch.setattr(deploy.subprocess, 'run', compile_command)
    digest = 'sha256:' + 'b' * 64
    secret_files = []
    calls = []

    def command(*args, private=False):
        calls.append(args)
        if '-g' in args:
            assert args[args.index('-g') + 1] == 'test-resource-group'
        assert fake_key not in ' '.join(args)
        if args[:3] == ('az', 'account', 'show'):
            return 'wrong-subscription' if wrong_subscription else 'test-subscription'
        if args[:3] == ('az', 'acr', 'show'):
            return json.dumps({'id': '/registry', 'loginServer': 'registry.azurecr.io'})
        if args[:3] == ('az', 'containerapp', 'show'):
            return 'backend.test' if '--query' in args else json.dumps({'identity': {'principalId': 'principal'}})
        if args[:4] == ('az', 'role', 'assignment', 'list'):
            return json.dumps([{'principalId': 'principal', 'roleDefinitionId': '/roles/7f951dda-4ed3-4680-a7ca-43fe172d538d'}])
        if args[:2] == ('docker', 'run'):
            return 'container-id'
        if args[:2] == ('docker', 'port'):
            return '127.0.0.1:12345'
        if args[:4] == ('az', 'acr', 'repository', 'show'):
            return digest
        if args[:4] == ('az', 'containerapp', 'env', 'show'):
            return '/environment'
        if args[:4] == ('az', 'deployment', 'group', 'create'):
            assert private
            path = Path(args[args.index('--parameters') + 1][1:])
            secret_files.append(path)
            assert os.stat(path).st_mode & 0o777 == 0o600
            deployed = json.loads(path.read_text())['parameters']
            assert deployed['storageAccountName']['value'] == 'teststorage'
            assert deployed['foundryApiKey']['value'] == fake_key
            assert deployed['backendImageReference']['value'] == 'registry.azurecr.io/openthread-backend@' + digest
            assert args[args.index('--template-file') + 1] == 'infra/backend.bicep'
        return ''

    monkeypatch.setattr(deploy, 'run', command)
    response = Mock(status=200)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)

    def urlopen(request, timeout):
        if isinstance(request, str):
            return response
        assert request.get_header('Authorization') is None
        raise urllib.error.HTTPError(request.full_url, 401, 'unauthenticated', {}, None)

    monkeypatch.setattr(deploy.urllib.request, 'urlopen', urlopen)
    if wrong_subscription:
        with pytest.raises(ValueError, match='wrong subscription'):
            deploy.main()
        assert calls == [('az', 'account', 'show', '--query', 'id', '-o', 'tsv')]
        return
    deploy.main()
    assert secret_files and all(not path.exists() for path in secret_files)
    assert compile_command.call_args.kwargs['env']['FOUNDRY_API_KEY_FOR_DEPLOYMENT'] == ''
    assert any(args[:2] == ('docker', 'rm') for args in calls)
    assert all('--build-arg' not in args for args in calls)


@pytest.mark.parametrize('value', ['', '<AZURE_SUBSCRIPTION_ID>', '$(UNSET_VARIABLE)', 'replace-with-subscription'])
def test_deployment_rejects_unconfigured_targets_before_commands(monkeypatch, value):
    monkeypatch.setattr(sys, 'argv', ['deploy_dev.py', '--execute'])
    monkeypatch.setenv('OPENTHREAD_AZURE_SUBSCRIPTION_ID', value)
    command = Mock()
    monkeypatch.setattr(deploy, 'run', command)
    with pytest.raises(ValueError, match='deployment setting'):
        deploy.main()
    command.assert_not_called()
