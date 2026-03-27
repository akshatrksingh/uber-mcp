import logging

from src.provider import get_provider
from src.state_manager import state

logger = logging.getLogger(__name__)


async def uber_get_ride_status(ride_id: str | None = None) -> dict:
    """Check the status of a ride.

    If no ride_id given, checks the most recent active ride.

    Args:
        ride_id: The ride ID to check. Omit to check the current active ride.

    Returns:
        {"status": str, "driver": {...}, "vehicle": {...}, "eta_minutes": int | None}
        Statuses: processing, accepted, arriving, in_progress, completed, cancelled.
    """
    target_id = ride_id or state.active_ride
    if not target_id:
        return {
            'error': 'RIDE_NOT_FOUND',
            'message': 'No ride_id provided and no active ride in session.',
            'recoverable': False,
            'suggestion': 'Book a ride first with uber_request_ride.',
        }
    logger.info('Getting ride status: %s', target_id)
    return await get_provider().get_ride_status(target_id)
