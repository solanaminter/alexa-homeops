/**
 * HomeOps demo backend for the Vercel serverless deployment.
 *
 * HONESTY NOTE: the production backend is a self-hosted Python MCP server
 * (Streamable HTTP, persistent process) orchestrated by a Strands agent — it
 * cannot run as plain serverless hosting. This module is a faithful
 * JavaScript re-implementation of the *offline demo path* (the same
 * ScriptedModel router and the same 16-tool semantics as src/homeops/),
 * operating on the real bundled seed data (../data/household.json, copied
 * from the repo's sample_data/household.json).
 *
 * State is kept in module scope (warm serverless instance), so the demo
 * session — including the approval gate round-trip — works end to end.
 * It resets on cold start; use /api/reset to reseed on demand. The audit
 * log is a real SHA-256 hash chain, exactly like the Python store.
 */

"use strict";

const crypto = require("crypto");

function deepClone(o) {
  return JSON.parse(JSON.stringify(o));
}

const SEED = require("../data/household.json");

// ---------------------------------------------------------------------------
// Scopes — mirrors src/homeops/store.py TOOL_SCOPES
// ---------------------------------------------------------------------------

const TOOL_SCOPES = {
  calendar_list_events: ["calendar:read"],
  calendar_add_event: ["calendar:write"],
  calendar_delete_event: ["calendar:write"],
  chores_list: ["chores:read"],
  chores_assign: ["chores:write"],
  chores_complete: ["chores:write"],
  grocery_list: ["grocery:read"],
  grocery_add_item: ["grocery:write"],
  grocery_remove_item: ["grocery:write"],
  school_get_schedule: ["school:read"],
  school_get_bus: ["school:read"],
  household_briefing: ["briefing:read"],
  approvals_list_pending: ["approvals:read"],
  approvals_decide: ["approvals:write"],
  audit_get_log: ["audit:read"],
  permissions_get_scopes: [],
};

const ALL_SCOPES = [...new Set(Object.values(TOOL_SCOPES).flat())].sort();

function grantedScopes() {
  const raw = process.env.HOMEOPS_SCOPES;
  if (!raw) return new Set(ALL_SCOPES); // demo default: full grant
  return new Set(raw.split(",").map((s) => s.trim()).filter(Boolean));
}

// ---------------------------------------------------------------------------
// Session state (module scope = one warm serverless instance)
// ---------------------------------------------------------------------------

let state = deepClone(SEED);
let auditLog = [];
let pendingApprovals = {}; // id -> approval record
let lastPendingId = null;

function reset() {
  state = deepClone(SEED);
  auditLog = [];
  pendingApprovals = {};
  lastPendingId = null;
}

// ---------------------------------------------------------------------------
// Hash-chained audit log — mirrors src/homeops/store.py
// ---------------------------------------------------------------------------

function sha256hex(s) {
  return crypto.createHash("sha256").update(s, "utf8").digest("hex");
}

function canonicalEntry(e) {
  const { entry_hash, ...rest } = e;
  return JSON.stringify(rest, Object.keys(rest).sort());
}

function lastHash() {
  return auditLog.length ? auditLog[auditLog.length - 1].entry_hash : "GENESIS";
}

function audit(tool, args, resultSummary, scopes, approvalId) {
  const prev = lastHash();
  const entry = {
    seq: auditLog.length + 1,
    ts: Date.now() / 1000,
    tool,
    args: deepClone(args),
    result_summary: resultSummary,
    scopes: [...scopes].sort(),
    approval_id: approvalId || null,
    prev_hash: prev,
  };
  const payload = JSON.stringify(entry, Object.keys(entry).sort());
  entry.entry_hash = sha256hex(prev + payload);
  auditLog.push(entry);
  return entry;
}

function verifyChain() {
  let prev = "GENESIS";
  let checked = 0;
  for (const e of auditLog) {
    const digest = e.entry_hash;
    const payload = canonicalEntry(e);
    if (e.prev_hash !== prev) return { ok: false, checked };
    if (sha256hex(prev + payload) !== digest) return { ok: false, checked };
    prev = digest;
    checked += 1;
  }
  return { ok: true, checked };
}

function getAudit(limit) {
  return auditLog.slice(-(limit || 50));
}

// ---------------------------------------------------------------------------
// Tool implementations — mirrors src/homeops/server.py semantics
// ---------------------------------------------------------------------------

