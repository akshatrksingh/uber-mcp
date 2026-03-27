import logging

from src.provider import get_provider

logger = logging.getLogger(__name__)


async def uber_authenticate(auth_code: str | None = None) -> dict:
    """Authenticate with Uber or exchange an auth code for a token.

    Use when other tools return AUTH_EXPIRED error. Provides a URL for the
    user to re-authorize. If called with auth_code, exchanges the code for
    an access token.

    Args:
        auth_code: OAuth authorization code from the redirect URL, if available.

    Returns:
        {"status": "authenticated", "user": {"name": str, "email": str}}
        OR {"status": "auth_required", "auth_url": str}
    """
    provider = get_provider()

    if not provider.is_authenticated() and auth_code is None:
        logger.info('Auth required — returning auth URL')
        return {
            'status': 'auth_required',
            'auth_url': provider.get_auth_url(),
        }

    logger.info('Auth check passed')
    return {'status': 'authenticated', 'user': provider.get_user_info()}
