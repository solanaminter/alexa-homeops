"""MCP-protocol tests: tools, approvals, scopes, audit chain — all over HTTP."""

from __future__ import annotations

import asyncio
import contextvars

import pytest

from homeops.client import HomeOpsClient

_LOOP: contextvars.ContextVar[asyncio.AbstractEventLoop] = contextvars.ContextVar("client_loop")


def run(coro):
    """Run a coroutine on the shared client loop (see `client_loop` fixture)."""
    return _LOOP.get().run_until_complete(coro)


@pytest.fixture()
def client_loop():
    """One event loop per test for all MCP client I/O.

    The v2 transport/session objects are bound to the loop that entered them;
    creating a fresh loop per await (as an earlier helper did) hangs forever.
    """
    import threading
    loop = asyncio.new_event_loop()
    token = _LOOP.set(loop)
    yield loop
    _LOOP.reset(token)
    loop.close()


@pytest.fixture()
def client(server_url, client_loop):
    async def _make():
        c = HomeOpsClient(server_url)
        await c.__aenter__()
        return c
    c = run(_make())
    yield c
    try:
        run(c.__aexit__(None, None, None))
    except Exception:
        pass


def test_lists_sixteen_tools(client):
    tools = run(client.list_tools())
    names = sorted(t["name"] for t in tools)
    assert len(names) == 16, names
    assert "household_briefing" in names
    assert "approvals_decide" in names


def test_calendar_roundtrip(client):
    added = run(client.call_tool("calendar_add_event",
                                {"title": "Test event", "day": "Sunday",
                                 "time": "1:00 PM", "who": "maya"}))
    assert added["status"] == "ok"
    events = run(client.call_tool("calendar_list_events", {"day": "Sunday"}))
    assert any(e["title"] == "Test event" for e in events["events"])


def test_delete_requires_approval_then_executes(client):
    first = run(client.call_tool("calendar_delete_event", {"event_id": "evt_1"}))
    assert first["status"] == "approval_required"
    aid = first["approval_id"]

    # Cannot bypass: calling delete with a bogus approval id fails.
    bogus = run(client.call_tool(
        "calendar_delete_event", {"event_id": "evt_1", "approval_id": "apr_nope"}))
    assert bogus["status"] == "denied"

    decided = run(client.call_tool(
        "approvals_decide", {"approval_id": aid, "decision": "approve"}))
    assert decided["status"] == "ok"
    assert decided["executed"] == {"deleted_event": "evt_1"}

    events = run(client.call_tool("calendar_list_events", {}))
    assert all(e["id"] != "evt_1" for e in events["events"])


def test_deny_leaves_state_untouched(client):
    first = run(client.call_tool("calendar_delete_event", {"event_id": "evt_2"}))
    aid = first["approval_id"]
    decided = run(client.call_tool(
        "approvals_decide", {"approval_id": aid, "decision": "deny"}))
    assert decided["status"] == "ok"
    assert decided["executed"] is None
    events = run(client.call_tool("calendar_list_events", {}))
    assert any(e["id"] == "evt_2" for e in events["events"])


def test_briefing_composes_across_tools(client):
    b = run(client.call_tool("household_briefing", {"day": "Monday"}))
    assert b["status"] == "ok"
    assert "events" in b and "pending_chores" in b and "buses" in b


def test_scope_denial_on_restricted_server(restricted_server_url, client_loop):
    async def _go():
        async with HomeOpsClient(restricted_server_url) as c:
            ok = await c.call_tool("calendar_list_events", {})
            denied = await c.call_tool(
                "grocery_add_item", {"item": "Bread", "qty": "1"})
            scopes = await c.call_tool("permissions_get_scopes", {})
            return ok, denied, scopes
    ok, denied, scopes = run(_go())
    assert ok["status"] == "ok"                      # calendar:read granted
    assert denied["status"] == "denied"              # grocery:write missing
    assert "grocery:write" in denied["error"]
    assert sorted(scopes["granted"]) == ["calendar:read", "chores:read"]


def test_audit_log_hash_chain_valid(server_url, client_loop):
    async def _go():
        async with HomeOpsClient(server_url) as c:
            return await c.call_tool("audit_get_log", {"limit": 5})
    log = run(_go())
    assert log["status"] == "ok"
    assert log["chain_valid"] is True
    assert log["entries_checked"] >= 1
    assert all("entry_hash" in e and "prev_hash" in e for e in log["entries"])
