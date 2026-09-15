"""HomeOps MCP server — MCP spec 2025-11-25+, Streamable HTTP transport.

Exposes the household tools an Alexa+ Agent Skill calls at runtime. Every tool
call is scope-checked (least-privilege per tool) and appended to the
hash-chained audit log. Consequential actions (event deletion) require a
human-in-the-loop approval before they execute.

Run:
    python -m homeops.server            # Streamable HTTP on :8765/mcp
    HOMEOPS_DATA_DIR=./data HOMEOPS_SCOPES=calendar:read python -m homeops.server
"""

from __future__ import annotations

import functools
import os
import time
import uuid

from mcp.server.mcpserver import MCPServer

from .store import Store, check_scopes, granted_scopes

mcp = MCPServer("homeops")
store = Store()


def _tool(name: str):
    """Register a tool with scope enforcement + audit logging."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(**kwargs):
            ok, missing = check_scopes(name)
            if not ok:
                store.audit(name, kwargs,
                            f"DENIED — missing scopes: {missing}",
                            sorted(granted_scopes()))
                return {
                    "status": "denied",
                    "error": f"Missing required scopes for {name}: {missing}. "
                             f"Granted: {sorted(granted_scopes())}",
                }
            result = fn(**kwargs)
            summary = str(result.get("status", "ok")) if isinstance(result, dict) else "ok"
            store.audit(name, kwargs, summary, sorted(granted_scopes()),
                        approval_id=result.get("approval_id") if isinstance(result, dict) else None)
            return result

        wrapper.__name__ = name
        return mcp.tool(name=name)(wrapper)
    return deco


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

@_tool("calendar_list_events")
def calendar_list_events(day: str = "") -> dict:
    """List family calendar events, optionally filtered by day of week."""
    events = store.load()["calendar"]
    if day:
        events = [e for e in events if e["day"].lower() == day.lower()]
    return {"status": "ok", "events": events}


@_tool("calendar_add_event")
def calendar_add_event(title: str, day: str, time: str, who: str = "") -> dict:
    """Add a family calendar event."""
    event = {"id": "evt_" + uuid.uuid4().hex[:6], "title": title,
             "day": day, "time": time, "who": who}

    def _add(state):
        state["calendar"].append(event)

    store.mutate(_add)
    return {"status": "ok", "event": event}


@_tool("calendar_delete_event")
def calendar_delete_event(event_id: str, approval_id: str = "") -> dict:
    """Delete a calendar event. Consequential: requires human approval first.

    Call once without approval_id to open an approval request; the user
    approves via approvals_decide; then call again with the approval_id.
    """
    if not approval_id:
        req = store.request_approval(
            "calendar_delete_event", {"event_id": event_id},
            reason=f"Deleting calendar event {event_id} is consequential and needs a human OK.",
        )
        return {"status": "approval_required", "approval_id": req["id"],
                "reason": req["reason"]}
    # Only proceed if this approval was approved via approvals_decide
    approvals = store._load_approvals()
    item = approvals["pending"].get(approval_id)
    if item is None or item["status"] != "approved":
        return {"status": "denied",
                "error": "No approved approval for this action.",
                "approval_id": approval_id}
    removed = {}

    def _delete(state):
        before = len(state["calendar"])
        state["calendar"] = [e for e in state["calendar"] if e["id"] != event_id]
        removed["count"] = before - len(state["calendar"])

    store.mutate(_delete)
    return {"status": "ok", "deleted": removed["count"], "approval_id": approval_id}


# ---------------------------------------------------------------------------
# Chores
# ---------------------------------------------------------------------------

@_tool("chores_list")
def chores_list(status: str = "") -> dict:
    """List household chores, optionally filtered by status."""
    chores = store.load()["chores"]
    if status:
        chores = [c for c in chores if c["status"] == status]
    return {"status": "ok", "chores": chores}


@_tool("chores_assign")
def chores_assign(chore_id: str, assignee: str) -> dict:
    """Assign a chore to a family member."""
    members = [m["id"] for m in store.load()["household"]["members"]]
    if assignee not in members:
        return {"status": "error", "error": f"Unknown member '{assignee}'. Known: {members}"}
    found = {}

    def _assign(state):
        for c in state["chores"]:
            if c["id"] == chore_id:
                c["assignee"] = assignee
                c["status"] = "pending"
                found["task"] = c["task"]

    store.mutate(_assign)
    if not found:
        return {"status": "error", "error": f"Unknown chore '{chore_id}'"}
    return {"status": "ok", "chore_id": chore_id, "assignee": assignee, "task": found["task"]}


@_tool("chores_complete")
def chores_complete(chore_id: str) -> dict:
    """Mark a chore complete."""
    found = {}

    def _complete(state):
        for c in state["chores"]:
            if c["id"] == chore_id:
                c["status"] = "done"
                found["task"] = c["task"]

    store.mutate(_complete)
    if not found:
        return {"status": "error", "error": f"Unknown chore '{chore_id}'"}
    return {"status": "ok", "chore_id": chore_id, "task": found["task"]}


# ---------------------------------------------------------------------------
# Grocery
# ---------------------------------------------------------------------------

@_tool("grocery_list")
def grocery_list() -> dict:
    """List items on the family grocery list."""
    return {"status": "ok", "items": store.load()["grocery"]}


@_tool("grocery_add_item")
def grocery_add_item(item: str, qty: str = "1", added_by: str = "alexa") -> dict:
    """Add an item to the grocery list."""
    entry = {"id": "g_" + uuid.uuid4().hex[:6], "item": item,
             "qty": qty, "added_by": added_by}

    def _add(state):
        state["grocery"].append(entry)

    store.mutate(_add)
    return {"status": "ok", "entry": entry}


@_tool("grocery_remove_item")
def grocery_remove_item(item_id: str) -> dict:
    """Remove an item from the grocery list by id."""
    removed = {}

    def _remove(state):
        before = len(state["grocery"])
        state["grocery"] = [g for g in state["grocery"] if g["id"] != item_id]
        removed["count"] = before - len(state["grocery"])

    store.mutate(_remove)
    return {"status": "ok", "removed": removed["count"]}


# ---------------------------------------------------------------------------
# School
# ---------------------------------------------------------------------------

@_tool("school_get_schedule")
def school_get_schedule(kid: str, day: str = "Monday") -> dict:
    """Get a kid's class schedule for a day."""
    school = store.load()["school"].get(kid.lower())
    if not school:
        return {"status": "error", "error": f"Unknown kid '{kid}'"}
    periods = next((d["periods"] for d in school["schedule"]
                    if d["day"].lower() == day.lower()), [])
    return {"status": "ok", "kid": kid, "school": school["school"],
            "day": day, "periods": periods}


