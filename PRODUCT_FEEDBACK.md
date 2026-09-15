# Product Feedback — HomeOps for Alexa+

Feedback on every tool / API / SDK used, in Devpost form format. Author: Solana Minter.

---

## 1. MCP Python SDK v2 (`mcp` 2.1.1 — server + client, Streamable HTTP)

- **Used for:** The entire Alexa+ track anchor — a self-hosted MCP server
  (`MCPServer`, `streamable_http_app()`) exposing 16 household tools, and the
  client (`streamable_http_client` + `ClientSession`) the Strands agent uses to
  invoke them at runtime. Protocol version negotiated: 2026-07-28 (exceeds the
  2025-11-25 requirement).
- **What worked well:** The `MCPServer` decorator API is genuinely pleasant —
  `@mcp.tool(name=...)` with type-hinted signatures producing correct JSON
  schemas, and `streamable_http_app()` giving a ready ASGI app. The
  "Did you mean …?" import suggestions saved real time during the v1→v2 rename.
- **What needs work:**
  1. `create_mcp_http_client()` honors proxy env vars and crashes with
     `httpx2.InvalidURL: Invalid port: ':1]'` when `NO_PROXY` contains IPv6
     literals like `[::1]` — in sandboxed/corporate environments the default
     client fails even for localhost. It should fall back to a direct
     connection with a warning, or the `http_client=` escape hatch should be
     front-and-center in the client quickstart.
  2. Transport/session objects are silently bound to the event loop that
     entered them; awaiting them from another loop hangs forever with no
     error. The loop-affinity requirement deserves a bold note in the docs.
  3. The v1→v2 rename (`FastMCP` → `MCPServer`, `streamablehttp_client` →
     `streamable_http_client`) broke every tutorial on the internet overnight;
     the PyPI page should banner the migration guide.
- **Onboarding experience:** 6/10. The in-error migration link is good, but I
  learned the streaming event shapes and client loop rules from source code,
  not docs.
- **Would use again?** Yes — the decorator ergonomics and spec currency are
  strong. I'd pin `mcp>=2,<3` and wrap client construction defensively from
  day one.

## 2. Strands SDK (`strands-agents` 1.55.1 — agent orchestration)

- **Used for:** The orchestration layer — a Strands `Agent` with 16 `@tool`
  functions that call the MCP server, driven in production by `BedrockModel`
  and in evals/demo by a deterministic `ScriptedModel`.
- **What worked well:** The `@tool` decorator inferring JSON schemas from
  signatures + docstrings is excellent; the agent's tool loop (tool_use →
  execute → toolResult → model) worked exactly as documented, including
  multi-turn approval flows. `BedrockModel` config (model id, region) is
  straightforward.
- **What needs work:**
  1. No "authoring a custom Model" quickstart — I derived the
     `messageStart → contentBlockStart → contentBlockDelta → messageStop`
     event shapes from `llamacpp.py` source. A 40-line echo-model example
     would make eval/offline patterns first-class.
  2. `Model` has four abstract methods (`stream`, `structured_output`,
     `get_config`, `update_config`) but nothing tells you that until
     instantiation fails; a checklist in the custom-model docs would help.
- **Onboarding experience:** 7/10. Core path is smooth; the edges are
  learn-by-reading-source.
- **Would use again?** Yes — it's the fastest credible agent loop on AWS, and
  the Bedrock/Nova pairing is the natural choice for an Amazon-track project.

## 3. Amazon Bedrock (Nova Lite — planned production model)

- **Used for:** The production LLM behind the Strands agent
  (`us.amazon.nova-lite-v1:0`, `us-west-2`, override via `BEDROCK_MODEL_ID`).
  Offline dev/eval used the scripted model; Bedrock is the deploy target.
- **What worked well:** Model-id + region configuration in Strands is
  one line; Nova is the right cost/latency tier for a household assistant.
- **What needs work:** Near-identical model ids across docs
  (`amazon.nova-lite-v1:0` vs `us.amazon.nova-lite-v1:0` inference profile)
  fail with opaque auth/region errors. Strands could validate the id format
  early and suggest the inference-profile form when the region prefix is
  missing.
- **Onboarding experience:** 6/10 — fine once you know the inference-profile
  convention, cryptic until then.
- **Would use again?** Yes, with the env-overridable model id pattern.

## 4. Alexa+ track (simulated-experience path)

- **Used for:** Primary track. The "simulated Alexa+ experience" web app is
  the demo surface; the MCP server + Agent Skill manifest are the technical
  integration.
- **What worked well:** Explicitly allowing a simulated web app (exempt from
  the runtime-tech requirement) made the track accessible without Alexa
  hardware; combining it with a real MCP server gave both demo richness and
  technical depth.
- **What needs work:** No published definition of what counts as a valid
  simulation — required disclaimers, branding do/don'ts. I labeled the UI
  "SIMULATED EXPERIENCE" and kept trademarks nominative, but I was guessing.
  A one-page guideline would raise submission quality across the track.
- **Onboarding experience:** 7/10.
- **Would use again?** Yes — highest-leverage track for developer-feedback
  value, which is clearly what Amazon wants from this hackathon.

## 5. HyperFrames + TTS (demo video pipeline)

- **Used for:** The sub-3-minute narrated demo video (composition → MP4) and
  its voiceover.
- **What worked well:** HTML-composition authoring with seekable timelines;
  `tts speak` producing consistent narration quickly.
- **What needs work:** Nothing blocking; the skill docs' lint-first guidance
  caught real issues (font embedding, clip tween rules) before render.
- **Onboarding experience:** 8/10.
- **Would use again?** Yes.
