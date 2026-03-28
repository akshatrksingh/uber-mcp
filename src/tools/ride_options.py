import logging

from src.provider import get_provider
from src.state_manager import state

logger = logging.getLogger(__name__)


async def uber_get_ride_options(
    pickup_latitude: float,
    pickup_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> dict:
    """Get available ride types with prices for a route.

    Always return ALL available ride options to the user, regardless of what
    ride type they asked for. Let the user see all options and prices before choosing.

    Call uber_geocode first for both pickup and destination to get coordinates.
    Returns all available products with price ranges and ETAs.

    Args:
        pickup_latitude: Latitude of the pickup location (-90 to 90).
        pickup_longitude: Longitude of the pickup location (-180 to 180).
        destination_latitude: Latitude of the destination (-90 to 90).
        destination_longitude: Longitude of the destination (-180 to 180).

    Returns:
        {"options": [{"product_id", "name", "estimate_low", "estimate_high",
                      "currency", "eta_minutes", "capacity"}, ...]}
    """
    if not (-90 <= pickup_latitude <= 90):
        return {
            'error': 'INVALID_INPUT',
            'message': f'pickup_latitude {pickup_latitude} must be between -90 and 90.',
            'recoverable': True,
            'suggestion': 'Re-geocode the pickup location.',
        }
    if not (-180 <= pickup_longitude <= 180):
        return {
            'error': 'INVALID_INPUT',
            'message': f'pickup_longitude {pickup_longitude} must be between -180 and 180.',
            'recoverable': True,
            'suggestion': 'Re-geocode the pickup location.',
        }
    if not (-90 <= destination_latitude <= 90):
        return {
            'error': 'INVALID_INPUT',
            'message': f'destination_latitude {destination_latitude} must be between -90 and 90.',
            'recoverable': True,
            'suggestion': 'Re-geocode the destination.',
        }
    if not (-180 <= destination_longitude <= 180):
        return {
            'error': 'INVALID_INPUT',
            'message': f'destination_longitude {destination_longitude} must be between -180 and 180.',
            'recoverable': True,
            'suggestion': 'Re-geocode the destination.',
        }

    result = await get_provider().get_ride_options(
        pickup_latitude, pickup_longitude, destination_latitude, destination_longitude
    )
    state.last_options = result.get('options')
    return result
