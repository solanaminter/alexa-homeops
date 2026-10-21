# HomeOps for Alexa+ 🏠

**Live Demo:** https://homeops-demo.vercel.app

**Demo Video:** https://youtu.be/Sq_Ce1QD7GE

**Family household coordinator for Alexa+** — an Alexa+ Agent Skill backed by a
self-hosted **MCP server** (MCP spec 2025-11-25+, Streamable HTTP), orchestrated
by a **Strands SDK agent on Amazon Bedrock**.

Built for the [Amazon Build/Ship/Shape Developer Hackathon](https://amazonappdev2026.devpost.com/)
(Alexa+ track + Open Source mini challenge).

> "Alexa, give me the family briefing" → the skill calls HomeOps tools for the
> calendar, chores, grocery list, and school bus times — consequential actions
> pause for a human approval, and every call lands in a hash-chained audit log.

## Demo (2:08 video)

📺 *Demo video: `assets/homeops-demo.mp4` (also on YouTube: https://youtu.be/Sq_Ce1QD7GE)*

The video walks through: the problem → a live simulated Alexa+ session
(briefing, grocery add, bus times, **approval-gated calendar delete**) →
the AWS/Strands layer → system architecture → impact.

## Live demo (Vercel)

The simulated Alexa+ web experience deploys as a static site + lightweight
serverless demo APIs (`web/`):

```bash
cd web && vercel deploy
```

(`vercel build` from `web/` validates the deploy locally — do not run
`vercel deploy` yourself; the parent deploys and fills in the **Live Demo**
URL at the top of this README.)

Backend honesty: the production backend is a self-hosted Python MCP server
(Streamable HTTP, persistent process) orchestrated by a Strands agent — it
can't run on plain static hosting. The deployed site's `/api/*` endpoints are
serverless functions (`web/api/`) that re-implement the **offline demo path**:
the same deterministic intent router and 16-tool semantics as `src/homeops/`,
over the real bundled seed data (`web/data/household.json`, copied from
`sample_data/household.json`). State is per-instance and resets on cold start;
"Reset demo state" reseeds. The full-fidelity backend runs locally (below).

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 1. Start the MCP server (Streamable HTTP, :8765/mcp)
python -m homeops.server

# 2. Start the demo web UI (simulated Alexa+ experience, :8080)
python web/bridge.py
# → open http://127.0.0.1:8080
```

Try: *"Good morning, give me the family briefing"* → *"Delete the PTA meeting
from the calendar"* (watch the approval gate) → approve or deny it.

Run the tests + evals:

```bash
pytest -q                 # spins up real MCP servers; 14 checks
python -m homeops.evals   # scenario evals against a live server
```

## Architecture

```
┌──────────────┐   voice/text    ┌─────────────────────────┐
│  Alexa+ Skill │ ─────────────▶ │ Strands Agent (Bedrock-  │  Strands SDK agent,
│  (utterances) │                │  configured)            │  Bedrock-configured
└──────────────┘                └────────────┬────────────┘
                                             │ Streamable HTTP (MCP 2025-11-25+)
                              ┌──────────────▼────────────┐
                              │   HomeOps MCP server      │  16 tools · per-tool
                              │   :8765/mcp               │  scopes · approvals
                              └──────────────┬────────────┘
                          ┌──────────────────┼──────────────────┐
                          ▼                  ▼                  ▼
                    household JSON   hash-chained audit   approval queue
```

- **`src/homeops/server.py`** — MCP server (`MCPServer`, Streamable HTTP).
  16 tools across calendar, chores, grocery, school, briefing, approvals,
  audit, permissions.
- **`src/homeops/agent.py`** — Strands agent. Production: `BedrockModel`
  (`BEDROCK_MODEL_ID`, default `us.amazon.nova-lite-v1:0`). Offline/demo:
  `ScriptedModel` — identical tool path, scripted LLM (clearly labeled).
- **`src/homeops/store.py`** — JSON state, append-only SHA-256-chained audit
  log (`verify_chain()`), approval queue, per-tool scope enforcement
  (`HOMEOPS_SCOPES` for least-privilege).
- **`src/homeops/evals.py`** — 6 scenario evals on tool-calling (incl. the
  approval and scope-denial flows) + audit-chain integrity.
- **`web/`** — simulated Alexa+ experience: chat UI, live MCP tool-call
  trace, approval cards, audit viewer.
- **`alexa-skill/SKILL.md`** — skill manifest: utterances → tools, endpoint,
  approval UX, account linking.

### Trust & safety design (2026 themes)
- **Scoped permissions per tool** — each tool declares required scopes;
  `HOMEOPS_SCOPES` grants least-privilege; denials are explicit, not silent.
- **Human-in-the-loop** — consequential actions return `approval_required`
  and only execute via `approvals_decide`. Denials leave state untouched
  (covered by evals).
- **Immutable audit log** — every call appended with a hash chain;
  `audit_get_log` verifies it on read.
- **Observability** — per-turn spans (tool, args, ms, result) feed the web UI
  trace panel.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `HOMEOPS_PORT` | `8765` | MCP server port |
| `HOMEOPS_DATA_DIR` | `./data` | state/audit/approvals dir |
| `HOMEOPS_SCOPES` | *(all)* | comma-separated granted scopes |
| `HOMEOPS_MCP_URL` | `http://127.0.0.1:8765/mcp` | server URL for agent/client |
| `BEDROCK_MODEL_ID` | `us.amazon.nova-lite-v1:0` | Bedrock model for production agent |
| `AWS_REGION` | `us-west-2` | Bedrock region |
| `HOMEOPS_WEB_PORT` | `8080` | demo UI port |

## Product feedback & friction log
- [`PRODUCT_FEEDBACK.md`](PRODUCT_FEEDBACK.md) — per-tool/SDK feedback for the
  Devpost form (MCP SDK, Strands, Bedrock, …).
- [`FRICTION_LOG.md`](FRICTION_LOG.md) — real build friction, kept live.

## License
MIT — Copyright (c) 2026 Solana Minter. See [LICENSE](LICENSE).
