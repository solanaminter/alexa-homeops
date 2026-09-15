# HomeOps — Alexa+ Agent Skill manifest (draft)

> Pairs with the self-hosted MCP server in `src/homeops/server.py`. In the
> Alexa+ developer console this becomes the skill's interaction model + endpoint
> configuration. Included so judges can see the full Alexa+ integration story.

## Skill identity
- **Name:** HomeOps
- **Invocation:** "Alexa, ask Home Ops…" / "Alexa, open Home Ops"
- **Category:** Productivity / Family
- **Locale:** en-US

## Sample utterances → MCP tools
| Utterance | MCP tool |
|---|---|
| "Give me the family briefing" | `household_briefing` |
| "What's on the calendar {day}?" | `calendar_list_events` |
| "Add {title} to the calendar {day} at {time}" | `calendar_add_event` |
| "Delete {event} from the calendar" | `calendar_delete_event` → approval card |
| "What chores are left?" | `chores_list` |
| "Assign {chore} to {person}" | `chores_assign` |
| "{chore} is done" | `chores_complete` |
| "Add {item} to the grocery list" | `grocery_add_item` |
| "When is {kid}'s bus?" | `school_get_bus` |
| "What did you do today?" | `audit_get_log` |

## Endpoint
- **Type:** MCP server (Streamable HTTP), MCP spec 2025-11-25+
- **URL:** `https://<your-host>/mcp` (self-hosted; local demo: `http://127.0.0.1:8765/mcp`)
- **Auth:** Bearer token per household; scopes negotiated at skill-enable time
  (see `permissions_get_scopes`). Least-privilege: a "kids" profile, for
  example, grants only `calendar:read`, `chores:read`, `school:read`.

## Human-in-the-loop
`calendar_delete_event` (and any future consequential tool) returns
`approval_required`. Alexa+ renders this as a confirmation card / voice
prompt ("Should I delete the PTA meeting?"); the skill calls
`approvals_decide` with the user's answer. Denials leave state untouched.

## Account linking
Household profile selected at enable time; the MCP server scopes all data to
that household. No per-user PII leaves the home server — the audit log is
local and hash-chained.
