"""Maps Uber API HTTP errors to the project's structured error format."""


def map_uber_error(status: int, body: dict) -> dict:
    """Convert an Uber API error response to a structured tool error dict.

    Args:
        status: HTTP status code from the Uber API.
        body: Parsed JSON response body.

    Returns:
        Dict with error, message, recoverable, suggestion keys.
    """
    errors = body.get('errors', [])
    code = (errors[0].get('code', '') if errors else body.get('code', '')).lower()
    msg = (
        errors[0].get('title') if errors else body.get('message', '')
    ) or 'Uber API error'

    if status == 401:
        return {'error': 'AUTH_EXPIRED', 'message': 'Session expired.',
                'recoverable': True, 'suggestion': 'Call uber_authenticate to re-authorize.'}
    if status == 403:
        return {'error': 'ACCOUNT_BLOCKED', 'message': msg,
                'recoverable': False, 'suggestion': 'Check Uber account for payment or verification issues.'}
    if status == 404:
        return {'error': 'RIDE_NOT_FOUND', 'message': 'Ride not found.',
                'recoverable': False, 'suggestion': 'Check the ride_id.'}
    if status == 409 and code == 'surge':
        return {'error': 'SURGE_REQUIRED', 'message': 'Surge pricing is active.',
                'recoverable': True, 'suggestion': 'Inform the user and confirm they accept the higher fare.'}
    if status == 409:
        return {'error': 'RIDE_CONFLICT', 'message': msg,
                'recoverable': False, 'suggestion': 'Check for an already-active ride.'}
    if status == 422:
        err = 'INVALID_LOCATION' if 'location' in msg.lower() else 'INVALID_INPUT'
        return {'error': err, 'message': msg,
                'recoverable': True, 'suggestion': 'Check the coordinates or input values.'}
    if status == 429:
        return {'error': 'RATE_LIMITED', 'message': 'Too many requests.',
                'recoverable': True, 'suggestion': 'Wait a moment then try again.'}
    return {'error': 'UBER_SERVICE_ERROR', 'message': msg,
            'recoverable': False, 'suggestion': 'Try again later.'}