function toolCalendarListEvents({ day = "" }) {
  let events = state.calendar;
  if (day) events = events.filter((e) => e.day.toLowerCase() === day.toLowerCase());
  return { status: "ok", events };
}

function toolCalendarAddEvent({ title, day, time, who = "" }) {
  const event = {
    id: "evt_" + crypto.randomBytes(3).toString("hex"),
    title, day, time, who,
  };
  state.calendar.push(event);
  return { status: "ok", event };
}

function toolCalendarDeleteEvent({ event_id, approval_id = "" }) {
  if (!approval_id) {
    const id = "apr_" + crypto.randomBytes(4).toString("hex");
    const reason = `Deleting calendar event ${event_id} is consequential and needs a human OK.`;
    pendingApprovals[id] = {
      id, tool: "calendar_delete_event", args: { event_id }, reason,
      ts: Date.now() / 1000, status: "pending",
    };
    lastPendingId = id;
    return { status: "approval_required", approval_id: id, reason };
  }
  const item = pendingApprovals[approval_id];
  if (!item || item.status !== "approved") {
    return { status: "denied", error: "No approved approval for this action.", approval_id };
  }
  const before = state.calendar.length;
  state.calendar = state.calendar.filter((e) => e.id !== event_id);
  return { status: "ok", deleted: before - state.calendar.length, approval_id };
}

function toolChoresList({ status = "" }) {
  let chores = state.chores;
  if (status) chores = chores.filter((c) => c.status === status);
  return { status: "ok", chores };
}

function toolChoresAssign({ chore_id, assignee }) {
  const members = state.household.members.map((m) => m.id);
  if (!members.includes(assignee)) {
    return { status: "error", error: `Unknown member '${assignee}'. Known: ${members}` };
  }
  const chore = state.chores.find((c) => c.id === chore_id);
  if (!chore) return { status: "error", error: `Unknown chore '${chore_id}'` };
  chore.assignee = assignee;
  chore.status = "pending";
  return { status: "ok", chore_id, assignee, task: chore.task };
}

function toolChoresComplete({ chore_id }) {
  const chore = state.chores.find((c) => c.id === chore_id);
  if (!chore) return { status: "error", error: `Unknown chore '${chore_id}'` };
  chore.status = "done";
  return { status: "ok", chore_id, task: chore.task };
}

function toolGroceryList() {
  return { status: "ok", items: state.grocery };
}

function toolGroceryAddItem({ item, qty = "1", added_by = "alexa" }) {
  const entry = {
    id: "g_" + crypto.randomBytes(3).toString("hex"),
    item, qty, added_by,
  };
  state.grocery.push(entry);
  return { status: "ok", entry };
}

function toolGroceryRemoveItem({ item_id }) {
  const before = state.grocery.length;
  state.grocery = state.grocery.filter((g) => g.id !== item_id);
  return { status: "ok", removed: before - state.grocery.length };
}

function toolSchoolGetSchedule({ kid, day = "Monday" }) {
  const school = state.school[(kid || "").toLowerCase()];
  if (!school) return { status: "error", error: `Unknown kid '${kid}'` };
  const row = school.schedule.find((d) => d.day.toLowerCase() === day.toLowerCase());
  return { status: "ok", kid, school: school.school, day, periods: row ? row.periods : [] };
}

function toolSchoolGetBus({ kid }) {
  const school = state.school[(kid || "").toLowerCase()];
  if (!school) return { status: "error", error: `Unknown kid '${kid}'` };
  return { status: "ok", kid, ...school.bus };
}

function toolHouseholdBriefing({ day = "Monday" }) {
  const events = state.calendar.filter((e) => e.day.toLowerCase() === day.toLowerCase());
  const pending = state.chores.filter((c) => c.status !== "done");
  const buses = Object.fromEntries(
    Object.entries(state.school).map(([kid, info]) => [kid, info.bus])
  );
  const summary =
    `Good morning, Rivera family — here's ${day}: ` +
    `${events.length} event(s) on the calendar. ` +
    `${pending.length} chore(s) still open. ` +
    `${state.grocery.length} item(s) on the grocery list.`;
  return {
    status: "ok", summary, events, pending_chores: pending,
    grocery_count: state.grocery.length, buses,
  };
}

