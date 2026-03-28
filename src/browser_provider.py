"""Browser-based Uber provider — drives uber.com via Playwright.

Implements the same interface as MockProvider; MCP tools are unchanged.
Browser is used ONLY for get_ride_options (navigate + scrape).
Everything after that (preview, confirm, status, cancel) is in-memory mock.
"""
import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from src import browser_actions as _ba
from src import geocoding_client
from src.browser_session import BrowserSession

logger = logging.getLogger(__name__)

_HISTORY_PATH = Path.home() / '.uber-mcp' / 'rides_history.json'

MOCK_DRIVERS = [
    {'name': 'Marcus T.',  'rating': 4.92, 'vehicle': ('Toyota',  'Camry',   'TLC-4829')},
    {'name': 'Priya S.',   'rating': 4.88, 'vehicle': ('Honda',   'Accord',  'TLC-7731')},
    {'name': 'James W.',   'rating': 4.95, 'vehicle': ('Hyundai', 'Sonata',  'TLC-2156')},
    {'name': 'Sofia R.',   'rating': 4.91, 'vehicle': ('Toyota',  'Prius',   'TLC-8843')},
    {'name': 'David K.',   'rating': 4.87, 'vehicle': ('Nissan',  'Altima',  'TLC-3367')},
    {'name': 'Aisha M.',   'rating': 4.93, 'vehicle': ('Kia',     'K5',      'TLC-5512')},
    {'name': 'Carlos P.',  'rating': 4.89, 'vehicle': ('Honda',   'Civic',   'TLC-9948')},
    {'name': 'Lin Z.',     'rating': 4.94, 'vehicle': ('Tesla',   'Model 3', 'TLC-1125')},
]


def _load_history() -> list[dict]:
    try:
        return json.loads(_HISTORY_PATH.read_text()) if _HISTORY_PATH.exists() else []
    except Exception as exc:
        logger.warning('Could not read rides_history.json: %s', exc)
        return []


def _save_history(history: list[dict]) -> None:
    try:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _HISTORY_PATH.write_text(json.dumps(history, indent=2))
    except Exception as exc:
        logger.warning('Could not write rides_history.json: %s', exc)


