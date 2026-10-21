# HomeOps for Alexa+ — Devpost submission text (filing-ready)

Prepared 2026-10-20 ~4:00 AM PT. Copy-paste into the Devpost form at
https://amazonappdev2026.devpost.com/. Tracks: **Alexa+** (primary).
Mini challenge: **Open Source** only.

## Project name
HomeOps for Alexa+

## Tagline
The family coordinator that knows when to ask — an Alexa+ Agent Skill backed by
a self-hosted MCP server, with human-in-the-loop approvals and a hash-chained
audit trail.

## Description (main, full text)
HomeOps is a family household coordinator built for the Alexa+ track. "Alexa,
give me the family briefing" → the skill calls HomeOps tools for the Rivera
family's calendar, chores, grocery list, and school bus times — and consequential
actions (like deleting a calendar event) pause for a human approval before they
execute. Every call lands in a hash-chained audit log; per-tool scopes enforce
least privilege.

Under the hood: a self-hosted MCP server implementing MCP spec 2025-11-25+ over
Streamable HTTP exposes 16 household tools (calendar, chores, grocery, school).
A Strands SDK agent (configured for Amazon Bedrock) plans each turn, invoked at
runtime by the live MCP client. The repo ships scenario evals on tool-calling —
briefings, approvals, denials, scope checks — with 14 checks green, plus a
simulated Alexa+ web experience with a live tool-call trace so anyone can watch
the agent work.

Trust is the differentiator: human-in-the-loop is a first-class primitive, not
a bolt-on. The simulated experience path is the explicit Alexa+ track path; the
demo web app is clearly labeled as a simulated experience.

Open source (MIT): github.com/solanaminter/alexa-homeops

## Built with
Python, MCP (Model Context Protocol), Strands SDK, Next.js, Vercel

## Try it out links
- **Live demo:** https://homeops-demo.vercel.app
- **Demo video (2:08):** https://youtu.be/Sq_Ce1QD7GE
- **Code repo:** https://github.com/solanaminter/alexa-homeops

## Team
Solana Minter (solo). Purple Castle Ventures.

## [AWAITING — his answer only]
Devpost form question: "Have you built for Amazon devices or services before?"
Leave this field until Dy answers (parked gate since 2026-10-19).

## Product feedback to paste (from PRODUCT_FEEDBACK.md)
Paste per-tool sections into the form's feedback fields; full file at
PRODUCT_FEEDBACK.md.

## Friction log
Attach/paste FRICTION_LOG.md (8 real entries — submitted for the +10% bonus).

## Filing checklist (filing window closes Oct 23, 2026, 12:00 PM PT)
- [x] Demo video public on YouTube, 2:08 (< 3:00 cap)
- [x] Live demo public, no login wall
- [x] Repo public, MIT license visible
- [x] Submission text drafted (this file)
- [x] Product feedback written
- [x] Friction log written
- [ ] His answer to the one form question above
