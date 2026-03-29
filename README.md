# uber-mcp

An MCP server that lets a Claude agent book Uber rides through conversation. The agent geocodes addresses, scrapes live ride options from uber.com via Playwright browser automation, and walks through a preview-then-confirm booking flow. The final booking step is mocked to prevent accidental real charges — everything up to and including price scraping uses the real Uber website.

---

## Quick Start (mock mode)

No Uber account needed. Requires only an Anthropic API key.

```bash
# 1. Install dependencies
uv sync
playwright install chromium

# 2. Set your API key
echo "ANTHROPIC_API_KEY=sk-..." > .env

# 3. Run
uv run python -m agent.cli_agent --mock
```

---

## Live Mode Setup

Live mode scrapes real prices from uber.com using your logged-in Uber account.

```bash
# 1. Install dependencies
uv sync
playwright install

# 2. Set your API key
cp .env.example .env
# edit .env and add ANTHROPIC_API_KEY

# 3. One-time browser login (opens Chrome, you log in manually)
uv run python setup_browser.py

# 4. Run the agent (hands-free from here on)
uv run python -m agent.cli_agent
```

Your session is saved in `~/.uber-mcp/chrome-profile`. You won't need to log in again unless the session expires.

---

## Architecture

```
agent/cli_agent.py              Claude Agent SDK — conversational REPL
  └─ MCP Client (stdio)
      └─ src/server.py           FastMCP server — registers 7 tools
          ├─ src/tools/          One file per tool
          ├─ src/browser_provider.py   Real provider (Playwright)
          │   ├─ src/browser_session.py   Chrome lifecycle + login detection
          │   └─ src/browser_actions.py   DOM interactions, selectors, screenshots
          ├─ src/mock_provider.py      Fake provider for --mock mode
          ├─ src/geocoding_client.py   Nominatim / Google Maps
          └─ src/state_manager.py      Active ride, last preview, history
```

---

## Tools

| Tool | What it does |
|------|-------------|
| `uber_authenticate` | Check login state; returns auth URL if session expired |
| `uber_geocode` | Convert address or landmark to lat/lng coordinates |
| `uber_get_ride_options` | Navigate uber.com, enter addresses, scrape all available ride types with live prices and ETAs |
| `uber_request_ride` | `confirm=false` → fare preview from scraped data; `confirm=true` → mock booking confirmation |
| `uber_get_ride_status` | Mock status that progresses accepted → arriving → in_progress → completed over time |
| `uber_cancel_ride` | Cancel active ride; updates `~/.uber-mcp/rides_history.json` |
| `uber_ride_history` | Read all booked rides from `~/.uber-mcp/rides_history.json` |

---

## Example Conversation

```
You: book an uber from times square to laguardia airport

Agent: Here are all available ride options from Times Square to LaGuardia Airport:

  • Shuttle         $21.84   ETA: <1 min
  • Share           $67.26   ETA: 1 min
  • UberX           $78.22   ETA: 1 min
  • Electric        $78.22   ETA: 4 min
  • Comfort         $93.44   ETA: 2 min
  • UberXL          $98.99   ETA: 2 min
  • Black          $108.47   ETA: 2 min
  • Black SUV      $152.25   ETA: 3 min

  Which would you like?

You: shuttle

Agent: Ride Preview — Shuttle, $21.84, arriving now. Shall I book? (yes/no)

You: yes

Agent: Ride confirmed!
  Driver: Marcus T. ★ 4.92 · Toyota Camry · TLC-4829
  ETA: arriving now · Fare: $21.84 · Ride ID: uber-1774733159
```

Transcripts are auto-saved to `transcripts/` after every session.

---

## How Auth Works

Uber's browser automation requires a real logged-in session.

1. **First time:** run `setup_browser.py` — Chrome opens, you log in to uber.com, session is saved to `~/.uber-mcp/chrome-profile`
2. **Every run after:** `BrowserSession` launches Chrome with that profile — no login prompt, no cookies to manage
3. **Session expires:** run `setup_browser.py` again to refresh

Login is detected by checking for the presence of `[data-uweb-guide-key="RV_PUDO_PICKUP_INPUT"]` — the pickup input on the ride-booking form. If it's absent, the agent waits up to 120 seconds for manual login before returning `LOGIN_REQUIRED`.

---

## Safety Guards

- **Preview required:** `uber_request_ride(confirm=true)` is blocked if `confirm=false` was never called first
- **One ride at a time:** a second booking is blocked while `state.active_ride` is set
- **Booking is mocked:** the "Request" button is never clicked in the browser — mock confirmation data is returned to prevent real charges
- **Ride history persists:** every confirmed booking is appended to `~/.uber-mcp/rides_history.json`

---

## Environment Variables

```
ANTHROPIC_API_KEY=required
GOOGLE_MAPS_API_KEY=optional  # falls back to Nominatim if absent
```
