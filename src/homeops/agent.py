"""HomeOps agent — Strands SDK orchestration over the HomeOps MCP server.

Production path: ``build_agent()`` wires a Strands ``Agent`` to Amazon Bedrock
(``BedrockModel``) with 16 tools. Every tool invocation goes through
``call_mcp_sync`` → the MCP client → the HomeOps MCP server over Streamable
HTTP, so the Alexa+ track tech is genuinely invoked at runtime.

Offline path: ``ScriptedModel`` is a deterministic stand-in for the LLM used
by evals and the web demo when no Bedrock credentials are available. The tool
execution path is identical — only the model is swapped.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from typing import Any

from strands import Agent
from strands.models import BedrockModel
from strands.models.model import Model
from strands.tools import tool

from .client import DEFAULT_URL, connect

# ---------------------------------------------------------------------------
# Sync bridge: Strands tools are sync, the MCP client is async.
# ---------------------------------------------------------------------------

_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_thread
    if _loop is None:
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True,
                                        name="homeops-mcp-loop")
        _loop_thread.start()
    return _loop


def call_mcp_sync(name: str, args: dict, url: str = DEFAULT_URL) -> dict:
    """Call an MCP tool synchronously (safe from any thread)."""
    async def _go():
        async with connect(url) as client:
            return await client.call_tool(name, args)

    future = asyncio.run_coroutine_threadsafe(_go(), _ensure_loop())
    try:
        return future.result(timeout=30)
    except Exception as e:  # transport errors become tool errors, not crashes
        return {"status": "error", "error": f"MCP transport error: {e}"}


MCP_URL = os.environ.get("HOMEOPS_MCP_URL", DEFAULT_URL)


def _call(name: str, args: dict) -> dict:
    t0 = time.time()
    result = call_mcp_sync(name, args, MCP_URL)
    entry: dict = {"tool": name, "args": args,
                   "duration_ms": round((time.time() - t0) * 1000, 1),
                   "ts": time.time()}
    if isinstance(result, dict):
        entry["result_status"] = str(result.get("status", "ok"))
        if result.get("status") == "approval_required":
            entry["approval_id"] = result.get("approval_id")
            entry["reason"] = result.get("reason")
    TRACE.append(entry)
    return result


TRACE: list[dict] = []  # per-turn spans; reset with new_turn()


def new_turn() -> None:
    TRACE.clear()


# ---------------------------------------------------------------------------
# Strands tools — one per MCP tool. Signatures become the tool schemas.
# ---------------------------------------------------------------------------

@tool
def calendar_list_events(day: str = "") -> dict:
    """List family calendar events. Args: day (optional day of week, e.g. 'Monday')."""
    return _call("calendar_list_events", {"day": day})


@tool
def calendar_add_event(title: str, day: str, time: str, who: str = "") -> dict:
    """Add a family calendar event. Args: title, day, time, who (family member id)."""
    return _call("calendar_add_event", {"title": title, "day": day, "time": time, "who": who})


@tool
def calendar_delete_event(event_id: str, approval_id: str = "") -> dict:
    """Delete a calendar event. Consequential: first call returns approval_required;
    after the human approves via approvals_decide, the deletion executes."""
    return _call("calendar_delete_event", {"event_id": event_id, "approval_id": approval_id})


@tool
def chores_list(status: str = "") -> dict:
    """List household chores. Args: status filter ('pending', 'done', 'unassigned')."""
    return _call("chores_list", {"status": status})


@tool
def chores_assign(chore_id: str, assignee: str) -> dict:
    """Assign a chore to a family member id (maya, daniel, sofia, mateo)."""
    return _call("chores_assign", {"chore_id": chore_id, "assignee": assignee})


@tool
def chores_complete(chore_id: str) -> dict:
    """Mark a chore complete by id."""
    return _call("chores_complete", {"chore_id": chore_id})


@tool
def grocery_list() -> dict:
    """List items on the family grocery list."""
    return _call("grocery_list", {})


@tool
def grocery_add_item(item: str, qty: str = "1", added_by: str = "alexa") -> dict:
    """Add an item to the grocery list."""
    return _call("grocery_add_item", {"item": item, "qty": qty, "added_by": added_by})


@tool
def grocery_remove_item(item_id: str) -> dict:
    """Remove a grocery item by id."""
    return _call("grocery_remove_item", {"item_id": item_id})


@tool
def school_get_schedule(kid: str, day: str = "Monday") -> dict:
    """Get a kid's class schedule. Args: kid ('sofia'|'mateo'), day."""
    return _call("school_get_schedule", {"kid": kid, "day": day})


@tool
def school_get_bus(kid: str) -> dict:
    """Get a kid's bus route and pickup/dropoff times."""
    return _call("school_get_bus", {"kid": kid})


