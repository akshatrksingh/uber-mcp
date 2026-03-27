"""Holds the active provider instance, shared across tool modules."""
import logging

logger = logging.getLogger(__name__)

_provider = None


def get_provider():
    """Return the configured provider (mock or real).

    Returns:
        The active provider instance.

    Raises:
        RuntimeError: If configure() has not been called yet.
    """
    if _provider is None:
        raise RuntimeError('Provider not initialised — call configure() first')
    return _provider


def configure(provider) -> None:
    """Set the active provider.

    Args:
        provider: A MockProvider or real UberClient instance.
    """
    global _provider
    _provider = provider
    logger.info('Provider configured: %s', type(provider).__name__)
