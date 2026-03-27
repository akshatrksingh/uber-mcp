import logging
import os
import sys

import click
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src.mock_provider import MockProvider
from src.state_manager import state

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

mcp = FastMCP('uber-mcp')
_provider: MockProvider | None = None


def get_provider() -> MockProvider:
    """Return the active provider (mock or real).

    Returns:
        The configured provider instance.
    """
    if _provider is None:
        raise RuntimeError('Provider not initialised — call configure_provider() first')
    return _provider


def configure_provider(mock: bool) -> None:
    """Set the provider based on the --mock flag.

    Args:
        mock: If True, use MockProvider. Real provider added in Phase 4.
    """
    global _provider
    if mock:
        _provider = MockProvider()
        logger.info('Using mock provider')
    else:
        # Phase 4: wire real UberClient here
        _provider = MockProvider()
        logger.warning('Real provider not yet implemented — falling back to mock')


# ---------------------------------------------------------------------------
# Tool: uber_authenticate
# ---------------------------------------------------------------------------

@mcp.tool()
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
        return {
            'status': 'auth_required',
            'auth_url': provider.get_auth_url(),
        }
    user = provider.get_user_info()
    return {'status': 'authenticated', 'user': user}


# ---------------------------------------------------------------------------
# Tool: uber_geocode
# ---------------------------------------------------------------------------

@mcp.tool()
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
    provider = get_provider()
    return await provider.geocode(address)


# ---------------------------------------------------------------------------
# Tool: uber_get_ride_options
# ---------------------------------------------------------------------------

@mcp.tool()
async def uber_get_ride_options(
    pickup_latitude: float,
    pickup_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> dict:
    """Get available ride types with prices for a route.

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
    provider = get_provider()
    result = await provider.get_ride_options(
        pickup_latitude, pickup_longitude, destination_latitude, destination_longitude
    )
    state.last_options = result.get('options')
    return result


# ---------------------------------------------------------------------------
# Tool: uber_request_ride
# ---------------------------------------------------------------------------

@mcp.tool()
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
            destination_latitude, destination_longitude
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


# ---------------------------------------------------------------------------
# Tool: uber_get_ride_status
# ---------------------------------------------------------------------------

@mcp.tool()
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
    provider = get_provider()
    return await provider.get_ride_status(target_id)


# ---------------------------------------------------------------------------
# Tool: uber_cancel_ride
# ---------------------------------------------------------------------------

@mcp.tool()
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
            'message': f'ride_id {ride_id} does not match the active ride {state.active_ride}.',
            'recoverable': False,
            'suggestion': 'Use the ride_id returned from uber_request_ride.',
        }
    provider = get_provider()
    result = await provider.cancel_ride(ride_id)
    state.active_ride = None
    logger.info('Ride cancelled: %s', ride_id)
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option('--mock', is_flag=True, default=False, help='Use mock provider instead of real Uber API.')
def main(mock: bool) -> None:
    """Start the Uber MCP server over stdio."""
    configure_provider(mock=mock)
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