@tool
def household_briefing(day: str = "Monday") -> dict:
    """Proactive morning briefing: events, open chores, grocery count, bus times."""
    return _call("household_briefing", {"day": day})


@tool
def approvals_list_pending() -> dict:
    """List pending human-approval requests."""
    return _call("approvals_list_pending", {})


@tool
def approvals_decide(approval_id: str, decision: str, decided_by: str = "user") -> dict:
    """Approve ('approve') or deny ('deny') a pending request by id. Approving
    executes the gated action."""
    return _call("approvals_decide", {"approval_id": approval_id,
                                      "decision": decision, "decided_by": decided_by})


@tool
def audit_get_log(limit: int = 20) -> dict:
    """Read the immutable audit log and verify its hash chain."""
    return _call("audit_get_log", {"limit": limit})


@tool
def permissions_get_scopes() -> dict:
    """Show granted scopes and the scope each tool requires."""
    return _call("permissions_get_scopes", {})


ALL_TOOLS = [calendar_list_events, calendar_add_event, calendar_delete_event,
             chores_list, chores_assign, chores_complete, grocery_list,
             grocery_add_item, grocery_remove_item, school_get_schedule,
             school_get_bus, household_briefing, approvals_list_pending,
             approvals_decide, audit_get_log, permissions_get_scopes]

SYSTEM_PROMPT = """You are HomeOps, the Rivera family's Alexa+ household coordinator.
You manage the family calendar, chores, grocery list, and school schedules
through your tools. Rules:
- Answer concisely, in a warm voice-assistant tone.
- For consequential actions (calendar_delete_event), the tool returns
  approval_required: explain what needs approval and wait. Never invent an
  approval or call with a fabricated approval_id.
- If a tool returns status 'denied' (missing scope), explain the permission gap
  plainly and suggest what to enable.
- Use audit_get_log when asked what you did.
- Today's briefing day defaults to Monday unless the user says otherwise."""


def build_agent(model: Model | None = None, system_prompt: str = SYSTEM_PROMPT) -> Agent:
    """Build the production agent: Strands + Amazon Bedrock (Nova)."""
    if model is None:
        model = BedrockModel(
            model_id=os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0"),
            region_name=os.environ.get("AWS_REGION", "us-west-2"),
        )
    return Agent(model=model, system_prompt=system_prompt, tools=ALL_TOOLS)


# ---------------------------------------------------------------------------
# ScriptedModel — deterministic offline model for evals + web demo.
# ---------------------------------------------------------------------------

def _last_text_user_index(messages: list) -> int:
    idx = -1
    for i, m in enumerate(messages):
        if m.get("role") == "user" and any(
                isinstance(b, dict) and "text" in b for b in m.get("content", [])):
            idx = i
    return idx


def _has_tool_results_since(messages: list, idx: int) -> bool:
    for m in messages[idx + 1:]:
        for b in m.get("content", []):
            if isinstance(b, dict) and "toolResult" in b:
                return True
    return False


def _last_approval_request(messages: list) -> dict | None:
    """Find the most recent approval_required tool result."""
    for m in reversed(messages):
        for b in m.get("content", []):
            if isinstance(b, dict) and "toolResult" in b:
                for c in b["toolResult"].get("content", []):
                    txt = c.get("text", "") if isinstance(c, dict) else ""
                    try:
                        data = json.loads(txt)
                    except ValueError:
                        continue
                    if isinstance(data, dict) and data.get("status") == "approval_required":
                        return data
    return None


