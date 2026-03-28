# Uber MCP Server

An MCP (Model Context Protocol) server that lets a Claude agent book Uber rides through natural conversation. The agent geocodes locations, compares ride options, previews fares, and books rides — all via six structured tools over stdio transport. Supports a `--mock` mode with hardcoded NYC data so you can run the full booking flow without any Uber credentials.

---

## Quick Start (mock mode — no credentials needed)

```bash
git clone <this-repo> && cd uber-mcp
cp .env.example .env && echo "ANTHROPIC_API_KEY=your_key_here" >> .env
uv sync && uv run python agent/cli_agent.py --mock
```

Then type something like:

```
You: Book me an Uber from NYU to JFK
```

---

## Full Setup (real Uber sandbox)

**1. Install dependencies**

```bash
uv sync
```

**2. Configure environment**

```bash
cp .env.example .env
# Edit .env — fill in UBER_CLIENT_ID, UBER_CLIENT_SECRET, ANTHROPIC_API_KEY
```

**3. Authorize with Uber (one-time)**

```bash
uv run python setup_auth.py
# Opens a browser → authorize → token.json is saved automatically
```

**4. Run the agent**

```bash
uv run python agent/cli_agent.py
```

### Required environment variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `UBER_CLIENT_ID` | From Uber Developer Dashboard |
| `UBER_CLIENT_SECRET` | From Uber Developer Dashboard |
| `UBER_REDIRECT_URI` | Must match your app's OAuth redirect (default: `http://localhost:3000/callback`) |
| `UBER_ENVIRONMENT` | `sandbox` or `production` (default: `sandbox`) |
| `GOOGLE_MAPS_API_KEY` | Optional — enables Google Maps geocoding; falls back to Nominatim without it |

---

## Architecture

```
agent/cli_agent.py          ← Claude Sonnet 4 + MCP client (you talk to this)
    │ stdio subprocess
src/server.py               ← MCP server, 6 tools registered
    ├── src/tools/          ← One file per tool
    ├── src/uber_client.py  ← Real Uber API (Phase 4)
    ├── src/geocoding_client.py
    ├── src/auth_manager.py
    ├── src/state_manager.py
    └── src/mock_provider.py ← Used with --mock
```

See [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) for full architecture details.

---

## Tools

| Tool | Description |
|------|-------------|
| `uber_authenticate` | Check auth status or get an OAuth URL to re-authorize |
| `uber_geocode` | Convert a location name or address to lat/lng coordinates |
| `uber_get_ride_options` | Get available ride types with price ranges and ETAs for a route |
| `uber_request_ride` | Preview a ride (`confirm=false`) or book it (`confirm=true`) |
| `uber_get_ride_status` | Check the status of a ride; defaults to the active ride |
| `uber_cancel_ride` | Cancel an active ride; reports any cancellation fee |

---

## Example Conversation

```
You: Book me an Uber from NYU to JFK

Agent: [uber_geocode × 2, uber_get_ride_options]

  Here are your ride options from NYU to JFK Airport:

  | Option     | Price      | ETA    | Seats |
  |------------|------------|--------|-------|
  | UberX      | $42–$55    | 4 min  | 4     |
  | Comfort    | $55–$70    | 6 min  | 4     |
  | UberXL     | $68–$85    | 8 min  | 6     |
  | Uber Black | $95–$115   | 10 min | 4     |

  Which option would you like?

You: UberX

Agent: [uber_request_ride confirm=false]

  Fare: $48.00 · ETA: 4 min. Shall I book this ride? (yes/no)

You: yes

Agent: [uber_request_ride confirm=true]

  Confirmed! Driver: Marcus J. ★4.92 · Toyota Camry NYC4821 · 4 min away.
```

See [transcripts/](transcripts/) for five complete conversation examples.

---

## Safety guards

- **Preview required**: calling `uber_request_ride(confirm=true)` without a prior `confirm=false` call returns a `NO_PREVIEW` error — bookings cannot be made without an explicit fare preview.
- **One ride at a time**: a second booking while a ride is active returns `RIDE_CONFLICT`.
- **Tokens never exposed**: OAuth tokens live in `token.json` and are only used in HTTP headers — they never appear in tool responses or logs.
