# Friction Log — HomeOps for Alexa+

Real build friction, recorded as it happened. Submitted with the hackathon
entry for the +10% judging bonus; also filed as product feedback where noted.

---

## 1. `pip install mcp` pulled the v2 SDK — FastMCP is gone
- **Attempted:** `pip install mcp`, then `from mcp.server.fastmcp import FastMCP`.
- **Expected:** FastMCP (the documented v1 API) to exist.
- **Actual:** `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` with a
  migration note — in mcp 2.x FastMCP was renamed to `MCPServer`
  (`from mcp.server.mcpserver import MCPServer`).
- **Severity:** Medium — every v1 tutorial/blog is now stale.
- **Workaround:** Used `MCPServer`; verified `streamable_http_app()` and the
  `tool()` decorator still exist under the new name.
- **Suggestion:** The migration guide URL printed in the error is good, but the
  PyPI page should banner the rename — most search results still show FastMCP.

## 2. Client import renamed too: `streamablehttp_client` → `streamable_http_client`
- **Attempted:** `from mcp.client.streamable_http import streamablehttp_client`.
- **Expected:** The v1 import path.
- **Actual:** `ImportError` (with a helpful "Did you mean" suggestion).
- **Severity:** Low.
- **Workaround:** Used `streamable_http_client`; session API
  (`ClientSession.initialize/list_tools/call_tool`) is unchanged.
- **Suggestion:** Same as above — a single canonical migration page linked from
  the old names would save everyone one round-trip.

## 3. PEP 668 blocks `pip install` on the system Python
- **Attempted:** `pip install mcp strands-agents pytest` on Ubuntu's Python 3.12.
- **Expected:** Install to succeed.
- **Actual:** "externally-managed-environment" refusal.
- **Severity:** Low (standard now, but surprises newcomers).
- **Workaround:** Project-local venv at `.venv/`; documented in README quickstart.
- **Suggestion:** N/A — environment behavior, not Amazon's.

## 4. No Alexa+ developer docs reachable from the hackathon page for the simulated path
- **Attempted:** Looked for the "simulated Alexa+ experience" web-app contract
  (what counts as a valid simulation, any required disclaimers/branding rules).
- **Expected:** A short spec or checklist on the Devpost resources tab.
- **Actual:** Only the track paragraph; nothing defining the simulation's
  boundaries (e.g. must it say "simulated"? can it use Alexa branding?).
- **Severity:** Medium — I chose to label the UI "SIMULATED EXPERIENCE" and keep
  Amazon trademarks to nominative use, but I'm guessing.
- **Workaround:** Conservative labeling + honest architecture section in the video.
- **Suggestion:** Publish a one-page "simulated experience" guideline with
  branding do/don'ts; it would raise submission quality across the track.

## 5. Bedrock model IDs: Nova naming is easy to get subtly wrong
- **Attempted:** Picking a default `BEDROCK_MODEL_ID` for the Strands `BedrockModel`.
- **Expected:** One obvious current Nova id.
- **Actual:** Several near-identical ids across docs (`amazon.nova-lite-v1:0` vs
  cross-region `us.amazon.nova-lite-v1:0`); wrong choice = opaque auth/region error.
- **Severity:** Low-Medium.
- **Workaround:** Default to `us.amazon.nova-lite-v1:0`, region `us-west-2`,
  override via env; Bedrock path is exercised in CI-less local runs via the
  scripted model, clearly labeled.
- **Suggestion:** Strands could validate the model id format early and suggest
  the inference-profile form when a region prefix is missing.

## 8. MCP v2 transport objects are bound to their event loop — fresh loop per await hangs
- **Attempted:** A test helper that created a new `asyncio` event loop for every
  client call (`asyncio.new_event_loop().run_until_complete(...)`).
- **Expected:** Each call independent and clean.
- **Actual:** Total hang — the v2 `ClientSession`/transport (anyio task groups)
  is bound to the loop that entered it; awaiting it from another loop blocks
  forever with no error.
- **Severity:** High for test authors; silent hang, no traceback.
- **Workaround:** One loop per test, shared across enter/call/exit.
- **Suggestion:** Document the loop-affinity requirement on the client
  quickstart; a hang with zero diagnostics is the worst failure mode.

## 7. MCP SDK's default HTTP client breaks on sandbox proxy env vars
- **Attempted:** `streamable_http_client("http://127.0.0.1:8765/mcp")` with no args.
- **Expected:** Localhost connection just works.
- **Actual:** `httpx2.InvalidURL: Invalid port: ':1]'` — the SDK builds its
  default `AsyncClient` with proxy env honored, and this sandbox's `NO_PROXY`
  contains IPv6 literals (`[::1]`) that httpx2's URLPattern parser rejects.
- **Severity:** Medium — in any proxied corporate/sandbox environment, the
  out-of-box client fails even for localhost.
- **Workaround:** Pass an explicit `httpx2.AsyncClient(trust_env=False)` via
  the `http_client=` parameter (correct here: we call our own server).
- **Suggestion:** `create_mcp_http_client()` should catch proxy-config parse
  failures and fall back to a direct connection with a warning, or document the
  `http_client=` escape hatch in the client quickstart.

## 6. Strands scripted-model streaming contract is learn-by-reading-source
- **Attempted:** Implementing a deterministic `Model` subclass for offline evals.
- **Expected:** A documented minimal event sequence for tool_use turns.
- **Actual:** No "authoring a custom model" quickstart found; derived the
  `messageStart → contentBlockStart → contentBlockDelta → messageStop` shapes
  from `llamacpp.py` source.
- **Severity:** Low (worked), but slows contributors.
- **Workaround:** Read the provider implementations; wrote `ScriptedModel`.
- **Suggestion:** A 40-line "echo model" example in the Strands docs would make
  eval/offline patterns first-class.
