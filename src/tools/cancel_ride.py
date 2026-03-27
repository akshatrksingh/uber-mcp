import logging

from src.provider import get_provider
from src.state_manager import state

logger = logging.getLogger(__name__)


async def uber_cancel_ride(ride_id: str) -> dict:
    """Cancel an active ride. May incur a cancellation fee.

    Args:
        ride_id: The ride ID to cancel (from uber_request_ride confirmed response).

    Returns:
        {"status": "cancelled", "cancellation_fee": {"amount": float, "currency": str} | None}
    """
    if not ride_id or not ride_id.strip():
        return {
            'error': 'INVALID_INPUT',
            'message': 'ride_id cannot be empty.',
            'recoverable': True,
            'suggestion': 'Provide the ride_id from the confirmed booking.',
        }

    if state.active_ride is None:
        return {
            'error': 'RIDE_NOT_FOUND',
            'message': 'No active ride found in this session.',
            'recoverable': False,
            'suggestion': 'There is no ride to cancel.',
        }

    if state.active_ride != ride_id:
        return {
            'error': 'RIDE_NOT_FOUND',
            'message': f'ride_id {ride_id!r} does not match the active ride {state.active_ride!r}.',
            'recoverable': False,
            'suggestion': 'Use the ride_id returned from uber_request_ride.',
        }

    result = await get_provider().cancel_ride(ride_id)
    state.active_ride = None
    logger.info('Ride cancelled: %s', ride_id)
    return result
