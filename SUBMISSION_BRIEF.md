# SUBMISSION BRIEF — HomeOps for Alexa+

## (a) Rules, criteria, track, mini challenges

- **Hackathon:** Amazon Build / Ship / Shape Developer Hackathon
  (https://amazonappdev2026.devpost.com/) — fully online.
- **Deadline:** Oct 23, 2026, 12:00 PM PT.
- **Primary track:** **Alexa+** — self-hosted MCP server implementing MCP spec
  2025-11-25+ over Streamable HTTP (protocol 2026-07-28 negotiated) **plus** a
  simulated Alexa+ experience web app (explicitly allowed path, exempt from the
  runtime-tech requirement) **plus** an Alexa+ Agent Skill manifest.
- **Mini challenges entered:**
  - **AWS Builder** — Strands SDK agent orchestrated on Amazon Bedrock
    (Nova); documented integration in README + code.
  - **Open Source** — this repo itself is the new OSS project (MIT).
- **Judging criteria mapping:**
  - *Tech Implementation* — real MCP server + client over Streamable HTTP,
    invoked at runtime by the Strands agent (import + invocation, verified by
    `test_agent_actually_invokes_mcp_track_tech`); Bedrock model config.
  - *Design* — coherent product: chat UI, live tool-call trace, approval
    cards, audit viewer, skill manifest.
  - *Potential Impact* — household coordination is a real Alexa+ use case;
    trust design (scopes, approvals, audit) is the differentiator.
  - *Quality of the Idea* — "the family coordinator that knows when to ask":
    human-in-the-loop as a first-class primitive, not a bolt-on.
- **Friction log:** `FRICTION_LOG.md` (8 real entries) — submitted for the
  +10% judging bonus.

## (b) Repo

- **Local path:** `~/workspace/hackathons/amazon-dev-hackathon/homeops/`
- **Suggested public name:** `alexa-homeops`
- **License:** MIT, Copyright (c) 2026 Solana Minter (LICENSE at root, visible).
- **Live demo:** `web/` deploys to Vercel (`cd web && vercel deploy` —
  parent only); demo video bundled at `web/homeops-demo.mp4`; demo APIs at
  `web/api/` re-implement the offline demo path over bundled seed data
  (production backend = self-hosted Python MCP server, documented in README).
- **Do NOT push yet** — parent handles GitHub creation + push + YouTube upload
  + Devpost submission + Vercel deploy.

## (c) Demo video

- **Local path:** `~/workspace/hackathons/amazon-dev-hackathon/homeops/assets/homeops-demo.mp4`
  (render with `cd video && npm run render`, then copy the MP4 to `assets/`).
- **Duration:** ~2:07 (under the 3:00 limit).
- **Proposed YouTube title:** `HomeOps for Alexa+ — the family coordinator that knows when to ask (Amazon Build/Ship/Shape hackathon)`
- **Proposed YouTube description:**
  > HomeOps is a family household coordinator built for the Alexa+ track of the
  > Amazon Build/Ship/Shape Developer Hackathon. An Alexa+ agent skill backed by
  > a self-hosted MCP server (MCP spec 2025-11-25+, Streamable HTTP) with 16
  > household tools — calendar, chores, grocery, school — orchestrated by a
  > Strands SDK agent on Amazon Bedrock. Consequential actions pause for human
  > approval; every call lands in a hash-chained audit log; per-tool scopes
  > enforce least privilege. Open source (MIT): github.com/solanaminter/alexa-homeops
- **Tags:** alexa plus, amazon hackathon, mcp, model context protocol, strands sdk, amazon bedrock, smart home, voice assistant, open source

## (d) Devpost form fields (filled answers)

- **Project name:** HomeOps for Alexa+
- **Tagline:** The family coordinator that knows when to ask — an Alexa+ skill
  backed by a self-hosted MCP server, orchestrated with Strands on Bedrock.
- **Description (short):** HomeOps coordinates the Rivera family's calendar,
  chores, grocery list, and school schedules through 16 MCP tools exposed over
  Streamable HTTP. A Strands agent on Amazon Bedrock plans each turn; per-tool
  scopes enforce least privilege; consequential actions (like deleting a
  calendar event) pause for human approval; every call is written to a
  hash-chained audit log. The repo ships scenario evals on tool-calling
  (briefings, approvals, denials, scope checks — 14 tests green) and a
  simulated Alexa+ web experience with a live tool-call trace.
- **Tracks:** Alexa+ (primary).
- **Mini challenges:** Open Source only (AWS Builder dropped — needs a real
  AWS runtime integration; credits form closed Oct 7).
- **Video URL:** https://youtu.be/Sq_Ce1QD7GE (uploaded 2026-10-20, Public, 2:08, processed + copyright clean; title trimmed to YouTube's 100-char limit: "HomeOps for Alexa+ — the family coordinator that knows when to ask (Amazon hackathon)")
- **Live demo URL:** https://homeops-demo.vercel.app
- **Code repo URL:** *(parent pastes GitHub URL after push)*
- **Product feedback:** see `PRODUCT_FEEDBACK.md` — paste per-tool sections
  into the form's feedback fields.
- **Feature requests:**
  1. Alexa+ developer console: publish the "simulated experience" guideline
     (branding do/don'ts, required disclaimers).
  2. MCP SDK: `create_mcp_http_client()` should survive proxy env vars with
     IPv6 `NO_PROXY` literals; document client event-loop affinity.
  3. Strands: ship a 40-line custom-`Model` (echo model) example for eval/offline use.
  4. Bedrock/Strands: validate `model_id` format early and suggest the
     inference-profile form when the region prefix is missing.
- **Friction logs:** attach/paste `FRICTION_LOG.md`.

## (e) Unverified / incomplete

- [ ] Bedrock path not exercised against real AWS (no credentials in build
      env); production agent code is written and configured, offline
      `ScriptedModel` covers evals/demo. Recommend a live Bedrock smoke test
      before submission if the $150 credits are claimed.
- [ ] YouTube upload + Devpost submission are the parent's (per campaign rules).
- [x] Final MP4 rendered and copied to `assets/homeops-demo.mp4` (verified 2026-10-19: 127s / 2:07, under the 3:00 cap; identical to `video/renders/video_2026-09-14_23-42-55.mp4`).
- [ ] The Devpost "simulated experience" rules were not published; the UI is
      conservatively labeled "SIMULATED EXPERIENCE".

## (f) AWS credits flag — CLOSED

⚠️ **Update 2026-10-19 (verified on amazonappdev2026.devpost.com/resources):
"October 7th Update: Unfortunately, we are out of credit codes and are no
longer accepting credit requests."** The $150 promotional-credits Google Form
is dead — 12 days before the brief's Oct 21 assumption. The live-Bedrock-smoke-test
path now depends on (a) a Bedrock quota increase (denied Sep 28; next billing
cycle has since turned, so re-apply is retryable — needs his AWS creds/console),
or (b) his standing budget decision on AWS spend. The Alexa+ track itself is
exempt from the runtime-tech requirement (simulated experience is the explicit
path), so filing is still viable; the AWS Builder mini-challenge needs a real,
documented AWS integration of some kind before filing.
