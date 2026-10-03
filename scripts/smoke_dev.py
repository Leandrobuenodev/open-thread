"""Read-only post-deployment checks; never sends an authenticated chat request."""
import argparse
import json
import subprocess
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

REQUIRED = {'ENTRA_AUTHORITY', 'ENTRA_API_AUDIENCE', 'ENTRA_REQUIRED_SCOPE', 'FOUNDRY_ENDPOINT',
            'FOUNDRY_DEPLOYMENT', 'STORAGE_AUTH_MODE', 'STORAGE_ACCOUNT_NAME', 'STORAGE_TABLE_ENDPOINT',
            'STORAGE_BLOB_ENDPOINT', 'STORAGE_TABLE_NAME', 'STORAGE_BLOB_CONTAINER', 'FRONTEND_ORIGIN', 'CHAT_RATE_LIMIT_REQUESTS', 'CHAT_RATE_LIMIT_WINDOW_SECONDS',
            'CHAT_MAX_CONCURRENCY', 'CHAT_MAX_BODY_BYTES', 'CHAT_MAX_MESSAGE_BYTES', 'FOUNDRY_MAX_OUTPUT_TOKENS'}


def request(url, method='GET', headers=None, body=None):
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        response = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read()


def check_config(app, origin):
    properties = app['properties']
    assert properties['provisioningState'] == 'Succeeded', 'ACA provisioning incomplete'
    env = {e['name']: e for e in properties['template']['containers'][0]['env']}
    assert all(env.get(name, {}).get('value') for name in REQUIRED), 'Required public env missing'
    assert env['STORAGE_AUTH_MODE']['value'] == 'managed_identity', 'Cloud storage auth must use Managed Identity'
    assert not ({'DATABASE_URL', 'AZURITE_CONNECTION_STRING', 'AZURE_STORAGE_CONNECTION_STRING', 'AZURE_STORAGE_KEY'} & env.keys()), 'Legacy/local/key storage configuration present'
    assert env['FRONTEND_ORIGIN']['value'] == origin, 'Origin mismatch'
    assert env.get('FOUNDRY_API_KEY', {}).get('secretRef') == 'foundry-api-key', 'Secret reference missing'
    assert 'value' not in env['FOUNDRY_API_KEY'], 'Key configured as plain env'
    assert any(s['name'] == 'foundry-api-key' for s in properties['configuration']['secrets']), 'Secret entry missing'
    assert properties['configuration']['ingress']['allowInsecure'] is False


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.root = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.root |= values.get('id') == 'root'
        if tag == 'script' and values.get('type') == 'module' and values.get('src'):
            self.scripts.append(values['src'])


def check_http(backend, frontend, commit):
    status, _, data = request(backend + '/health')
    assert status == 200 and json.loads(data)['status'] == 'ok', 'Health failed'
    status, _, data = request(backend + '/health/version')
    version = json.loads(data)
    assert status == 200 and version['status'] == 'ok' and version['commit'] == commit and version['environment'] == 'dev', 'Serving version mismatch'
    status, headers, _ = request(backend + '/api/chat', 'POST', {'Content-Type': 'application/json'}, b'{"message":"smoke"}')
    assert status == 401 and headers.get('WWW-Authenticate', '').lower().startswith('bearer'), 'Auth smoke failed'
    for origin, allowed in ((frontend, True), ('https://untrusted.invalid', False)):
        status, headers, _ = request(backend + '/api/chat', 'OPTIONS', {'Origin': origin, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization,content-type'})
        assert (headers.get('Access-Control-Allow-Origin') == origin) == allowed, 'CORS origin failed'
        assert status == (200 if allowed else 400), 'CORS preflight status failed'
        assert headers.get('Access-Control-Allow-Credentials') is None, 'Unexpected credentials'
    status, _, html = request(frontend)
    assert status == 200, 'Frontend unavailable'
    assets = Assets()
    assets.feed(html.decode())
    assert assets.root and assets.scripts, 'Application entry missing'
    for src in assets.scripts:
        status, headers, _ = request(urljoin(frontend + '/', src))
        assert status == 200 and 'javascript' in headers.get('Content-Type', ''), 'Application bundle unavailable'
    assert request(frontend + '/redirect.html')[0] == 200, 'Redirect bridge unavailable'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', required=True)
    parser.add_argument('--frontend', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--resource-group', required=True)
    parser.add_argument('--container-app', required=True)
    args = parser.parse_args()
    # Select only env metadata and secret NAMES; never list secret values.
    query = '{properties:{provisioningState:properties.provisioningState,template:properties.template,configuration:{ingress:properties.configuration.ingress,secrets:properties.configuration.secrets[].{name:name}}}}'
    result = subprocess.run(['az', 'containerapp', 'show', '-g', args.resource_group, '-n', args.container_app, '--query', query, '-o', 'json'], capture_output=True, text=True, check=True)
    check_config(json.loads(result.stdout), args.frontend.rstrip('/'))
    check_http(args.backend.rstrip('/'), args.frontend.rstrip('/'), args.commit)
    print('DEV health, version, authentication, CORS, frontend assets and secret reference checks passed.')


if __name__ == '__main__':
    main()
