import logging

from src import geocoding_client

logger = logging.getLogger(__name__)


async def uber_geocode(address: str) -> dict:
    """Convert a location name or address to coordinates.

    Use this tool to convert human-readable locations like 'NYU' or
    '350 5th Ave, New York' into latitude/longitude coordinates.
    Call this BEFORE uber_get_ride_options — that tool requires coordinates.

    Args:
        address: Location name or street address to geocode.

    Returns:
        Single result: {latitude, longitude, display_name}
        Ambiguous: {results: [...], ambiguous: true} — ask user to clarify.
    """
    if not address or not address.strip():
        return {
            'error': 'INVALID_INPUT',
            'message': 'Address cannot be empty.',
            'recoverable': True,
            'suggestion': 'Ask the user for a location name or street address.',
        }
    return await geocoding_client.geocode(address)
