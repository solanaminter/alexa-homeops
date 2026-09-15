"""Persistent store: household data, hash-chained audit log, approvals, scopes.

All state lives under ``HOMEOPS_DATA_DIR`` (default ``./data``). The audit log
is append-only JSONL where each entry carries the SHA-256 of the previous
entry, making tampering evident. ``verify_chain()`` replays the file.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Scopes: every tool declares the scope(s) it needs; the server enforces them.
# ---------------------------------------------------------------------------

TOOL_SCOPES: dict[str, list[str]] = {
    "calendar_list_events": ["calendar:read"],
    "calendar_add_event": ["calendar:write"],
    "calendar_delete_event": ["calendar:write"],
    "chores_list": ["chores:read"],
    "chores_assign": ["chores:write"],
    "chores_complete": ["chores:write"],
    "grocery_list": ["grocery:read"],
    "grocery_add_item": ["grocery:write"],
    "grocery_remove_item": ["grocery:write"],
    "school_get_schedule": ["school:read"],
    "school_get_bus": ["school:read"],
    "household_briefing": ["briefing:read"],
    "approvals_list_pending": ["approvals:read"],
    "approvals_decide": ["approvals:write"],
    "audit_get_log": ["audit:read"],
    "permissions_get_scopes": [],
}

ALL_SCOPES = sorted({s for scopes in TOOL_SCOPES.values() for s in scopes})


def granted_scopes() -> set[str]:
    """Scopes granted to the calling skill (env override for least-privilege)."""
    raw = os.environ.get("HOMEOPS_SCOPES")
    if raw is None:
        return set(ALL_SCOPES)  # demo default: full grant
    return {s.strip() for s in raw.split(",") if s.strip()}


def check_scopes(tool: str) -> tuple[bool, list[str]]:
    required = TOOL_SCOPES.get(tool, [])
    granted = granted_scopes()
    missing = [s for s in required if s not in granted]
    return (len(missing) == 0, missing)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

SEED_PATH = Path(__file__).resolve().parent.parent.parent / "sample_data" / "household.json"


def _data_dir() -> Path:
    d = Path(os.environ.get("HOMEOPS_DATA_DIR", Path.cwd() / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d


class Store:
    """Household state + audit log + approval queue, persisted as JSON/JSONL."""

    def __init__(self, data_dir: Path | None = None):
        self.dir = Path(data_dir) if data_dir else _data_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self.dir / "state.json"
        self._audit_file = self.dir / "audit.jsonl"
        self._approvals_file = self.dir / "approvals.json"
        if not self._state_file.exists():
            seed = json.loads(SEED_PATH.read_text())
            self._state_file.write_text(json.dumps(seed, indent=2))
        if not self._approvals_file.exists():
            self._approvals_file.write_text(json.dumps({"pending": {}}))

    # -- state ------------------------------------------------------------
    def load(self) -> dict:
        return json.loads(self._state_file.read_text())

    def save(self, state: dict) -> None:
        self._state_file.write_text(json.dumps(state, indent=2))

    def mutate(self, fn) -> dict:
        state = self.load()
        fn(state)
        self.save(state)
        return state

    # -- audit ------------------------------------------------------------
    def _last_hash(self) -> str:
        if not self._audit_file.exists():
            return "GENESIS"
        last = None
        with self._audit_file.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    last = line
        if last is None:
            return "GENESIS"
        return json.loads(last)["entry_hash"]

    def audit(self, tool: str, args: dict, result_summary: str,
              scopes: list[str], approval_id: str | None = None) -> dict:
        prev = self._last_hash()
        entry = {
            "seq": self._audit_count() + 1,
            "ts": time.time(),
            "tool": tool,
            "args": _redact(args),
            "result_summary": result_summary,
            "scopes": scopes,
            "approval_id": approval_id,
            "prev_hash": prev,
        }
        payload = json.dumps(entry, sort_keys=True)
        entry["entry_hash"] = hashlib.sha256((prev + payload).encode()).hexdigest()
        with self._audit_file.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def _audit_count(self) -> int:
        if not self._audit_file.exists():
            return 0
        n = 0
        with self._audit_file.open() as f:
            for line in f:
                if line.strip():
                    n += 1
        return n

    def get_audit(self, limit: int = 50) -> list[dict]:
        if not self._audit_file.exists():
            return []
        entries = [json.loads(l) for l in self._audit_file.open() if l.strip()]
        return entries[-limit:]

    def verify_chain(self) -> tuple[bool, int]:
        """Replay the hash chain. Returns (ok, entries_checked)."""
        prev = "GENESIS"
        n = 0
        if not self._audit_file.exists():
            return True, 0
        for line in self._audit_file.open():
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            digest = entry.pop("entry_hash")
            payload = json.dumps(entry, sort_keys=True)
            if entry.get("prev_hash") != prev:
                return False, n
            if hashlib.sha256((prev + payload).encode()).hexdigest() != digest:
                return False, n
            prev = digest
            n += 1
        return True, n

    # -- approvals ----------------------------------------------------------
    def _load_approvals(self) -> dict:
        return json.loads(self._approvals_file.read_text())

    def _save_approvals(self, data: dict) -> None:
        self._approvals_file.write_text(json.dumps(data, indent=2))

    def request_approval(self, tool: str, args: dict, reason: str) -> dict:
        data = self._load_approvals()
        approval_id = "apr_" + uuid.uuid4().hex[:8]
        data["pending"][approval_id] = {
            "id": approval_id,
            "tool": tool,
            "args": args,
            "reason": reason,
            "ts": time.time(),
            "status": "pending",
        }
        self._save_approvals(data)
        return data["pending"][approval_id]

    def list_pending(self) -> list[dict]:
        data = self._load_approvals()
        return [a for a in data["pending"].values() if a["status"] == "pending"]

    def decide(self, approval_id: str, decision: str, decided_by: str = "user") -> dict | None:
        data = self._load_approvals()
        item = data["pending"].get(approval_id)
        if item is None or item["status"] != "pending":
            return None
        item["status"] = "approved" if decision == "approve" else "denied"
        item["decided_by"] = decided_by
        item["decided_ts"] = time.time()
        self._save_approvals(data)
        return item

    def reset(self) -> None:
        """Restore seed data (used by tests/demos). Clears state, approvals, audit."""
        seed = json.loads(SEED_PATH.read_text())
        self._state_file.write_text(json.dumps(seed, indent=2))
        self._approvals_file.write_text(json.dumps({"pending": {}}))
        if self._audit_file.exists():
            self._audit_file.unlink()


def _redact(args: dict) -> dict:
    """Deep-copy args; nothing sensitive is stored in this demo, hook for PII."""
    return copy.deepcopy(args)
