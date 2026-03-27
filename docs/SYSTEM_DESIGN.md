# System Design — Uber MCP Server

This document is the source of truth for building this project. Follow it exactly.

## Overview

Build an MCP server (Python) that lets a Claude agent book Uber rides via conversation. 6 tools, stdio transport, sandbox environment.

## Stack

- Python 3.12+, `uv` for deps
- MCP Python SDK (`mcp`)
- Claude Agent SDK (`anthropic`)
- `httpx` for async HTTP
- `python-dotenv` for env vars
- `click` for CLI

## Architecture

```
CLI Agent (cli_agent.py)
  └─ Claude Sonnet 4 (claude-sonnet-4-20250514)
      └─ MCP Client (SDK-provided)
          └─ stdio transport (JSON-RPC 2.0)
              └─ MCP Server (server.py)
                  ├─ Tools (6 tools, uber_ prefixed)
                  ├─ Auth Manager (token.json, refresh)
                  ├─ State Manager (active ride, preview guard, history)
                  ├─ Uber API Client (httpx, sandbox)
                  ├─ Geocoding Client (Google Maps / Nominatim)
                  └─ Mock Provider (--mock flag)
```

## Tool Definitions

All tools: `uber_` prefix, flat primitive inputs only, return dicts.

### uber_authenticate

```python
# Fallback for mid-session token expiry
Input:  auth_code: str | None = None
Output: {"status": "authenticated", "user": {"name": str, "email": str}}
    OR: {"status": "auth_required", "auth_url": str}
```
- Token stored in private `self._token`, never returned
- Docstring: "Use when other tools return AUTH_EXPIRED error. Provides a URL for the user to re-authorize."

### uber_geocode

```python
Input:  address: str
Output: {"latitude": float, "longitude": float, "display_name": str}
    OR: {"results": [{"latitude": float, "longitude": float, "display_name": str}], "ambiguous": true}
```
- If 1 clear match: return single result
- If multiple matches: return top 3 with `ambiguous: true`
- Docstring: "Convert a location name or address to coordinates. Use before uber_get_ride_options. Example: 'NYU' → lat/lng."

### uber_get_ride_options

```python
Input:  pickup_latitude: float, pickup_longitude: float,
        destination_latitude: float, destination_longitude: float
Output: {"options": [
    {"product_id": str, "name": str, "estimate_low": float,
     "estimate_high": float, "currency": str, "eta_minutes": int,
     "capacity": int}
]}
```
- Internally calls Uber's GET /v1.2/estimates/price AND GET /v1.2/estimates/time
- Merges and curates results (strip unnecessary fields)
- Docstring: "Get available ride types with prices for a route. Call uber_geocode first for both pickup and destination."

### uber_request_ride

```python
Input:  product_id: str, pickup_latitude: float, pickup_longitude: float,
        destination_latitude: float, destination_longitude: float,
        confirm: bool = False
Output (confirm=False):
    {"status": "preview", "fare": {"display": str, "value": float, "currency": str},
     "eta_minutes": int, "product_name": str}
Output (confirm=True):
    {"status": "confirmed", "ride_id": str,
     "driver": {"name": str, "phone": str, "rating": float},
     "vehicle": {"make": str, "model": str, "license_plate": str},
     "eta_minutes": int}
```
- **GUARD**: If `confirm=True` and `state.last_preview` is None → return error "No preview found. Call with confirm=false first."
- **GUARD**: If `state.active_ride` is not None → return error "A ride is already in progress."
- On confirmed booking: write to ride_history.json, set state.active_ride
- confirm=False → Uber POST /v1.2/requests/estimate
- confirm=True → Uber POST /v1.2/requests
- Docstring: "Preview a ride (confirm=false) or book it (confirm=true). Always preview first — booking without preview is blocked."

### uber_get_ride_status

```python
Input:  ride_id: str | None = None  # defaults to state.active_ride
Output: {"status": str, "driver": {...}, "vehicle": {...}, "eta_minutes": int | None}
```
- Statuses: "processing", "accepted", "arriving", "in_progress", "completed", "cancelled"
- Uber GET /v1.2/requests/{ride_id}
- Docstring: "Check the status of a ride. If no ride_id given, checks the most recent ride."

### uber_cancel_ride

```python
Input:  ride_id: str
Output: {"status": "cancelled", "cancellation_fee": {"amount": float, "currency": str} | None}
```
- **GUARD**: If ride_id doesn't match an active ride → error
- Uber DELETE /v1.2/requests/{ride_id}
- Clear state.active_ride
- Docstring: "Cancel an active ride. May incur a cancellation fee."

