import logging

from src.provider import get_provider
from src.state_manager import state

logger = logging.getLogger(__name__)


async def uber_request_ride(
    product_id: str,
    pickup_latitude: float,
    pickup_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    confirm: bool = False,
) -> dict:
    """Preview a ride (confirm=false) or book it (confirm=true).

    Always preview first — booking without preview is blocked server-side.
    Call uber_get_ride_options first to get a valid product_id.

    Args:
        product_id: Product ID from uber_get_ride_options.
        pickup_latitude: Latitude of the pickup location.
        pickup_longitude: Longitude of the pickup location.
        destination_latitude: Latitude of the destination.
        destination_longitude: Longitude of the destination.
        confirm: False = preview only. True = actually book the ride.

    Returns:
        confirm=false: {"status": "preview", "fare": {...}, "eta_minutes", "product_name"}
        confirm=true:  {"status": "confirmed", "ride_id", "driver": {...},
                        "vehicle": {...}, "eta_minutes"}
    """
    if not product_id or not product_id.strip():
        return {
            'error': 'INVALID_INPUT',
            'message': 'product_id cannot be empty.',
            'recoverable': True,
            'suggestion': 'Call uber_get_ride_options first to get a valid product_id.',
        }

    if confirm and state.last_preview is None:
        return {
            'error': 'NO_PREVIEW',
            'message': 'No preview found. Call with confirm=false first.',
            'recoverable': True,
            'suggestion': 'Call uber_request_ride with confirm=false to preview the ride first.',
        }

    if confirm and state.active_ride is not None:
        return {
            'error': 'RIDE_CONFLICT',
            'message': f'A ride is already in progress (ride_id: {state.active_ride}).',
            'recoverable': False,
            'suggestion': 'Check ride status with uber_get_ride_status or cancel with uber_cancel_ride.',
        }

    provider = get_provider()

    if not confirm:
        result = await provider.request_estimate(
            product_id, pickup_latitude, pickup_longitude,
            destination_latitude, destination_longitude,
        )
        state.last_preview = result
        logger.info('Preview stored for product_id=%s', product_id)
        return result

    fare_id = state.last_preview.get('fare_id') if state.last_preview else None
    result = await provider.request_ride(
        product_id, pickup_latitude, pickup_longitude,
        destination_latitude, destination_longitude,
        fare_id=fare_id,
    )
    state.active_ride = result['ride_id']
    state.save_ride(result)
    logger.info('Ride booked: %s', result['ride_id'])
    return result
