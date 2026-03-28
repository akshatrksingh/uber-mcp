from src.provider import get_provider


async def uber_ride_history() -> dict:
    """Return the history of all rides booked in this session.

    Shows confirmed, completed, and cancelled rides with fare, pickup,
    destination, and booking timestamp.

    Returns:
        {"rides": [{"ride_id", "product_name", "pickup", "destination",
                    "fare", "booked_at", "status"}, ...]}
    """
    rides = get_provider().get_ride_history()
    return {'rides': rides}