function toolApprovalsListPending() {
  return {
    status: "ok",
    pending: Object.values(pendingApprovals).filter((a) => a.status === "pending"),
  };
}

function toolApprovalsDecide({ approval_id, decision, decided_by = "user" }) {
  if (decision !== "approve" && decision !== "deny") {
    return { status: "error", error: "decision must be 'approve' or 'deny'" };
  }
  const item = pendingApprovals[approval_id];
  if (!item || item.status !== "pending") {
    return { status: "error", error: `Unknown or settled approval '${approval_id}'` };
  }
  item.status = decision === "approve" ? "approved" : "denied";
  item.decided_by = decided_by;
  item.decided_ts = Date.now() / 1000;
  let executed = null;
  if (decision === "approve" && item.tool === "calendar_delete_event") {
    const eventId = item.args.event_id;
    const ev = state.calendar.find((e) => e.id === eventId);
    state.calendar = state.calendar.filter((e) => e.id !== eventId);
    executed = { deleted_event: eventId, deleted_title: ev ? ev.title : null };
  }
  if (approval_id === lastPendingId) lastPendingId = null;
  return { status: "ok", approval_id, decision, executed };
}

function toolAuditGetLog({ limit = 20 }) {
  const { ok, checked } = verifyChain();
  return {
    status: "ok", chain_valid: ok, entries_checked: checked,
    entries: getAudit(limit),
  };
}

function toolPermissionsGetScopes() {
  return { status: "ok", granted: [...grantedScopes()].sort(), tool_scopes: TOOL_SCOPES };
}

const TOOLS = {
  calendar_list_events: toolCalendarListEvents,
  calendar_add_event: toolCalendarAddEvent,
  calendar_delete_event: toolCalendarDeleteEvent,
  chores_list: toolChoresList,
  chores_assign: toolChoresAssign,
  chores_complete: toolChoresComplete,
  grocery_list: toolGroceryList,
  grocery_add_item: toolGroceryAddItem,
  grocery_remove_item: toolGroceryRemoveItem,
  school_get_schedule: toolSchoolGetSchedule,
  school_get_bus: toolSchoolGetBus,
  household_briefing: toolHouseholdBriefing,
  approvals_list_pending: toolApprovalsListPending,
  approvals_decide: toolApprovalsDecide,
  audit_get_log: toolAuditGetLog,
  permissions_get_scopes: toolPermissionsGetScopes,
};

/** Invoke one tool with scope enforcement + audit, and build the trace span. */
function callTool(name, args) {
  const t0 = Date.now();
  const granted = grantedScopes();
  const required = TOOL_SCOPES[name] || [];
  const missing = required.filter((s) => !granted.has(s));
  let result;
  if (missing.length) {
    result = {
      status: "denied",
      error: `Missing required scopes for ${name}: ${missing}. Granted: ${[...granted].sort()}`,
    };
  } else {
    result = TOOLS[name](args || {});
  }
  const summary = result && typeof result === "object" ? String(result.status || "ok") : "ok";
  const approvalId = result && result.approval_id ? result.approval_id : null;
  audit(name, args || {}, summary, granted, approvalId);
  const span = {
    tool: name, args: args || {},
    duration_ms: Math.max(1, Math.round(Date.now() - t0)),
    ts: Date.now() / 1000,
    result_status: summary,
  };
  // Only a live approval_required result raises a pending-approval card.
  // approvals_decide / calendar_delete_event echo the approval_id on their
  // *settled* results (status ok/error/denied) — surfacing those would render
  // a duplicate "Approval required" card after every approve/deny.
  if (summary === "approval_required" && approvalId) span.approval_id = approvalId;
  if (result && result.reason) span.reason = result.reason;
  return { result, span };
}

// ---------------------------------------------------------------------------
// Intent router — deterministic port of route_demo() in src/homeops/agent.py
// ---------------------------------------------------------------------------

