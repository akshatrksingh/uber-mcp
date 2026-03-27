"""Geocoding client — mock implementation for Phase 2.

Phase 4 will replace _geocode_mock with real Google Maps / Nominatim calls.
The public interface (geocode) stays the same.
"""
import logging

logger = logging.getLogger(__name__)

_KNOWN: dict[str, dict] = {
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
    'brooklyn bridge': {
        'latitude': 40.7061,
        'longitude': -73.9969,
        'display_name': 'Brooklyn Bridge, Manhattan/Brooklyn, New York, NY',
    },
    'columbia university': {
        'latitude': 40.8075,
        'longitude': -73.9626,
        'display_name': 'Columbia University, Morningside Heights, Manhattan, NY',
    },
}

_cache: dict[str, dict] = {}


async def geocode(address: str) -> dict:
    """Convert an address or location name to coordinates.

    Returns a single result for unambiguous input, or top-3 with
    ambiguous=true for unknown addresses.

    Args:
        address: Location name or street address.

    Returns:
        {latitude, longitude, display_name}
        OR {results: [...], ambiguous: true}
    """
    key = address.strip().lower()
    if key in _cache:
        logger.debug('Geocode cache hit: %s', address)
        return _cache[key]

    logger.info('Geocoding address: %s', address)

    if key in _KNOWN:
        result = _KNOWN[key]
        _cache[key] = result
        return result

    # Unknown address — return ambiguous top-3
    result = {
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
    _cache[key] = result
    return result
