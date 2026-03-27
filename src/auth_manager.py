"""Auth manager — reads/writes token.json, checks expiry.

Phase 4 will add token refresh and OAuth exchange.
The public interface stays the same.
"""
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

TOKEN_FILE = Path('token.json')


class AuthManager:
    """Manages Uber OAuth tokens stored in token.json."""

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
            expires_in = data.get('expires_in', 3600)
            issued_at = data.get('issued_at', time.time())
            self._expires_at = issued_at + expires_in
            logger.info('Loaded token from token.json (expires_at=%s)', self._expires_at)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error('Failed to parse token.json: %s', exc)

    def is_authenticated(self) -> bool:
        """Return True if a non-expired access token is loaded.

        Returns:
            True if authenticated and token has not expired.
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
        """Return placeholder user info.

        Real profile fetch added in Phase 4.

        Returns:
            User dict with name and email.
        """
        return {'name': 'Authenticated User', 'email': 'user@example.com'}