function route(text) {
  const t = (text || "").toLowerCase();
  const hasYes = ["approve", "yes", "go ahead", "do it", "confirm"].some((w) => t.includes(w));
  const hasNo = ["deny", "don't", "cancel", "never mind"].some((w) => t.includes(w));

  if (hasYes && !hasNo && lastPendingId) {
    return {
      kind: "approve",
      calls: [{ tool: "approvals_decide",
                args: { approval_id: lastPendingId, decision: "approve", decided_by: "user" } }],
    };
  }
  if (hasNo && lastPendingId) {
    return {
      kind: "deny",
      calls: [{ tool: "approvals_decide",
                args: { approval_id: lastPendingId, decision: "deny", decided_by: "user" } }],
    };
  }
  if (["briefing", "good morning", "morning rundown", "my day"].some((w) => t.includes(w))) {
    return { kind: "briefing", calls: [{ tool: "household_briefing", args: { day: "Monday" } }] };
  }
  if (t.includes("delete") && ["event", "meeting", "calendar"].some((w) => t.includes(w))) {
    return { kind: "delete",
             calls: [{ tool: "calendar_delete_event", args: { event_id: "evt_3", approval_id: "" } }] };
  }
  if (t.includes("grocery") && ["add", "need", "get some", "buy"].some((w) => t.includes(w))) {
    let item = "Oat milk";
    for (const cand of ["oat milk", "bread", "cheese", "yogurt", "bananas"]) {
      if (t.includes(cand)) { item = cand.replace(/\b\w/g, (c) => c.toUpperCase()); break; }
    }
    return { kind: "grocery_add",
             calls: [{ tool: "grocery_add_item", args: { item, qty: "1", added_by: "alexa" } }] };
  }
  if (t.includes("grocery") || t.includes("shopping list")) {
    return { kind: "grocery_list", calls: [{ tool: "grocery_list", args: {} }] };
  }
  if (t.includes("assign") && ["chore", "laundry", "dishes", "trash", "task"].some((w) => t.includes(w))) {
    const who = ["sofia", "mateo", "maya", "daniel"].find((k) => t.includes(k)) || "mateo";
    return { kind: "chores_assign",
             calls: [{ tool: "chores_assign", args: { chore_id: "ch_3", assignee: who } }] };
  }
  if (t.includes("chore") && ["done", "complete", "finished"].some((w) => t.includes(w))) {
    return { kind: "chores_complete",
             calls: [{ tool: "chores_complete", args: { chore_id: "ch_1" } }] };
  }
  if (t.includes("chore")) {
    return { kind: "chores_list", calls: [{ tool: "chores_list", args: { status: "" } }] };
  }
  if (t.includes("bus")) {
    const kid = t.includes("sofia") ? "sofia" : "mateo";
    return { kind: "bus", calls: [{ tool: "school_get_bus", args: { kid } }] };
  }
  if (["school", "class", "schedule"].some((w) => t.includes(w))) {
    const kid = t.includes("sofia") ? "sofia" : "mateo";
    return { kind: "schedule", calls: [{ tool: "school_get_schedule", args: { kid, day: "Monday" } }] };
  }
  if (["calendar", "event", "meeting"].some((w) => t.includes(w))) {
    return { kind: "calendar_list",
             calls: [{ tool: "calendar_list_events", args: { day: "" } }] };
  }
  if (t.includes("add") && ["event", "calendar", "dentist", "appointment"].some((w) => t.includes(w))) {
    return { kind: "calendar_add",
             calls: [{ tool: "calendar_add_event",
                       args: { title: "Dentist — checkup", day: "Thursday",
                               time: "4:00 PM", who: "sofia" } }] };
  }
  if (["audit", "what did you do", "log"].some((w) => t.includes(w))) {
    return { kind: "audit", calls: [{ tool: "audit_get_log", args: { limit: 10 } }] };
  }
  if (["permission", "scope"].some((w) => t.includes(w))) {
    return { kind: "scopes", calls: [{ tool: "permissions_get_scopes", args: {} }] };
  }
  return { kind: "fallback", calls: [] };
}

// ---------------------------------------------------------------------------
// Reply composition — warm voice-assistant text built from real tool results
// ---------------------------------------------------------------------------

function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

