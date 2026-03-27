# Uber API Reference

Exact endpoints, parameters, and responses for the Riders API v1.2.
Claude Code: use this as the source of truth for all Uber API calls. Do NOT guess endpoints.

## Base URLs

- Sandbox: `https://sandbox-api.uber.com/v1.2`
- Production: `https://api.uber.com/v1.2`

## Authentication

All requests require: `Authorization: Bearer {access_token}`
Content-Type: `application/json`

### OAuth Token Exchange

```
POST https://login.uber.com/oauth/v2/token
Content-Type: application/x-www-form-urlencoded

client_id={id}&client_secret={secret}&grant_type=authorization_code&code={auth_code}&redirect_uri={uri}
```

Response:
```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "scope": "profile request"
}
```

### Token Refresh

```
POST https://login.uber.com/oauth/v2/token
Content-Type: application/x-www-form-urlencoded

client_id={id}&client_secret={secret}&grant_type=refresh_token&refresh_token={token}
```

### OAuth Scopes

- `profile` — read user name/email
- `request` — book rides (privileged, auto-approved in sandbox)
- `ride_request` — view/manage active rides

### Auth URL Format

```
https://login.uber.com/oauth/v2/authorize?client_id={id}&response_type=code&scope=profile+request&redirect_uri={uri}
```

## Endpoints

### GET /v1.2/products

Get available products (UberX, Comfort, XL) at a location.

```
GET /v1.2/products?latitude={lat}&longitude={lng}
```

Response:
```json
{
  "products": [
    {
      "product_id": "a1111c8c-c720-46c3-8534-2fcdd730040d",
      "display_name": "UberX",
      "capacity": 4,
      "description": "Affordable rides",
      "image": "https://..."
    }
  ]
}
```

### GET /v1.2/estimates/price

Price estimates for a route. Does NOT require auth scope `request`.

```
GET /v1.2/estimates/price?start_latitude={lat}&start_longitude={lng}&end_latitude={lat}&end_longitude={lng}
```

Response:
```json
{
  "prices": [
    {
      "product_id": "a1111c8c-...",
      "display_name": "UberX",
      "currency_code": "USD",
      "low_estimate": 42,
      "high_estimate": 55,
      "estimate": "$42-55",
      "surge_multiplier": 1.0,
      "duration": 1800,
      "distance": 18.04
    }
  ]
}
```

### GET /v1.2/estimates/time

ETA for nearest drivers by product type.

```
GET /v1.2/estimates/time?start_latitude={lat}&start_longitude={lng}
```

Response:
```json
{
  "times": [
    {
      "product_id": "a1111c8c-...",
      "display_name": "UberX",
      "estimate": 240
    }
  ]
}
```

Note: `estimate` is in SECONDS. Convert to minutes for tool response.

### POST /v1.2/requests/estimate

Upfront fare estimate before requesting. Requires `request` scope.

```json
POST /v1.2/requests/estimate
{
  "product_id": "a1111c8c-...",
  "start_latitude": 40.7295,
  "start_longitude": -73.9965,
  "end_latitude": 40.6413,
  "end_longitude": -73.7781
}
```

Response:
```json
{
  "fare": {
    "display": "$48.00",
    "value": 48.00,
    "currency_code": "USD"
  },
  "trip": {
    "distance_estimate": 18.04,
    "distance_unit": "mile",
    "duration_estimate": 30
  },
  "pickup_estimate": 4
}
```

### POST /v1.2/requests

Request a ride. Requires `request` scope. THIS BOOKS A REAL RIDE IN PRODUCTION.

```json
POST /v1.2/requests
{
  "product_id": "a1111c8c-...",
  "start_latitude": 40.7295,
  "start_longitude": -73.9965,
  "end_latitude": 40.6413,
  "end_longitude": -73.7781,
  "fare_id": "..."
}
```

Note: `fare_id` comes from the /requests/estimate response when upfront fares are enabled.

Response:
```json
{
  "request_id": "b5512127-a134-4bf4-b1ba-fe9f93f...",
  "status": "processing",
  "product_id": "a1111c8c-...",
  "driver": null,
  "vehicle": null,
  "pickup": {
    "latitude": 40.7295,
    "longitude": -73.9965,
    "eta": 4
  },
  "destination": {
    "latitude": 40.6413,
    "longitude": -73.7781,
    "eta": 30
  }
}
```

### GET /v1.2/requests/{request_id}

Get status of a ride.

Response:
```json
{
  "request_id": "b5512127-...",
  "status": "accepted",
  "driver": {
    "name": "John",
    "phone_number": "+15551234567",
    "rating": 4.9,
    "picture_url": "https://..."
  },
  "vehicle": {
    "make": "Toyota",
    "model": "Camry",
    "license_plate": "ABC1234"
  },
  "location": {
    "latitude": 40.7295,
    "longitude": -73.9965,
    "bearing": 180
  },
  "pickup": {"eta": 3},
  "destination": {"eta": 28}
}
```

Possible `status` values:
- `processing` — looking for driver
- `accepted` — driver assigned
- `arriving` — driver approaching pickup
- `in_progress` — trip underway
- `driver_canceled` — driver canceled
- `rider_canceled` — rider canceled
- `completed` — trip finished
- `no_drivers_available` — no drivers found

### DELETE /v1.2/requests/{request_id}

Cancel a ride. Returns 204 on success.

If cancellation fee applies:
```json
{
  "cancellation_fee": {
    "amount": 5.00,
    "currency_code": "USD"
  }
}
```

## Sandbox-Specific

### PUT /v1.2/sandbox/requests/{request_id}

Step a sandbox ride through states. NOT available in production.

```json
PUT /v1.2/sandbox/requests/{request_id}
{
  "status": "accepted"
}
```

Valid status transitions:
- processing → accepted → arriving → in_progress → completed
- Any state → rider_canceled / driver_canceled

Returns 204 on success.

### PUT /v1.2/sandbox/products/{product_id}

Simulate surge pricing or driver unavailability in sandbox.

```json
{
  "surge_multiplier": 2.0,
  "drivers_available": false
}
```

## Error Format

All errors return JSON:
```json
{
  "message": "Human readable message",
  "code": "error_code_string"
}
```

For ride request errors:
```json
{
  "meta": { ... },
  "errors": [
    {
      "status": 409,
      "code": "surge",
      "title": "Surge pricing is currently in effect."
    }
  ]
}
```

### Common Error Codes

| HTTP | Code | Meaning |
|------|------|---------|
| 401 | unauthorized | Missing or invalid token |
| 403 | forbidden | Missing required scope |
| 404 | not_found | Resource doesn't exist |
| 409 | surge | Surge pricing, needs confirmation |
| 409 | fare_expired | Upfront fare estimate expired |
| 409 | retry | Transient error, retry |
| 422 | invalid_request | Missing required params |
| 422 | unprocessable | Invalid param values |
| 429 | rate_limited | Too many requests |
| 500 | internal_server_error | Uber server error |

### Account-Level Errors

Ride request may fail with 403 if rider account has issues:
- Invalid payment method
- Unverified phone number
- Account flagged for fraud
- Outstanding balance

These return a `message` explaining the issue.

## Important Notes

- Access tokens expire in 3600 seconds (1 hour). Always check expiry before API calls.
- In sandbox, rides stay in "processing" state forever unless you call PUT /sandbox/requests/{id} to advance them.
- The `fare_id` from /requests/estimate may be required for /requests in upfront fare markets. Include it if available.
- All timestamps are Unix epoch in UTC.
- Coordinates are floats with up to 6 decimal places.
- Currency follows ISO 4217 (USD, EUR, etc.).
