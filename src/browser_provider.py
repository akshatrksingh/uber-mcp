"""Browser-based Uber provider — drives uber.com via Playwright.

Implements the same interface as MockProvider; MCP tools are unchanged.
All DOM interaction is delegated to browser_actions.py.
"""
import asyncio
import logging
import re
import time

from src import browser_actions as _ba
from src import geocoding_client
from src.browser_session import BrowserSession

logger = logging.getLogger(__name__)


class BrowserProvider:
    """Implements the MockProvider interface by automating uber.com."""

    def __init__(self) -> None:
        self._session = BrowserSession()
        self._addr_cache: dict[str, str] = {}   # "lat,lng" → original address string
        self._selected_product: str | None = None
        self._active_ride_id: str | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _key(self, lat: float, lng: float) -> str:
        return f'{lat:.4f},{lng:.4f}'

    def _addr(self, lat: float, lng: float) -> str:
        return self._addr_cache.get(self._key(lat, lng), '')

    async def _ensure_ready(self) -> dict | None:
        """Start the browser and verify Uber login.

        Returns:
            None on success, or a structured LOGIN_REQUIRED error dict.
        """
        await self._session.start()
        if not await self._session.ensure_logged_in():
            return {
                'error': 'LOGIN_REQUIRED',
                'message': (
                    'Not logged in to Uber. A browser window has opened. '
                    'Log in to uber.com, then call uber_authenticate to continue.'
                ),
                'recoverable': True,
                'suggestion': 'Log in via the open browser window, then call uber_authenticate.',
            }
        return None

    # ------------------------------------------------------------------
    # Provider interface
    # ------------------------------------------------------------------

    async def geocode(self, address: str) -> dict:
        """Resolve coordinates via geocoding_client and cache the address string.

        Args:
            address: Location name or street address.

        Returns:
            {latitude, longitude, display_name}, ambiguous dict, or error dict.
        """
        result = await geocoding_client.geocode(address)
        if 'latitude' in result:
            self._addr_cache[self._key(result['latitude'], result['longitude'])] = address
        elif 'results' in result:
            for r in result['results']:
                self._addr_cache[self._key(r['latitude'], r['longitude'])] = address
        return result

    async def get_ride_options(
        self, pickup_lat: float, pickup_lng: float, dest_lat: float, dest_lng: float
    ) -> dict:
        """Navigate to uber.com, enter both addresses, and scrape available ride types."""
        if err := await self._ensure_ready():
            return err
        pickup = self._addr(pickup_lat, pickup_lng)
        dest = self._addr(dest_lat, dest_lng)
        logger.info('get_ride_options: pickup=%r dest=%r', pickup, dest)
        if not pickup or not dest:
            return {'error': 'MISSING_ADDRESS',
                    'message': 'No cached address for these coordinates.',
                    'recoverable': True,
                    'suggestion': 'Call uber_geocode for both pickup and destination first.'}
        page = self._session.page
        try:
            await page.goto('https://www.uber.com/us/en/rider-home/', wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(1)
            if not await _ba.fill_address(page, 0, pickup):
                return {'error': 'BROWSER_ERROR', 'message': 'Could not enter pickup address.',
                        'recoverable': True, 'suggestion': 'Uber UI may have changed — see SEL constants in browser_actions.py.'}
            if not await _ba.fill_address(page, 1, dest):
                return {'error': 'BROWSER_ERROR', 'message': 'Could not enter destination.',
                        'recoverable': True, 'suggestion': 'Uber UI may have changed — see SEL constants in browser_actions.py.'}
            if not await _ba.click_see_prices(page):
                return {'error': 'BROWSER_ERROR', 'message': 'Could not click "See prices" button.',
                        'recoverable': True, 'suggestion': 'Update _SEE_PRICES_BTN selector in browser_actions.py.'}
            options = await _ba.scrape_product_cards(page)
            if not options:
                return {'error': 'BROWSER_ERROR', 'message': 'No ride options found.',
                        'recoverable': True, 'suggestion': 'Update _PRODUCT_CARDS selector in browser_actions.py.'}
            return {'options': options}
        except Exception as exc:
            logger.error('get_ride_options: %s', exc)
            return {'error': 'BROWSER_ERROR', 'message': str(exc), 'recoverable': True, 'suggestion': 'Try again.'}

    async def request_estimate(
        self, product_id: str, pickup_lat: float, pickup_lng: float,
        dest_lat: float, dest_lng: float,
    ) -> dict:
        """Click the matching product card and return the displayed fare preview."""
        if err := await self._ensure_ready():
            return err
        try:
            name, fare_text = await _ba.click_product(self._session.page, product_id)
            if not name:
                return {'error': 'PRODUCT_NOT_FOUND', 'message': f'Ride type {product_id!r} not available.',
                        'recoverable': True, 'suggestion': 'Call uber_get_ride_options to refresh options.'}
            self._selected_product = name
            pn = re.findall(r'\d+(?:\.\d+)?', fare_text.replace(',', ''))
            return {
                'status': 'preview',
                'fare': {'display': fare_text.strip(), 'value': float(pn[0]) if pn else 0.0, 'currency': 'USD'},
                'eta_minutes': 0, 'product_name': name, 'fare_id': None,
            }
        except Exception as exc:
            logger.error('request_estimate: %s', exc)
            return {'error': 'BROWSER_ERROR', 'message': str(exc), 'recoverable': True, 'suggestion': 'Try again.'}

    async def request_ride(
        self, product_id: str, pickup_lat: float, pickup_lng: float,
        dest_lat: float, dest_lng: float, fare_id: str | None = None,
    ) -> dict:
        """Click the Request/Confirm button; scrape and return confirmed ride details."""
        if err := await self._ensure_ready():
            return err
        try:
            driver, eta_raw = await _ba.click_request(self._session.page)
            eta_nums = re.findall(r'\d+', eta_raw)
            ride_id = f'browser-ride-{int(time.time())}'
            self._active_ride_id = ride_id
            return {
                'status': 'confirmed', 'ride_id': ride_id,
                'driver': {'name': driver or 'Your driver', 'phone': None, 'rating': None},
                'vehicle': {'make': None, 'model': None, 'license_plate': None},
                'eta_minutes': int(eta_nums[0]) if eta_nums else 0,
            }
        except Exception as exc:
            logger.error('request_ride: %s', exc)
            return {'error': 'BROWSER_ERROR', 'message': str(exc), 'recoverable': True, 'suggestion': 'Try again.'}

    async def get_ride_status(self, ride_id: str) -> dict:
        """Scrape driver name and ETA from the active ride screen."""
        if err := await self._ensure_ready():
            return err
        page = self._session.page
        driver = await _ba.safe_text(page, _ba._DRIVER_NAME)
        eta_raw = await _ba.safe_text(page, _ba._ETA_ACTIVE)
        eta_nums = re.findall(r'\d+', eta_raw)
        return {
            'status': 'accepted',
            'driver': {'name': driver or 'Your driver', 'phone': None, 'rating': None},
            'vehicle': None,
            'eta_minutes': int(eta_nums[0]) if eta_nums else None,
        }

    async def cancel_ride(self, ride_id: str) -> dict:
        """Click Cancel and confirm the cancellation dialog."""
        if err := await self._ensure_ready():
            return err
        ok = await _ba.click_cancel(self._session.page)
        if not ok:
            return {'error': 'BROWSER_ERROR', 'message': 'Cancel button not found.',
                    'recoverable': False, 'suggestion': 'Cancel manually in the Uber app.'}
        self._active_ride_id = None
        return {'status': 'cancelled', 'cancellation_fee': None}

    def is_authenticated(self) -> bool:
        return self._session.is_logged_in

    def get_auth_url(self) -> str:
        return 'uber.com — call uber_authenticate to open a browser and log in.'

    def get_user_info(self) -> dict:
        return {'name': 'Browser session', 'email': 'logged in via uber.com'}