function replyFor(kind, results) {
  const r = results[0] || {};
  switch (kind) {
    case "briefing": {
      const evs = r.events || [];
      const evTxt = evs.length
        ? evs.map((e) => `${e.title} at ${e.time}`).join("; ")
        : "nothing on the calendar";
      const buses = r.buses || {};
      const busTxt = Object.entries(buses)
        .map(([kid, b]) => `${cap(kid)}'s bus ${b.route} picks up at ${b.pickup}`)
        .join("; ");
      return `Good morning, Rivera family — here's Monday: ${r.events ? r.events.length : 0} event(s) ` +
        `on the calendar — ${evTxt}. ${(r.pending_chores || []).length} chore(s) still open, ` +
        `${r.grocery_count || 0} item(s) on the grocery list. ${busTxt}. Anything else?`;
    }
    case "delete":
      return r.status === "approval_required"
        ? `That action needs your approval: ${r.reason} Say approve or deny.`
        : "That event was already handled.";
    case "approve": {
      const ex = r.executed || {};
      return `Done — approved and executed. ${ex.deleted_title ? `"${ex.deleted_title}" is off the calendar.` : ""} Anything else?`;
    }
    case "deny":
      return "Understood — I cancelled that. Nothing was changed.";
    case "grocery_add":
      return `Added ${r.entry ? r.entry.item : "it"} to the grocery list.`;
    case "grocery_list": {
      const items = (r.items || []).map((g) => `${g.item} (${g.qty})`).join(", ");
      return `Here's the grocery list: ${items || "it's empty"}.`;
    }
    case "bus":
      return r.status === "ok"
        ? `${cap(r.kid)}'s bus is route ${r.route} — pickup ${r.pickup} at ${r.stop}, dropoff ${r.dropoff}.`
        : `Sorry — ${r.error || "I couldn't find that bus info."}`;
    case "schedule": {
      const periods = (r.periods || []).join(", ");
      return r.status === "ok"
        ? `Here's ${cap(r.kid)}'s schedule for ${r.day} at ${r.school}: ${periods || "no classes found"}.`
        : `Sorry — ${r.error || "I couldn't find that schedule."}`;
    }
    case "calendar_list": {
      const evs = (r.events || []).map((e) => `${e.day}: ${e.title} at ${e.time}`).join("; ");
      return `Here's the family calendar: ${evs || "no events"}.`;
    }
    case "calendar_add":
      return r.status === "ok"
        ? `Added "${r.event.title}" to the calendar for ${r.event.day} at ${r.event.time}.`
        : `Sorry — ${r.error || "I couldn't add that."}`;
    case "chores_assign":
      return r.status === "ok"
        ? `Assigned "${r.task}" to ${cap(r.assignee)}.`
        : `Sorry — ${r.error || "I couldn't assign that."}`;
    case "chores_complete":
      return r.status === "ok"
        ? `Marked "${r.task}" complete. Nice work.`
        : `Sorry — ${r.error || "I couldn't find that chore."}`;
    case "chores_list": {
      const open = (r.chores || []).filter((c) => c.status !== "done");
      const txt = open.map((c) => `${c.task}${c.assignee ? ` (${cap(c.assignee)})` : " (unassigned)"}`).join("; ");
      return `Here are the household chores: ${txt || "all done"}.`;
    }
    case "audit": {
      const ents = r.entries || [];
      const last = ents.slice(-5).map((e) => `${e.tool}`).join(", ");
      return `Here's the recent audit log — ${ents.length} entr${ents.length === 1 ? "y" : "ies"} recorded, ` +
        `hash chain verified: ${r.chain_valid ? "valid" : "INVALID"}. ` +
        (last ? `Latest calls: ${last}.` : "") + " Open the audit panel to inspect every entry.";
    }
    case "scopes": {
      const g = (r.granted || []).join(", ");
      return `The skill is granted these scopes: ${g}. Every tool declares the scopes it needs, ` +
        `and calls without them are denied explicitly — not silently.`;
    }
    default:
      return "I can help with the family calendar, chores, grocery list, school schedules, " +
        "and the morning briefing. What do you need?";
  }
}

/** Handle one chat turn: route → run tools → reply. Same contract as web/bridge.py. */
function handleChat(text) {
  const routed = route(text);
  const trace = [];
  const results = [];
  for (const c of routed.calls) {
    const { result, span } = callTool(c.tool, c.args);
    trace.push(span);
    results.push(result);
  }
  const reply = replyFor(routed.kind, results);
  const approvalSpan = trace.find((s) => s.approval_id && s.result_status === "approval_required");
  const approval = approvalSpan
    ? { approval_id: approvalSpan.approval_id, reason: approvalSpan.reason || "",
        tool: approvalSpan.tool }
    : null;
  return { reply, trace, approval };
}

module.exports = {
  handleChat,
  reset,
  getAudit,
  verifyChain,
  TOOL_SCOPES,
  ALL_SCOPES,
};
