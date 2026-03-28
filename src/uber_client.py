"""Uber API client — async httpx calls to the Riders API v1.2."""
import asyncio
import logging
import os

import httpx

from src.auth_manager import AuthManager
from src.uber_errors import map_uber_error

logger = logging.getLogger(__name__)

_SANDBOX_BASE = 'https://sandbox-api.uber.com/v1.2'
_PROD_BASE = 'https://api.uber.com/v1.2'


class UberClient:
    """Async Uber Riders API v1.2 client. Shares provider interface with MockProvider."""

    def __init__(self, auth: AuthManager) -> None:
        env = os.environ.get('UBER_ENVIRONMENT', 'sandbox')
        self._base = _SANDBOX_BASE if env == 'sandbox' else _PROD_BASE
        self._auth = auth
        self._sandbox = (env == 'sandbox')

    async def _request(self, method: str, path: str, **kwargs) -> tuple[int, dict]:
        """Make an authenticated request; returns (status_code, body)."""
        try:
            await self._auth.ensure_token()
        except RuntimeError as exc:
            return 401, {'message': str(exc), 'code': 'unauthorized'}
        headers = {
            'Authorization': f'Bearer {self._auth.get_token()}',
            'Content-Type': 'application/json',
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await getattr(client, method)(
                    f'{self._base}{path}', headers=headers, **kwargs
                )
            try:
                body = resp.json() if resp.content else {}
            except Exception:
                body = {}
            return resp.status_code, body
        except httpx.RequestError as exc:
            logger.error('HTTP request error: %s', exc)
            return 503, {'message': str(exc)}

    async def _get_products(self, lat: float, lng: float) -> list:
        s, b = await self._request('get', '/products', params={'latitude': lat, 'longitude': lng})
        return b.get('products', []) if s == 200 else []

    async def _get_price_estimates(
        self, slat: float, slng: float, elat: float, elng: float
    ) -> list:
        s, b = await self._request('get', '/estimates/price', params={
            'start_latitude': slat, 'start_longitude': slng,
            'end_latitude': elat, 'end_longitude': elng,
        })
        return b.get('prices', []) if s == 200 else []

    async def _get_time_estimates(self, lat: float, lng: float) -> list:
        s, b = await self._request('get', '/estimates/time', params={
            'start_latitude': lat, 'start_longitude': lng,
        })
        return b.get('times', []) if s == 200 else []

    async def get_ride_options(
        self, pickup_lat: float, pickup_lng: float, dest_lat: float, dest_lng: float
    ) -> dict:
        """Merge products, price estimates, and time estimates into a ride options list.

        Calls GET /products, GET /estimates/price, GET /estimates/time concurrently.
        """
        products, prices, times = await asyncio.gather(
            self._get_products(pickup_lat, pickup_lng),
            self._get_price_estimates(pickup_lat, pickup_lng, dest_lat, dest_lng),
            self._get_time_estimates(pickup_lat, pickup_lng),
        )
        if not prices:
            return map_uber_error(422, {'message': 'No rides available for this route.'})
        cap = {p['product_id']: p.get('capacity', 0) for p in products}
        eta = {t['product_id']: t.get('estimate', 0) for t in times}
        return {'options': [
            {
                'product_id': p['product_id'],
                'name': p['display_name'],
                'estimate_low': p.get('low_estimate') or 0,
                'estimate_high': p.get('high_estimate') or 0,
                'currency': p.get('currency_code', 'USD'),
                'eta_minutes': (eta.get(p['product_id'], 0) or 0) // 60,
                'capacity': cap.get(p['product_id'], 0),
            }
            for p in prices
        ]}

    async def request_estimate(
        self, product_id: str, pickup_lat: float, pickup_lng: float,
        dest_lat: float, dest_lng: float,
    ) -> dict:
        """POST /v1.2/requests/estimate — upfront fare preview."""
        status, body = await self._request('post', '/requests/estimate', json={
            'product_id': product_id, 'start_latitude': pickup_lat,
            'start_longitude': pickup_lng, 'end_latitude': dest_lat, 'end_longitude': dest_lng,
        })
        if status != 200:
            return map_uber_error(status, body)
        fare = body.get('fare', {})
        products = await self._get_products(pickup_lat, pickup_lng)
        name = next(
            (p['display_name'] for p in products if p['product_id'] == product_id), product_id
        )
        return {
            'status': 'preview',
            'fare': {'display': fare.get('display', ''), 'value': fare.get('value', 0.0),
                     'currency': fare.get('currency_code', 'USD')},
            'eta_minutes': body.get('pickup_estimate', 0),
            'product_name': name,
            'fare_id': fare.get('fare_id'),
        }

    async def request_ride(
        self, product_id: str, pickup_lat: float, pickup_lng: float,
        dest_lat: float, dest_lng: float, fare_id: str | None = None,
    ) -> dict:
        """POST /v1.2/requests — book a ride; auto-advances sandbox state to accepted."""
        payload: dict = {'product_id': product_id, 'start_latitude': pickup_lat,
                         'start_longitude': pickup_lng, 'end_latitude': dest_lat,
                         'end_longitude': dest_lng}
        if fare_id:
            payload['fare_id'] = fare_id
        status, body = await self._request('post', '/requests', json=payload)
        if status not in (200, 201, 202):
            return map_uber_error(status, body)
        ride_id = body.get('request_id', '')
        pickup_eta = (body.get('pickup') or {}).get('eta', 0)
        if self._sandbox and ride_id:
            try:
                await self.update_sandbox_ride(ride_id, 'accepted')
                sd = await self.get_ride_status(ride_id)
                return {'status': 'confirmed', 'ride_id': ride_id,
                        'driver': sd.get('driver'), 'vehicle': sd.get('vehicle'),
                        'eta_minutes': sd.get('eta_minutes') or pickup_eta}
            except Exception as exc:
                logger.warning('Sandbox state advance failed: %s', exc)
        return {'status': 'confirmed', 'ride_id': ride_id,
                'driver': None, 'vehicle': None, 'eta_minutes': pickup_eta}

    async def get_ride_status(self, ride_id: str) -> dict:
        """GET /v1.2/requests/{ride_id}."""
        status, body = await self._request('get', f'/requests/{ride_id}')
        if status != 200:
            return map_uber_error(status, body)
        d = body.get('driver') or {}
        v = body.get('vehicle') or {}
        return {
            'status': body.get('status'),
            'driver': {'name': d.get('name'), 'phone': d.get('phone_number'),
                       'rating': d.get('rating')} if d else None,
            'vehicle': {'make': v.get('make'), 'model': v.get('model'),
                        'license_plate': v.get('license_plate')} if v else None,
            'eta_minutes': (body.get('pickup') or {}).get('eta'),
        }

    async def cancel_ride(self, ride_id: str) -> dict:
        """DELETE /v1.2/requests/{ride_id}."""
        status, body = await self._request('delete', f'/requests/{ride_id}')
        if status == 204:
            return {'status': 'cancelled', 'cancellation_fee': None}
        if status in (200, 202):
            fee = body.get('cancellation_fee')
            return {'status': 'cancelled',
                    'cancellation_fee': {'amount': fee.get('amount'),
                                         'currency': fee.get('currency_code')} if fee else None}
        return map_uber_error(status, body)

    async def update_sandbox_ride(self, ride_id: str, status: str) -> None:
        """PUT /v1.2/sandbox/requests/{ride_id} — step sandbox ride through states."""
        code, _ = await self._request(
            'put', f'/sandbox/requests/{ride_id}', json={'status': status}
        )
        if code not in (200, 204):
            raise RuntimeError(f'Sandbox state update failed: HTTP {code}')
        logger.info('Sandbox ride %s → %s', ride_id, status)

    def is_authenticated(self) -> bool:
        return self._auth.is_authenticated()

    def get_auth_url(self) -> str:
        return self._auth.get_auth_url()

    def get_user_info(self) -> dict:
        return self._auth.get_user_info()
