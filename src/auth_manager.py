"""Manages Uber OAuth tokens: loads token.json, checks expiry, refreshes."""
import json
import logging
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TOKEN_FILE = Path('token.json')
TOKEN_URL = 'https://login.uber.com/oauth/v2/token'


class AuthManager:
    """Reads token.json on startup, refreshes access tokens transparently."""

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0
        self._load_token()

    def _load_token(self) -> None:
        """Read token.json into private fields if it exists."""
        if not TOKEN_FILE.exists():
            logger.info('No token.json found — not authenticated')
            return
        try:
            data = json.loads(TOKEN_FILE.read_text())
            self._access_token = data.get('access_token')
            self._refresh_token = data.get('refresh_token')
            issued_at = data.get('issued_at', time.time())
            self._expires_at = issued_at + data.get('expires_in', 3600)
            logger.info('Loaded token from token.json (expires_at=%.0f)', self._expires_at)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error('Failed to parse token.json: %s', exc)

    def _save_token(self, data: dict) -> None:
        """Persist token data to token.json with current issued_at timestamp.

        Args:
            data: Token response dict from Uber OAuth endpoint.
        """
        data['issued_at'] = time.time()
        TOKEN_FILE.write_text(json.dumps(data, indent=2))
        logger.info('Token saved to token.json')

    def is_authenticated(self) -> bool:
        """Return True if a non-expired access token is available.

        Returns:
            True if token exists and has not expired.
        """
        return bool(self._access_token) and time.time() < self._expires_at

    def get_token(self) -> str:
        """Return the current access token.

        Returns:
            The access token string.

        Raises:
            RuntimeError: If not authenticated.
        """
        if not self.is_authenticated():
            raise RuntimeError('Not authenticated')
        return self._access_token  # type: ignore[return-value]

    async def ensure_token(self) -> None:
        """Ensure a valid token is available, refreshing if needed.

        Raises:
            RuntimeError: If no valid token and refresh fails or is unavailable.
        """
        if self.is_authenticated():
            return
        if self._refresh_token:
            logger.info('Access token expired — refreshing')
            await self.refresh_token()
        if not self.is_authenticated():
            raise RuntimeError('Not authenticated — run setup_auth.py first')

    async def refresh_token(self) -> None:
        """Exchange the refresh token for a new access token.

        Raises:
            RuntimeError: If the refresh request fails.
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    'client_id': os.environ.get('UBER_CLIENT_ID', ''),
                    'client_secret': os.environ.get('UBER_CLIENT_SECRET', ''),
                    'grant_type': 'refresh_token',
                    'refresh_token': self._refresh_token,
                },
            )
        if resp.status_code != 200:
            raise RuntimeError(f'Token refresh failed: {resp.status_code} {resp.text}')
        data = resp.json()
        self._access_token = data['access_token']
        self._refresh_token = data.get('refresh_token', self._refresh_token)
        self._expires_at = time.time() + data.get('expires_in', 3600)
        self._save_token(data)

    def get_auth_url(self) -> str:
        """Build the Uber OAuth authorization URL.

        Returns:
            The authorization URL string.
        """
        client_id = os.environ.get('UBER_CLIENT_ID', 'YOUR_CLIENT_ID')
        redirect_uri = os.environ.get('UBER_REDIRECT_URI', 'http://localhost:3000/callback')
        return (
            f'https://login.uber.com/oauth/v2/authorize'
            f'?client_id={client_id}'
            f'&response_type=code'
            f'&scope=profile+request'
            f'&redirect_uri={redirect_uri}'
        )

    def get_user_info(self) -> dict:
        """Return basic user info.

        Returns:
            User dict. Profile API endpoint not in spec; returns placeholder.
        """
        return {'name': 'Authenticated User', 'email': 'user@example.com'}
