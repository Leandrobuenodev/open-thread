"""DEV delivery. Mutates Azure only with an explicit --execute flag."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

TARGET_SETTINGS = {
    'subscription': 'OPENTHREAD_AZURE_SUBSCRIPTION_ID',
    'resource_group': 'OPENTHREAD_DEV_RESOURCE_GROUP',
    'container_app': 'OPENTHREAD_CONTAINER_APP_NAME',
    'registry': 'OPENTHREAD_ACR_NAME',
    'environment': 'OPENTHREAD_CONTAINER_APPS_ENVIRONMENT_NAME',
    'storage': 'OPENTHREAD_STORAGE_ACCOUNT_NAME',
}


def required_setting(name):
    value = os.environ.get(name, '').strip()
    if not value or '$(' in value or '<' in value or 'replace-with' in value:
        raise ValueError(f'Missing or placeholder deployment setting: {name}')
    return value


def run(*args, private=False):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        # Never propagate deployment errors that could contain secure parameters.
        raise RuntimeError('Protected command failed; inspect Azure deployment status.' if private else result.stderr)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        parser.error('No action taken. Future deployment requires --execute.')
    target = {key: required_setting(name) for key, name in TARGET_SETTINGS.items()}
    for name in ('ENTRA_AUTHORITY', 'ENTRA_API_AUDIENCE', 'ENTRA_REQUIRED_SCOPE',
                 'FOUNDRY_ENDPOINT', 'FOUNDRY_DEPLOYMENT', 'OPENTHREAD_FRONTEND_ORIGIN'):
        required_setting(name)
    subscription = target['subscription']
    rg, app_name = target['resource_group'], target['container_app']
    acr, environment_name = target['registry'], target['environment']
    sha = os.environ['BUILD_SOURCEVERSION']
    build = os.environ['BUILD_BUILDID']
    if not re.fullmatch(r'[0-9a-f]{40}', sha) or not build.isdigit():
        raise ValueError('Invalid commit/build identifier')
    key = os.environ.get('FOUNDRY_API_KEY', '').strip()
    if not key or '$(' in key or not os.environ.get('SWA_DEPLOYMENT_TOKEN', '').strip() or '$(' in os.environ.get('SWA_DEPLOYMENT_TOKEN', ''):
        raise ValueError('Protected deployment variables are missing')
    for name in ('VITE_ENTRA_CLIENT_ID', 'VITE_ENTRA_AUTHORITY', 'VITE_ENTRA_API_SCOPE'):
        value = os.environ.get(name, '').strip()
        if not value or '$(' in value:
            raise ValueError(f'Missing public frontend setting: {name}')
    if run('az', 'account', 'show', '--query', 'id', '-o', 'tsv') != subscription:
        raise ValueError('Service connection targets the wrong subscription')
    # A separately authorized bootstrap must already have completed.
    registry = json.loads(run('az', 'acr', 'show', '-g', rg, '-n', acr, '-o', 'json'))
    app = json.loads(run('az', 'containerapp', 'show', '-g', rg, '-n', app_name, '-o', 'json'))
    principal = app.get('identity', {}).get('principalId')
    if not principal:
        raise ValueError('Bootstrap required: ACA system identity is absent')
    roles = json.loads(run('az', 'role', 'assignment', 'list', '--scope', registry['id'], '--fill-principal-name', 'false', '-o', 'json'))
    if not any(r['principalId'] == principal and r['roleDefinitionId'].endswith('7f951dda-4ed3-4680-a7ca-43fe172d538d') for r in roles):
        raise ValueError('Bootstrap required: AcrPull assignment is absent')
    server = registry['loginServer']
    tag = f'{server}/openthread-backend:{sha}-{build}'
    run('docker', 'build', '--platform', 'linux/amd64', '-t', tag, 'backend')
    container = run('docker', 'run', '-d', '-p', '127.0.0.1::8000', tag)
    try:
        mapping = run('docker', 'port', container, '8000/tcp')
        base = 'http://' + mapping
        for attempt in range(30):
            try:
                with urllib.request.urlopen(base + '/health', timeout=2) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(1)
        else:
            raise RuntimeError('Container health failed')
        request = urllib.request.Request(base + '/api/chat', data=b'{"message":"smoke"}', headers={'Content-Type': 'application/json'})
        try:
            urllib.request.urlopen(request, timeout=5)
            raise RuntimeError('Unauthenticated request was accepted')
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise RuntimeError('Unauthenticated request did not return 401') from None
    finally:
        run('docker', 'rm', '-f', container)
    run('az', 'acr', 'login', '-n', acr)
    run('docker', 'push', tag)
    digest = run('az', 'acr', 'repository', 'show', '-n', acr, '--image', f'openthread-backend:{sha}-{build}', '--query', 'digest', '-o', 'tsv')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('Invalid image digest')
    environment_id = run('az', 'containerapp', 'env', 'show', '-g', rg, '-n', environment_name, '--query', 'id', '-o', 'tsv')
    # Compilation must never inherit a developer's real bootstrap secret.
    compile_env = dict(os.environ, FOUNDRY_API_KEY_FOR_DEPLOYMENT='')
    compiled = subprocess.run(['az', 'bicep', 'build-params', '--file', 'infra/dev.bicepparam', '--stdout'], env=compile_env, capture_output=True, text=True, check=True)
    params = json.loads(compiled.stdout)['parametersJson']
    if isinstance(params, str):
        params = json.loads(params)
    params = params['parameters']
    for name in ('staticWebAppName', 'containerAppsEnvironmentName', 'containerRegistryBaseName'):
        params.pop(name)
    values = {'containerAppName': app_name, 'containerAppsEnvironmentId': environment_id, 'registryLoginServer': server,
              'deployBackend': True, 'backendImageReference': f'{server}/openthread-backend@{digest}',
              'storageAccountName': target['storage'],
              'foundryApiKey': key, 'appGitSha': sha, 'appBuildId': build, 'appReleaseId': build, 'appImageDigest': digest}
    params.update({name: {'value': value} for name, value in values.items()})
    with tempfile.TemporaryDirectory(prefix='openthread-secure-') as directory:
        path = Path(directory) / 'parameters.json'
        path.touch(mode=0o600)
        path.write_text(json.dumps({'$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#', 'contentVersion': '1.0.0.0', 'parameters': params}))
        run('az', 'deployment', 'group', 'create', '-g', rg, '-n', f'openthread-backend-{build}', '--template-file', 'infra/backend.bicep', '--parameters', '@' + str(path), '--mode', 'Incremental', '--only-show-errors', '-o', 'none', private=True)
    hostname = run('az', 'containerapp', 'show', '-g', rg, '-n', app_name, '--query', 'properties.configuration.ingress.fqdn', '-o', 'tsv')
    print(f'##vso[task.setvariable variable=backendUrl]https://{hostname}')


if __name__ == '__main__':
    main()
