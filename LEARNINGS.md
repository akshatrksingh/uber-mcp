# Learnings

## What went well

- **MCP tool design clicked fast.** The "outcomes not operations" principle from the MCP guidelines is the right instinct. `uber_get_ride_options` internally calls two Uber endpoints but the agent sees one clean tool. Claude never needs to know about `/estimates/price` vs `/estimates/time`.
- **Flat inputs remove a whole class of errors.** No nested dicts in tool parameters means no ambiguity in how Claude passes arguments. The schema is self-documenting.
- **Structured errors are genuinely better than exceptions.** Claude reads `{"error": "NO_PREVIEW", "recoverable": true, "suggestion": "..."}` and gives the user a sensible next step. An uncaught exception would just confuse it.
- **`--mock` made iteration fast.** Being able to run the full booking flow without any credentials meant all the agent/tool/state logic could be validated before touching the real API.

## What was harder than expected

- **Circular imports.** `server.py` wants to register tools; tools need access to the provider; provider is configured in `server.py`. Solved with a tiny `src/provider.py` registry, but it took a moment to see clearly.
- **Async input in the REPL.** Python's `input()` blocks the event loop. For this project it's fine (one turn at a time), but a production agent would need `asyncio.to_thread` or a proper async readline.
- **MCP session lifecycle.** The `stdio_client` / `ClientSession` async context managers need the subprocess to stay alive for the whole conversation. Getting the nesting right (and graceful shutdown on `KeyboardInterrupt` inside an `ExceptionGroup`) required care.

## Auth design choices

- Tokens stored in `token.json`, never in env vars — env vars appear in `ps` output and CI logs.
- `_access_token` and `_refresh_token` are private attributes; they are never returned by any tool.
- Expiry is tracked by `issued_at + expires_in` so the manager can pre-emptively refresh before a request fails rather than recovering after a 401.
- OAuth flow is separate (`setup_auth.py`) from the server — the server never redirects or opens browsers. Clean separation of setup vs runtime.

## What I'd do differently at scale

- **Per-user state.** `StateManager` is a global singleton. A multi-tenant deployment needs state keyed by session/user ID.
- **Persistent preview guard.** `last_preview` lives in memory and is lost on server restart. A real deployment would store it in Redis or a DB with a TTL.
- **Token storage.** `token.json` is fine for a single-user CLI. At scale: encrypted secrets manager (AWS Secrets Manager, Vault) with automatic rotation.
- **Geocoding cache.** The in-memory dict works for a session. A shared Redis cache with a 24h TTL would be appropriate for a service.

## MCP observations

- **What works well:** The stdio transport is dead simple. Any subprocess that speaks JSON-RPC 2.0 is an MCP server. The Python SDK's `FastMCP` class removes almost all boilerplate.
- **What's awkward:** There's no standard way for a tool to "stream" a response mid-call (e.g., showing live ETA updates). Each tool call is a single request/response. For ride tracking you'd need polling from the agent.
- **Tool docstrings are load-bearing.** The LLM's decision about *when* to call a tool depends almost entirely on the docstring. A vague description leads to wrong tool selection. Writing tools is half code, half prompt engineering.