@_tool("school_get_bus")
def school_get_bus(kid: str) -> dict:
    """Get a kid's bus route and pickup/dropoff times."""
    school = store.load()["school"].get(kid.lower())
    if not school:
        return {"status": "error", "error": f"Unknown kid '{kid}'"}
    return {"status": "ok", "kid": kid, **school["bus"]}


# ---------------------------------------------------------------------------
# Briefing / approvals / audit / permissions
# ---------------------------------------------------------------------------

@_tool("household_briefing")
def household_briefing(day: str = "Monday") -> dict:
    """Proactive household briefing: today's events, pending chores, grocery count, bus times."""
    state = store.load()
    events = [e for e in state["calendar"] if e["day"].lower() == day.lower()]
    pending = [c for c in state["chores"] if c["status"] != "done"]
    buses = {kid: info["bus"] for kid, info in state["school"].items()}
    lines = [
        f"Good morning, Rivera family — here's {day}:",
        f"{len(events)} event(s) on the calendar.",
        f"{len(pending)} chore(s) still open.",
        f"{len(state['grocery'])} item(s) on the grocery list.",
    ]
    return {"status": "ok", "summary": " ".join(lines), "events": events,
            "pending_chores": pending,
            "grocery_count": len(state["grocery"]), "buses": buses}


@_tool("approvals_list_pending")
def approvals_list_pending() -> dict:
    """List pending human-approval requests."""
    return {"status": "ok", "pending": store.list_pending()}


@_tool("approvals_decide")
def approvals_decide(approval_id: str, decision: str, decided_by: str = "user") -> dict:
    """Approve or deny a pending request. Approving executes the gated action."""
    if decision not in ("approve", "deny"):
        return {"status": "error", "error": "decision must be 'approve' or 'deny'"}
    item = store.decide(approval_id, decision, decided_by)
    if item is None:
        return {"status": "error", "error": f"Unknown or settled approval '{approval_id}'"}
    executed = None
    if decision == "approve":
        # Execute the gated action now that a human said yes.
        if item["tool"] == "calendar_delete_event":
            event_id = item["args"]["event_id"]

            def _delete(state):
                state["calendar"] = [e for e in state["calendar"] if e["id"] != event_id]

            store.mutate(_delete)
            executed = {"deleted_event": event_id}
    return {"status": "ok", "approval_id": approval_id,
            "decision": decision, "executed": executed}


@_tool("audit_get_log")
def audit_get_log(limit: int = 20) -> dict:
    """Read the immutable audit log (most recent entries)."""
    ok, checked = store.verify_chain()
    return {"status": "ok", "chain_valid": ok, "entries_checked": checked,
            "entries": store.get_audit(limit)}


@_tool("permissions_get_scopes")
def permissions_get_scopes() -> dict:
    """Show which scopes this skill was granted and what each tool needs."""
    from .store import TOOL_SCOPES
    return {"status": "ok", "granted": sorted(granted_scopes()),
            "tool_scopes": TOOL_SCOPES}


def main() -> None:
    import uvicorn
    host = os.environ.get("HOMEOPS_HOST", "127.0.0.1")
    port = int(os.environ.get("HOMEOPS_PORT", "8765"))
    app = mcp.streamable_http_app()
    print(f"HomeOps MCP server on http://{host}:{port}/mcp "
          f"(protocol {__import__('mcp.types', fromlist=['LATEST_PROTOCOL_VERSION']).LATEST_PROTOCOL_VERSION})")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
