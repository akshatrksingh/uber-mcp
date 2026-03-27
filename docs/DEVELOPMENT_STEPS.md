# Development Steps

Build in order. Do not skip phases. Test at every checkpoint before moving on.

## Phase 1: Project scaffold + Mock provider

### Steps
1. Create `pyproject.toml` with all dependencies from SYSTEM_DESIGN.md
2. Create `.env.example` with all required env vars:
   ```
   UBER_CLIENT_ID=your_client_id
   UBER_CLIENT_SECRET=your_client_secret
   UBER_REDIRECT_URI=http://localhost:3000/callback
   UBER_ENVIRONMENT=sandbox
   GOOGLE_MAPS_API_KEY=optional_for_geocoding
   ANTHROPIC_API_KEY=your_anthropic_key
   ```
3. Create `.gitignore` (include: .env, token.json, ride_history.json, __pycache__, .venv)
4. Create `src/mock_provider.py` with hardcoded realistic responses for ALL tool operations
5. Create `src/state_manager.py` with: active_ride, last_preview, last_options, ride history file I/O
6. Create `src/server.py` as MCP server entry point — register all 6 tools, wire to mock provider

### Self-test
Run the MCP server and verify tool listing works:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python -m src.server
```
Then send tools/list to verify all 6 tools are registered with correct names and schemas.

### User checkpoint
User runs: `uv sync && python -c "from src.server import main; print('Server imports OK')"`

---

## Phase 2: Implement tools with mock provider

Build each tool one at a time. After each tool, test it.

### Step 2a: uber_geocode
1. Create `src/tools/geocode.py`
2. Create `src/geocoding_client.py` (start with mock, real API later)
3. Tool accepts `address: str`, returns lat/lng/display_name
4. Handle ambiguous results (return top 3)

**Self-test**: Call uber_geocode with "NYU" via MCP Inspector or JSON-RPC pipe. Verify response shape matches SYSTEM_DESIGN.md.

### Step 2b: uber_get_ride_options
1. Create `src/tools/ride_options.py`
2. Tool accepts 4 floats, returns list of ride options
3. Validate coordinate ranges

**Self-test**: Call with NYC coordinates. Verify response has `options` array with correct fields.

### Step 2c: uber_request_ride
1. Create `src/tools/request_ride.py`
2. Implement confirm=false (preview) and confirm=true (book) paths
3. **Implement server-side guards**:
   - confirm=true without last_preview → NO_PREVIEW error
   - active ride exists → RIDE_CONFLICT error
4. On confirmed: write to ride_history.json via state_manager

**Self-test**:
- Call with confirm=false → verify preview response
- Call with confirm=true WITHOUT prior preview → verify NO_PREVIEW error
- Call with confirm=false, then confirm=true → verify booking response
- Call confirm=true again → verify RIDE_CONFLICT error
- Check ride_history.json was written

### Step 2d: uber_get_ride_status
1. Create `src/tools/ride_status.py`
2. Accept optional ride_id, default to state.active_ride
3. Return status, driver, vehicle info

**Self-test**: After a mock booking, call without ride_id → verify returns active ride status.

### Step 2e: uber_cancel_ride
1. Create `src/tools/cancel_ride.py`
2. Validate ride_id exists
3. Clear state.active_ride

**Self-test**: After mock booking, cancel → verify cancelled response. Call cancel again → verify error.

### Step 2f: uber_authenticate
1. Create `src/tools/auth.py`
2. Create `src/auth_manager.py` (start with reading token.json, skip OAuth flow for now)
3. Tool returns auth URL or confirms authentication

**Self-test**: With no token.json, call → verify auth_required response. Create dummy token.json, restart server → verify authenticated.

### User checkpoint
User tests full mock flow via MCP Inspector:
1. uber_geocode("NYU") → get coords
2. uber_geocode("JFK Airport") → get coords
3. uber_get_ride_options(coords) → get options
4. uber_request_ride(product_id, coords, confirm=false) → preview
5. uber_request_ride(product_id, coords, confirm=true) → booked
6. uber_get_ride_status() → status
7. uber_cancel_ride(ride_id) → cancelled

All 7 calls should succeed with mock data.

---

## Phase 3: CLI Agent

### Steps
1. Create `agent/cli_agent.py` using Claude Agent SDK (anthropic)
2. Agent connects to MCP server via stdio subprocess
3. Simple REPL: read user input → send to Claude with tools → print response
4. Support `--mock` flag (passed through to MCP server)
5. Agent system prompt should instruct Claude:
   - Always geocode locations before requesting rides
   - Always preview before booking (confirm=false first)
   - Present ride options clearly to the user
   - Ask for user confirmation before booking
   - Report errors in plain language

### Self-test
Run `python agent/cli_agent.py --mock` and type "Book me an Uber from NYU to JFK".
Agent should:
1. Call uber_geocode twice
2. Call uber_get_ride_options
3. Present options to user
4. Wait for user selection
5. Preview the ride
6. Ask for confirmation
7. Book on confirmation

### User checkpoint
User runs: `python agent/cli_agent.py --mock`
Verify the full conversation flow works end-to-end with mock data.

---

## Phase 4: Real Uber API integration

### Steps
1. Update `src/uber_client.py` — implement all methods with real httpx calls to Uber sandbox API
2. Update `src/geocoding_client.py` — implement Google Maps geocoding (with Nominatim fallback)
3. Update `src/auth_manager.py` — implement token reading, refresh, expiry checking
4. Create `setup_auth.py`:
   - Generate OAuth URL with scopes: profile, request
   - Start temporary HTTP server on localhost:3000
   - Catch callback, exchange code for tokens
   - Save to token.json
5. Wire real providers into server.py (use mock if --mock flag, real otherwise)
6. Implement sandbox ride state stepping:
   - After POST /requests, call PUT /sandbox/requests/{id} with status "accepted"
   - Then step to "arriving", "in_progress" as needed for testing

### Error mapping
Map all Uber API errors to our error format:
- 401 → AUTH_EXPIRED
- 404 → RIDE_NOT_FOUND
- 409 code:surge → SURGE_REQUIRED
- 409 code:other → RIDE_CONFLICT
- 422 → INVALID_LOCATION or INVALID_INPUT (check error body)
- 429 → RATE_LIMITED
- 500+ → UBER_SERVICE_ERROR
- Account-level blocks → ACCOUNT_BLOCKED

### Self-test
With real Uber sandbox credentials:
1. Run setup_auth.py → get token
2. Start server without --mock
3. Call uber_geocode("Times Square") → verify real coordinates
4. Call uber_get_ride_options with real NYC coords → verify real products
5. Call uber_request_ride(confirm=false) → verify real estimate
6. Call uber_request_ride(confirm=true) → verify sandbox ride created
7. Step sandbox ride to "accepted" → call uber_get_ride_status → verify
8. Call uber_cancel_ride → verify

### User checkpoint
User runs: `python setup_auth.py` (one-time auth)
Then: `python agent/cli_agent.py` (real sandbox mode)
Full booking conversation should work against real Uber sandbox.

---

## Phase 5: Transcripts + README + Learnings

### Steps
1. Record 5 conversation transcripts by running the CLI agent:
   - `01_basic_booking.md` — "Book me an Uber from NYU to JFK" (happy path)
   - `02_compare_options.md` — "What rides are available from Times Square to LaGuardia?" (user picks)
   - `03_cancel_ride.md` — Book then cancel (test cancel + fee)
   - `04_error_handling.md` — Invalid address, bad input (test error paths)
   - `05_multi_step.md` — Change destination mid-flow, check status

2. Each transcript format:
   ```markdown
   # Transcript: [Scenario Name]
   
   **Mode:** sandbox / mock
   **Date:** YYYY-MM-DD
   
   ---
   
   **User:** Book me an Uber from NYU to JFK
   
   **Agent:** [Agent's response including tool calls made]
   
   **User:** [Next message]
   
   ...
   ```

3. Write `README.md`:
   - Project description (1 paragraph)
   - Quick start with --mock (3 commands: clone, uv sync, run)
   - Full setup with Uber sandbox (setup_auth.py, env vars)
   - Architecture overview (brief, link to SYSTEM_DESIGN.md)
   - Tool list with one-line descriptions
   - Example conversation snippet

4. Write `LEARNINGS.md` — keep this SUPER SHORT (max 1 page):
   - What went well
   - What was harder than expected
   - Auth design choices and tradeoffs
   - What you'd do differently at scale
   - MCP observations (what works, what's awkward)

### User checkpoint
User reviews all 5 transcripts for quality and readability.
User reviews README for clarity — can someone follow it from zero?

---

## Phase 6: Polish

### Steps
1. Verify .gitignore covers: .env, token.json, ride_history.json, __pycache__, .venv, *.pyc
2. Verify .env.example has all required vars with placeholder values
3. Run full --mock flow one more time to verify nothing is broken
4. Optional: record asciinema terminal session for README
5. Final review of all files for: unused imports, commented-out code, print statements, hardcoded credentials

### User checkpoint
Final end-to-end test:
1. `uv sync`
2. `python agent/cli_agent.py --mock` → full booking conversation
3. Review ride_history.json
4. Review all files in repo

---

## Key reminders during development

- Check CODING_GUIDELINES.md before writing any code
- Check UBER_API_REFERENCE.md before calling any Uber endpoint
- Log all design deviations in SYSTEM_DESIGN.md Changelog
- Never run git commands
- Test after every tool, not just at the end
