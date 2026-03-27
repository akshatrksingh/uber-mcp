# Coding Guidelines

Follow these rules strictly. They are non-negotiable.

## Strict No-Go's

- **NEVER run git add, git commit, git push, git init, or any git commands.** The user manages version control manually.
- **NEVER over-engineer.** No base classes, no factory patterns, no plugin systems, no abstract layers, no dependency injection frameworks. If a pattern isn't solving a concrete problem in this project, don't use it.
- **NEVER create unnecessary abstractions.** If there's only one implementation, don't make an interface/protocol for it. No `BaseProvider`, no `AbstractTool`, no `ToolRegistry` class.
- **NEVER add dependencies not listed in SYSTEM_DESIGN.md** without logging it in the Changelog.
- **NEVER expose auth tokens in tool responses.** Token lives in `self._access_token` and is only used in HTTP headers.
- **NEVER use `requests` library.** Use `httpx` with async.
- **NEVER use `print()` for debugging.** Use Python `logging` module.
- **NEVER create files over 200 lines.** Split into modules if approaching this.
- **NEVER use nested dicts as tool inputs.** All MCP tool parameters must be flat primitives (str, float, int, bool).
- **NEVER auto-retry ride booking failures.** Report error to user, let them decide.

## Code Style

- Python 3.12+ features are allowed
- Type hints on all function signatures
- Docstrings on all public functions (Google style)
- f-strings for formatting, never .format() or %
- Use `async/await` throughout — the MCP SDK is async
- Single quotes for strings unless the string contains a single quote
- No unused imports
- No commented-out code

## MCP Best Practices (Phil Schmid)

### 1. Outcomes, not operations
Each tool should accomplish what the user wants, not mirror an API endpoint. `uber_get_ride_options` internally calls two Uber endpoints and merges results — the LLM sees one tool that answers "what rides are available?"

### 2. Flatten arguments
All tool inputs are top-level primitives. Never:
```python
# BAD
def uber_request_ride(ride_config: dict): ...

# GOOD
def uber_request_ride(product_id: str, pickup_latitude: float, ...): ...
```

### 3. Instructions are context
Every tool needs a rich docstring that tells the LLM:
- WHEN to use this tool
- WHAT the inputs mean
- WHAT to expect back
- HOW it relates to other tools

Example:
```python
@server.tool()
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
```

### 4. Curate ruthlessly
- Strip unnecessary fields from Uber API responses before returning
- Only return what the LLM needs to present to the user or pass to the next tool
- Never dump raw API responses

### 5. Name for discovery
All tools prefixed with `uber_`. This is already defined in SYSTEM_DESIGN.md.

### 6. Errors are context
Error responses are NOT exceptions thrown to the user. They are structured data the LLM reads and reasons about.

```python
# BAD - raw exception
raise ValueError("Invalid location")

# GOOD - structured error the LLM can act on
return {
    "error": "INVALID_LOCATION",
    "message": "Could not find 'asdfgh'. Try a more specific address.",
    "recoverable": True,
    "suggestion": "Ask the user for a more specific location name."
}
```

Every error includes: `error` (code), `message` (human-readable), `recoverable` (bool), `suggestion` (for LLM).

## Tool Response Curation

When mapping Uber API responses to tool outputs, strip everything the LLM doesn't need:

```python
# BAD - raw Uber response passthrough
return uber_response

# GOOD - curated
return {
    "product_id": uber_response["product_id"],
    "name": uber_response["display_name"],
    "estimate_low": uber_response["low_estimate"],
    "estimate_high": uber_response["high_estimate"],
    "currency": uber_response["currency_code"],
    "eta_minutes": uber_response["eta"] // 60 if uber_response.get("eta") else None,
}
```

## Input Validation

Validate all inputs at the tool level before calling any API:

```python
if not (-90 <= pickup_latitude <= 90):
    return {"error": "INVALID_INPUT", "message": "Latitude must be between -90 and 90", ...}
if not address or not address.strip():
    return {"error": "INVALID_INPUT", "message": "Address cannot be empty", ...}
```

## State Guards

The state manager enforces critical safety checks:

```python
# In uber_request_ride, BEFORE calling Uber API:
if confirm and state.last_preview is None:
    return {"error": "NO_PREVIEW", "message": "No preview found. Call with confirm=false first.", ...}
if confirm and state.active_ride is not None:
    return {"error": "RIDE_CONFLICT", "message": "A ride is already in progress.", ...}
```

These guards are server-side and cannot be bypassed by the LLM.

## Mock Provider Pattern

The mock provider must return the same dict structure as the real provider:

```python
class MockProvider:
    async def get_ride_options(self, pickup_lat, pickup_lng, dest_lat, dest_lng):
        return {"options": [
            {"product_id": "mock-uberx-001", "name": "UberX",
             "estimate_low": 42.0, "estimate_high": 55.0,
             "currency": "USD", "eta_minutes": 4, "capacity": 4},
            # ... more options
        ]}
```

The agent code should not know whether it's talking to mock or real — same interface.

## File Organization

- One tool per file in `src/tools/`
- Each tool file exports one async function
- `server.py` imports all tools and registers them
- No circular imports — tools import from clients, never from each other
- `__init__.py` files are empty or contain only `__all__`

## Logging

Use structured logging:
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Calling Uber API: %s", endpoint)
logger.error("Uber API error: %s %s", status_code, error_code)
logger.debug("Tool response: %s", response)  # Only in debug mode
```

Never log tokens or credentials.
