import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class MockProvider:
    """Returns hardcoded realistic responses for all tool operations.

    Used when --mock flag is passed. Return shapes must match real provider exactly.
    """

    async def geocode(self, address: str) -> dict:
        """Return fake coordinates for well-known NYC locations.

        Args:
            address: Location string from user.

        Returns:
            Single result dict or ambiguous results list.
        """
        logger.info('Mock geocode: %s', address)
        known = {
            'nyu': {
                'latitude': 40.7295,
                'longitude': -73.9965,
                'display_name': 'New York University, Washington Square, Manhattan, NY',
            },
            'jfk': {
                'latitude': 40.6413,
                'longitude': -73.7781,
                'display_name': 'John F. Kennedy International Airport, Queens, NY',
            },
            'jfk airport': {
                'latitude': 40.6413,
                'longitude': -73.7781,
                'display_name': 'John F. Kennedy International Airport, Queens, NY',
            },
            'times square': {
                'latitude': 40.7580,
                'longitude': -73.9855,
                'display_name': 'Times Square, Midtown Manhattan, New York, NY',
            },
            'laguardia': {
                'latitude': 40.7769,
                'longitude': -73.8740,
                'display_name': 'LaGuardia Airport (LGA), Queens, New York, NY',
            },
            'laguardia airport': {
                'latitude': 40.7769,
                'longitude': -73.8740,
                'display_name': 'LaGuardia Airport (LGA), Queens, New York, NY',
            },
            'central park': {
                'latitude': 40.7851,
                'longitude': -73.9683,
                'display_name': 'Central Park, Manhattan, New York, NY',
            },
            'grand central': {
                'latitude': 40.7527,
                'longitude': -73.9772,
                'display_name': 'Grand Central Terminal, Midtown East, Manhattan, NY',
            },
        }
        key = address.strip().lower()
        if key in known:
            return known[key]

        # Ambiguous: return top 3 plausible NYC results
        return {
            'results': [
                {
                    'latitude': 40.7128,
                    'longitude': -74.0060,
                    'display_name': f'{address}, Downtown Manhattan, New York, NY',
                },
                {
                    'latitude': 40.7282,
                    'longitude': -73.7949,
                    'display_name': f'{address}, Queens, New York, NY',
                },
                {
                    'latitude': 40.6782,
                    'longitude': -73.9442,
                    'display_name': f'{address}, Brooklyn, New York, NY',
                },
            ],
            'ambiguous': True,
        }

    async def get_ride_options(
        self,
        pickup_lat: float,
        pickup_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> dict:
        """Return fake ride options for a route.

        Args:
            pickup_lat: Pickup latitude.
            pickup_lng: Pickup longitude.
            dest_lat: Destination latitude.
            dest_lng: Destination longitude.

        Returns:
            Dict with options list.
        """
        logger.info('Mock get_ride_options: %s,%s → %s,%s', pickup_lat, pickup_lng, dest_lat, dest_lng)
        return {
            'options': [
                {
                    'product_id': 'mock-uberx-001',
                    'name': 'UberX',
                    'estimate_low': 42.0,
                    'estimate_high': 55.0,
                    'currency': 'USD',
                    'eta_minutes': 4,
                    'capacity': 4,
                },
                {
                    'product_id': 'mock-comfort-002',
                    'name': 'Comfort',
                    'estimate_low': 55.0,
                    'estimate_high': 70.0,
                    'currency': 'USD',
                    'eta_minutes': 6,
                    'capacity': 4,
                },
                {
                    'product_id': 'mock-uberxl-003',
                    'name': 'UberXL',
                    'estimate_low': 68.0,
                    'estimate_high': 85.0,
                    'currency': 'USD',
                    'eta_minutes': 8,
                    'capacity': 6,
                },
                {
                    'product_id': 'mock-black-004',
                    'name': 'Uber Black',
                    'estimate_low': 95.0,
                    'estimate_high': 115.0,
                    'currency': 'USD',
                    'eta_minutes': 10,
                    'capacity': 4,
                },
            ]
        }

    async def request_estimate(
        self,
        product_id: str,
        pickup_lat: float,
        pickup_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> dict:
        """Return a fake upfront fare estimate (preview).

        Args:
            product_id: The selected product ID.
            pickup_lat: Pickup latitude.
            pickup_lng: Pickup longitude.
            dest_lat: Destination latitude.
            dest_lng: Destination longitude.

        Returns:
            Preview dict with status, fare, eta, product_name.
        """
        logger.info('Mock request_estimate: product_id=%s', product_id)
        names = {
            'mock-uberx-001': ('UberX', '$48.00', 48.00, 4),
            'mock-comfort-002': ('Comfort', '$62.00', 62.00, 6),
            'mock-uberxl-003': ('UberXL', '$75.00', 75.00, 8),
            'mock-black-004': ('Uber Black', '$105.00', 105.00, 10),
        }
        name, display, value, eta = names.get(product_id, ('UberX', '$48.00', 48.00, 4))
        return {
            'status': 'preview',
            'fare': {'display': display, 'value': value, 'currency': 'USD'},
            'eta_minutes': eta,
            'product_name': name,
            'fare_id': f'mock-fare-{product_id}',
        }

    async def request_ride(
        self,
        product_id: str,
        pickup_lat: float,
        pickup_lng: float,
        dest_lat: float,
        dest_lng: float,
        fare_id: str | None = None,
    ) -> dict:
        """Return a fake confirmed ride booking.

        Args:
            product_id: The selected product ID.
            pickup_lat: Pickup latitude.
            pickup_lng: Pickup longitude.
            dest_lat: Destination latitude.
            dest_lng: Destination longitude.
            fare_id: Optional fare ID from estimate.

        Returns:
            Confirmed ride dict with driver and vehicle info.
        """
        logger.info('Mock request_ride: product_id=%s', product_id)
        ride_id = f'mock-ride-{uuid.uuid4().hex[:8]}'
        names = {
            'mock-uberx-001': ('UberX', 4),
            'mock-comfort-002': ('Comfort', 6),
            'mock-uberxl-003': ('UberXL', 8),
            'mock-black-004': ('Uber Black', 10),
        }
        product_name, eta = names.get(product_id, ('UberX', 4))
        return {
            'status': 'confirmed',
            'ride_id': ride_id,
            'driver': {'name': 'Marcus J.', 'phone': '+15551234567', 'rating': 4.92},
            'vehicle': {'make': 'Toyota', 'model': 'Camry', 'license_plate': 'NYC4821'},
            'eta_minutes': eta,
            'product_name': product_name,
            'booked_at': datetime.utcnow().isoformat() + 'Z',
        }

    async def get_ride_status(self, ride_id: str) -> dict:
        """Return a fake ride status.

        Args:
            ride_id: The ride ID to check.

        Returns:
            Status dict with driver and vehicle info.
        """
        logger.info('Mock get_ride_status: ride_id=%s', ride_id)
        return {
            'status': 'accepted',
            'driver': {'name': 'Marcus J.', 'phone': '+15551234567', 'rating': 4.92},
            'vehicle': {'make': 'Toyota', 'model': 'Camry', 'license_plate': 'NYC4821'},
            'eta_minutes': 3,
        }

    async def cancel_ride(self, ride_id: str) -> dict:
        """Return a fake cancellation response.

        Args:
            ride_id: The ride ID to cancel.

        Returns:
            Cancellation dict (no fee in mock).
        """
        logger.info('Mock cancel_ride: ride_id=%s', ride_id)
        return {
            'status': 'cancelled',
            'cancellation_fee': None,
        }

    def is_authenticated(self) -> bool:
        """Mock always returns authenticated.

        Returns:
            True always.
        """
        return True

    def get_auth_url(self) -> str:
        """Return a fake OAuth URL.

        Returns:
            Fake auth URL string.
        """
        return 'https://login.uber.com/oauth/v2/authorize?client_id=mock&response_type=code&scope=profile+request'

    def get_user_info(self) -> dict:
        """Return fake user profile.

        Returns:
            User dict with name and email.
        """
        return {'name': 'Test User', 'email': 'test@example.com'}
