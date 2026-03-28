"""Geocoding client — Google Maps with Nominatim fallback.

Uses Google Maps Geocoding API if GOOGLE_MAPS_API_KEY is set in the environment.
Falls back to Nominatim (OpenStreetMap) otherwise. Results are cached in memory.
"""
import logging
import os
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

_GOOGLE_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
_NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
_NOMINATIM_HEADERS = {'User-Agent': 'uber-mcp-agent/1.0'}

_cache: dict[str, dict] = {}


def _single(lat: float, lng: float, display: str) -> dict:
    return {'latitude': lat, 'longitude': lng, 'display_name': display}


def _ambiguous(results: list[dict]) -> dict:
    return {'results': results[:3], 'ambiguous': True}


async def _google(address: str) -> dict | None:
    """Call Google Maps Geocoding API. Returns result dict or None on failure."""
    key = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_GOOGLE_URL, params={'address': address, 'key': key})
        body = resp.json()
    except Exception as exc:
        logger.warning('Google Maps request failed: %s', exc)
        return None

    if body.get('status') == 'ZERO_RESULTS':
        return {'error': 'INVALID_LOCATION',
                'message': f'No results found for "{address}".',
                'recoverable': True,
                'suggestion': 'Try a more specific address or landmark name.'}
    if body.get('status') != 'OK':
        logger.warning('Google Maps status: %s', body.get('status'))
        return None  # fall through to Nominatim

    hits = body.get('results', [])
    if not hits:
        return None
    if len(hits) == 1:
        loc = hits[0]['geometry']['location']
        return _single(loc['lat'], loc['lng'], hits[0]['formatted_address'])
    return _ambiguous([
        _single(h['geometry']['location']['lat'],
                h['geometry']['location']['lng'],
                h['formatted_address'])
        for h in hits
    ])


async def _nominatim(address: str) -> dict:
    """Call Nominatim (OpenStreetMap). Always returns a result dict."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                _NOMINATIM_URL,
                params={'q': address, 'format': 'json', 'limit': 3},
                headers=_NOMINATIM_HEADERS,
            )
        hits = resp.json()
    except Exception as exc:
        logger.error('Nominatim request failed: %s', exc)
        return {'error': 'INVALID_LOCATION',
                'message': f'Geocoding service unavailable for "{address}".',
                'recoverable': True,
                'suggestion': 'Try again or provide more specific coordinates.'}

    if not hits:
        return {'error': 'INVALID_LOCATION',
                'message': f'No results found for "{address}".',
                'recoverable': True,
                'suggestion': 'Try a more specific address or nearby landmark.'}
    if len(hits) == 1:
        return _single(float(hits[0]['lat']), float(hits[0]['lon']), hits[0]['display_name'])
    return _ambiguous([
        _single(float(h['lat']), float(h['lon']), h['display_name']) for h in hits
    ])


async def geocode(address: str) -> dict:
    """Convert an address or location name to coordinates.

    Uses Google Maps if GOOGLE_MAPS_API_KEY is set, otherwise Nominatim.
    Results are cached in memory for the lifetime of the process.

    Args:
        address: Location name or street address.

    Returns:
        {latitude, longitude, display_name}
        OR {results: [...], ambiguous: true}
        OR {error, message, recoverable, suggestion}
    """
    key = address.strip().lower()
    if key in _cache:
        logger.debug('Geocode cache hit: %s', address)
        return _cache[key]

    logger.info('Geocoding: %s', address)

    result: dict | None = None
    if os.environ.get('GOOGLE_MAPS_API_KEY'):
        result = await _google(address)

    if result is None:
        result = await _nominatim(address)

    _cache[key] = result
    return result