## Internal Modules

### auth_manager.py
- `__init__`: Read token from `token.json` if exists
- `get_token() -> str`: Return current access token
- `refresh_token()`: Use refresh token to get new access token from Uber
- `is_authenticated() -> bool`
- Private `self._access_token`, `self._refresh_token` — NEVER expose
- Token refresh: POST https://login.uber.com/oauth/v2/token with grant_type=refresh_token
- Uber access tokens expire in ~1 hour (3600s). Check expiry before each API call.

### state_manager.py
- `active_ride: str | None` — current ride_id
- `last_preview: dict | None` — last preview response (for confirm guard)
- `last_options: list | None` — last ride options (for product_id validation)
- `save_ride(ride_data: dict)` — append to ride_history.json
- `get_ride_history() -> list` — read ride_history.json
- `clear()` — reset in-memory state

### uber_client.py
- Base URL: `https://sandbox-api.uber.com/v1.2` (UBER_ENVIRONMENT=sandbox)
          or `https://api.uber.com/v1.2` (UBER_ENVIRONMENT=production)
- All methods async, use httpx.AsyncClient
- Methods:
  - `get_products(lat, lng) -> list`
  - `get_price_estimates(start_lat, start_lng, end_lat, end_lng) -> list`
  - `get_time_estimates(lat, lng) -> list`
  - `request_estimate(product_id, start, end) -> dict`
  - `request_ride(product_id, start, end, fare_id) -> dict`
  - `get_ride(ride_id) -> dict`
  - `cancel_ride(ride_id) -> dict`
  - `update_sandbox_ride(ride_id, status) -> None`  # sandbox only
- Curate all responses: only return fields the tools need
- Error handling: catch httpx errors, map to structured error dicts

### geocoding_client.py
- Google Maps: GET https://maps.googleapis.com/maps/api/geocode/json?address={}&key={}
- Nominatim fallback: GET https://nominatim.openstreetmap.org/search?q={}&format=json
- Use Google if GOOGLE_MAPS_API_KEY in env, else Nominatim
- Cache recent lookups in dict (address → result)

### mock_provider.py
- Provides fake responses for all tool operations
- Realistic data: real NYC addresses, plausible prices, driver names
- Activated when `--mock` flag is passed to cli_agent.py
- Same return type signatures as real providers

## Error Format

Every tool error returns:
```python
{
    "error": "ERROR_CODE",       # machine-readable
    "message": "Human text",     # LLM reads this
    "recoverable": True/False,   # LLM decides retry vs give up
    "suggestion": "Try X"        # LLM tells user this
}
```

Error codes:
- AUTH_EXPIRED — token invalid, need re-auth
- INVALID_LOCATION — geocode failed or Uber can't route
- RIDE_NOT_FOUND — ride_id doesn't exist
- RIDE_CONFLICT — ride already active
- NO_PREVIEW — confirm=true without prior preview
- RATE_LIMITED — too many requests
- UBER_SERVICE_ERROR — Uber API 5xx
- INVALID_INPUT — bad coordinates, empty address, etc.
- SURGE_REQUIRED — surge pricing active (409 from Uber)
- ACCOUNT_BLOCKED — rider account issue (payment, fraud)

## File Layout

```
uber-mcp-server/
├── pyproject.toml
├── .env.example
├── .gitignore
├── setup_auth.py
├── README.md
├── LEARNINGS.md
├── src/
│   ├── server.py
│   ├── tools/
│   │   ├── auth.py
│   │   ├── geocode.py
│   │   ├── ride_options.py
│   │   ├── request_ride.py
│   │   ├── ride_status.py
│   │   └── cancel_ride.py
│   ├── uber_client.py
│   ├── geocoding_client.py
│   ├── auth_manager.py
│   ├── state_manager.py
│   └── mock_provider.py
├── agent/
│   └── cli_agent.py
├── transcripts/
│   ├── 01_basic_booking.md
│   ├── 02_compare_options.md
│   ├── 03_cancel_ride.md
│   ├── 04_error_handling.md
│   └── 05_multi_step.md
└── ride_history.json (auto-generated)
```

## Sandbox Notes

- Sandbox base URL: https://sandbox-api.uber.com/v1.2
- In sandbox, rides don't progress automatically. Use PUT /v1.2/sandbox/requests/{id} to step through states:
  - "accepted" → "arriving" → "in_progress" → "completed"
- Sandbox returns simulated products, prices, and driver info
- No real charges, no real drivers

## Changelog

_Deviations from this design are logged below by Claude Code as development progresses._

