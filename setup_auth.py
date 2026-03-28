"""One-time Uber OAuth flow. Saves access + refresh tokens to token.json."""
import json
import os
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import httpx
from dotenv import load_dotenv

load_dotenv()

_TOKEN_URL = 'https://login.uber.com/oauth/v2/token'


def _require(name: str) -> str:
    val = os.environ.get(name, '').strip()
    if not val:
        print(f'Error: {name} is not set. Copy .env.example to .env and fill it in.')
        sys.exit(1)
    return val


class _AuthServer(HTTPServer):
    """HTTPServer subclass that stores the captured OAuth code."""
    auth_code: str | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        params = parse_qs(urlparse(self.path).query)
        code = params.get('code', [None])[0]
        self.server.auth_code = code  # type: ignore[attr-defined]
        self.send_response(200)
        self.end_headers()
        if code:
            self.wfile.write(b'<html><body><h2>Authorization successful!</h2>'
                             b'<p>You can close this tab and return to the terminal.</p>'
                             b'</body></html>')
        else:
            self.wfile.write(b'<html><body><h2>Error: no code in callback.</h2></body></html>')

    def log_message(self, *args) -> None:  # suppress access logs
        pass


def main() -> None:
    client_id = _require('UBER_CLIENT_ID')
    client_secret = _require('UBER_CLIENT_SECRET')
    redirect_uri = os.environ.get('UBER_REDIRECT_URI', 'http://localhost:3000/callback')

    port = int(urlparse(redirect_uri).port or 3000)

    auth_url = (
        f'https://login.uber.com/oauth/v2/authorize'
        f'?client_id={client_id}'
        f'&response_type=code'
        f'&scope=profile+request'
        f'&redirect_uri={redirect_uri}'
    )

    print('Opening browser for Uber authorization...')
    print(f'If the browser does not open automatically, visit:\n\n  {auth_url}\n')
    webbrowser.open(auth_url)

    server = _AuthServer(('localhost', port), _CallbackHandler)
    print(f'Waiting for OAuth callback on port {port}...')
    server.handle_request()

    if not server.auth_code:
        print('Error: callback received but no authorization code found.')
        sys.exit(1)

    print('Code received — exchanging for tokens...')
    resp = httpx.post(
        _TOKEN_URL,
        data={
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'authorization_code',
            'code': server.auth_code,
            'redirect_uri': redirect_uri,
        },
        timeout=15,
    )

    if resp.status_code != 200:
        print(f'Token exchange failed: HTTP {resp.status_code}\n{resp.text}')
        sys.exit(1)

    token_data = resp.json()
    token_data['issued_at'] = time.time()

    with open('token.json', 'w') as f:
        json.dump(token_data, f, indent=2)

    print('\nSuccess! Tokens saved to token.json')
    print(f'  Scope    : {token_data.get("scope", "unknown")}')
    print(f'  Expires  : {token_data.get("expires_in", 3600)} seconds')
    print(f'\nRun the agent with: uv run python agent/cli_agent.py')


if __name__ == '__main__':
    main()