def route_demo(text: str, messages: list) -> tuple[list[tuple[str, dict]], str]:
    """Deterministic intent router → (tool_calls, final_text)."""
    t = text.lower()

    # Approval follow-ups: user says yes/no after an approval request.
    if any(w in t for w in ("approve", "yes", "go ahead", "do it", "confirm")):
        pending = _last_approval_request(messages)
        if pending and not any(w in t for w in ("don't", "cancel", "deny", "no ")):
            aid = pending["approval_id"]
            return ([("approvals_decide",
                       {"approval_id": aid, "decision": "approve", "decided_by": "user"})],
                    "Done — approved and executed. Anything else?")
        if "deny" in t or "don't" in t or "cancel" in t:
            pending = _last_approval_request(messages)
            if pending:
                aid = pending["approval_id"]
                return ([("approvals_decide",
                           {"approval_id": aid, "decision": "deny", "decided_by": "user"})],
                        "Understood — I cancelled that. Nothing was changed.")
    if any(w in t for w in ("deny", "don't", "cancel", "never mind")):
        pending = _last_approval_request(messages)
        if pending:
            aid = pending["approval_id"]
            return ([("approvals_decide",
                       {"approval_id": aid, "decision": "deny", "decided_by": "user"})],
                    "Understood — I cancelled that. Nothing was changed.")

    if any(w in t for w in ("briefing", "good morning", "morning rundown", "my day")):
        return ([("household_briefing", {"day": "Monday"})],
                "Here's the family briefing. Anything else?")
    if "delete" in t and ("event" in t or "meeting" in t or "calendar" in t):
        # demo maps to the PTA meeting
        return ([("calendar_delete_event", {"event_id": "evt_3", "approval_id": ""})],
                "That needs your approval first — I've put in the request.")
    if "grocery" in t and any(w in t for w in ("add", "need", "get some", "buy")):
        item = "Oat milk"
        for cand in ("oat milk", "bread", "cheese", "yogurt", "bananas"):
            if cand in t:
                item = cand.title()
                break
        return ([("grocery_add_item", {"item": item, "qty": "1", "added_by": "alexa"})],
                f"Added {item} to the grocery list.")
    if "grocery" in t or "shopping list" in t:
        return ([("grocery_list", {})], "Here's the grocery list.")
    if "assign" in t and any(w in t for w in
            ("chore", "laundry", "dishes", "trash", "task")):
        who = next((k for k in ("sofia", "mateo", "maya", "daniel") if k in t), "mateo")
        return ([("chores_assign", {"chore_id": "ch_3", "assignee": who})],
                f"Assigned the laundry to {who.title()}.")
    if "chore" in t and ("done" in t or "complete" in t or "finished" in t):
        return ([("chores_complete", {"chore_id": "ch_1"})],
                "Marked the dishwasher chore complete. Nice work.")
    if "chore" in t:
        return ([("chores_list", {"status": ""})], "Here are the household chores.")
    if "bus" in t:
        kid = "sofia" if "sofia" in t else "mateo"
        return ([("school_get_bus", {"kid": kid})],
                f"Here's {kid.title()}'s bus info.")
    if "school" in t or "class" in t or "schedule" in t:
        kid = "sofia" if "sofia" in t else "mateo"
        return ([("school_get_schedule", {"kid": kid, "day": "Monday"})],
                f"Here's {kid.title()}'s schedule for Monday.")
    if "calendar" in t or "event" in t or "meeting" in t:
        return ([("calendar_list_events", {"day": ""})], "Here's the family calendar.")
    if "add" in t and ("event" in t or "calendar" in t or "dentist" in t or "appointment" in t):
        return ([("calendar_add_event",
                   {"title": "Dentist — checkup", "day": "Thursday",
                    "time": "4:00 PM", "who": "sofia"})],
                "Added it to the calendar.")
    if "audit" in t or "what did you do" in t or "log" in t:
        return ([("audit_get_log", {"limit": 10})],
                "Here's the recent audit log — every action is recorded.")
    if "permission" in t or "scope" in t:
        return ([("permissions_get_scopes", {})],
                "Here are the skill's granted scopes.")
    return ([], "I can help with the family calendar, chores, grocery list, "
                "school schedules, and the morning briefing. What do you need?")


class ScriptedModel(Model):
    """Deterministic stand-in LLM: routes via route_demo, yields real stream events."""

    def __init__(self):
        self._config: dict[str, Any] = {}

    def get_config(self) -> dict[str, Any]:
        return dict(self._config)

    def update_config(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError("ScriptedModel does not support structured output")
        yield  # pragma: no cover - makes this an async generator

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        # Only treat tool results as "already answered" when they came after the
        # latest real user utterance (multi-turn safe).
        last_user = _last_text_user_index(messages)
        user_text = ""
        if last_user >= 0:
            user_text = " ".join(
                b.get("text", "") for b in messages[last_user].get("content", [])
                if isinstance(b, dict) and "text" in b)
        tool_calls, final_text = route_demo(user_text, messages)
        if _has_tool_results_since(messages, last_user) or not tool_calls:
            # Final text turn. If a tool result needs approval, surface it.
            pending = _last_approval_request(messages)
            if pending and not tool_calls:
                text = (f"That action needs your approval: {pending['reason']} "
                        "Say approve or deny.")
            else:
                text = final_text
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": text}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            return
        # Tool-use turn
        yield {"messageStart": {"role": "assistant"}}
        for name, args in tool_calls:
            tid = "toolu_" + uuid.uuid4().hex[:8]
            yield {"contentBlockStart": {"start": {"toolUse": {
                "name": name, "toolUseId": tid}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {
                "input": json.dumps(args)}}}}
            yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}


def build_demo_agent() -> Agent:
    """Offline demo agent: identical tools + MCP path, scripted model."""
    return build_agent(model=ScriptedModel())