class BrowserProvider:
    """Implements the MockProvider interface by automating uber.com."""

    def __init__(self) -> None:
        self._session = BrowserSession()
        self._addr_cache: dict[str, str] = {}   # "lat,lng" → original address string
        self._last_options: list[dict] = []      # scraped from last get_ride_options call
        self._last_ride: dict | None = None      # set on confirm=true

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _key(self, lat: float, lng: float) -> str:
        return f'{lat:.4f},{lng:.4f}'

    def _addr(self, lat: float, lng: float) -> str:
        return self._addr_cache.get(self._key(lat, lng), '')

    def _find_option(self, product_id: str) -> dict | None:
        return next((o for o in self._last_options if o['product_id'] == product_id), None)

    async def _ensure_ready(self) -> dict | None:
        """Start the browser and verify Uber login."""
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
        """Resolve coordinates via geocoding_client and cache the address string."""
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
        """Navigate to uber.com, enter both addresses, scrape and store ride options."""
        if err := await self._ensure_ready():
            return err
        pickup = self._addr(pickup_lat, pickup_lng)
        dest = self._addr(dest_lat, dest_lng)
        logger.info('get_ride_options: pickup=%r dest=%r', pickup, dest)
        if not pickup or not dest:
            return {
                'error': 'MISSING_ADDRESS',
                'message': 'No cached address for these coordinates.',
                'recoverable': True,
                'suggestion': 'Call uber_geocode for both pickup and destination first.',
            }
        page = self._session.page
        try:
            await page.goto('https://www.uber.com/us/en/rider-home/', wait_until='domcontentloaded', timeout=30000)
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
            self._last_options = options
            return {'options': options}
        except Exception as exc:
            logger.error('get_ride_options: %s', exc)
            return {'error': 'BROWSER_ERROR', 'message': str(exc), 'recoverable': True, 'suggestion': 'Try again.'}

    async def request_estimate(
        self, product_id: str, pickup_lat: float, pickup_lng: float,
        dest_lat: float, dest_lng: float,
    ) -> dict:
        """Return a fare preview from stored ride options — no browser interaction."""
        option = self._find_option(product_id)
        if not option:
            return {
                'error': 'PRODUCT_NOT_FOUND',
                'message': f'Ride type {product_id!r} not in last options list.',
                'recoverable': True,
                'suggestion': 'Call uber_get_ride_options first.',
            }
        low, high = option['estimate_low'], option['estimate_high']
        display = f'${low:.2f}' if low == high else f'${low:.2f}–${high:.2f}'
        return {
            'status': 'preview',
            'fare': {'display': display, 'value': low, 'currency': option['currency']},
            'eta_minutes': option['eta_minutes'],
            'product_name': option['name'],
            'fare_id': None,
        }

    async def request_ride(
        self, product_id: str, pickup_lat: float, pickup_lng: float,
        dest_lat: float, dest_lng: float, fare_id: str | None = None,
    ) -> dict:
        """Return a mock confirmed ride using stored option data and persist to history.

        # MOCK: Real implementation would click the "Request" button or call Uber API.
        """
        option = self._find_option(product_id)
        ride_id = f'uber-{int(time.time())}'
        now = datetime.now(timezone.utc).isoformat()
        low = option['estimate_low'] if option else 0
        high = option['estimate_high'] if option else 0
        fare_display = f'${low:.2f}' if low == high else f'${low:.2f}–${high:.2f}'

        driver = random.choice(MOCK_DRIVERS)
        make, model, plate = driver['vehicle']

        self._last_ride = {
            'ride_id': ride_id,
            'product_name': option['name'] if option else product_id,
            'booked_at': time.time(),
            'driver': driver,
        }

        entry = {
            'ride_id': ride_id,
            'product_name': self._last_ride['product_name'],
            'pickup': self._addr(pickup_lat, pickup_lng),
            'destination': self._addr(dest_lat, dest_lng),
            'fare': fare_display,
            'booked_at': now,
            'status': 'confirmed',
        }
        history = _load_history()
        history.append(entry)
        _save_history(history)

        return {
            'status': 'confirmed',
            'ride_id': ride_id,
            'product_name': self._last_ride['product_name'],
            'driver': {'name': driver['name'], 'phone': None, 'rating': driver['rating']},
            'vehicle': {'make': make, 'model': model, 'license_plate': plate},
            'eta_minutes': option['eta_minutes'] if option else 3,
            'note': 'Mock confirmation — in production this would trigger a real Uber booking via API or browser click.',
        }

    async def get_ride_status(self, ride_id: str) -> dict:
        """Return a mock ride status that progresses based on time since booking.

        # MOCK: Real implementation would scrape the active-ride screen or call Uber API.
        """
        booked_at = self._last_ride['booked_at'] if self._last_ride else time.time()
        elapsed = time.time() - booked_at
        if elapsed < 60:
            status, eta = 'accepted', 3
        elif elapsed < 180:
            status, eta = 'arriving', 1
        elif elapsed < 300:
            status, eta = 'in_progress', None
        else:
            status, eta = 'completed', None
        driver = self._last_ride.get('driver', MOCK_DRIVERS[0]) if self._last_ride else MOCK_DRIVERS[0]
        make, model, plate = driver['vehicle']
        return {
            'status': status,
            'driver': {'name': driver['name'], 'phone': None, 'rating': driver['rating']},
            'vehicle': {'make': make, 'model': model, 'license_plate': plate},
            'eta_minutes': eta,
        }

    async def cancel_ride(self, ride_id: str) -> dict:
        """Return a mock cancellation and update history status to 'cancelled'.

        # MOCK: Real implementation would click the Cancel button or call Uber API.
        """
        history = _load_history()
        for entry in history:
            if entry['ride_id'] == ride_id:
                entry['status'] = 'cancelled'
                break
        _save_history(history)
        self._last_ride = None
        return {'status': 'cancelled', 'cancellation_fee': None}

    def get_ride_history(self) -> list[dict]:
        """Return all persisted rides from rides_history.json."""
        return _load_history()

    def is_authenticated(self) -> bool:
        return self._session.is_logged_in

    def get_auth_url(self) -> str:
        return 'uber.com — call uber_authenticate to open a browser and log in.'

    def get_user_info(self) -> dict:
        return {'name': 'Browser session', 'email': 'logged in via uber.com'}
