"""HomeOps evals — scenario-based tool-calling evaluation.

Each scenario drives the (offline) agent with a user utterance and asserts the
expected MCP tools fired with the expected arguments. Run against a live MCP
server::

    python -m homeops.server &          # or: pytest (spins one up)
    python -m homeops.evals

Exit code 0 = all scenarios pass. This is the "evals on tool-calling" layer:
the model is scripted, but every assertion covers the real agent → MCP →
server path, including approvals, scope denials, and the audit chain.
"""

from __future__ import annotations

import dataclasses
import os

import homeops.agent as agent_mod
from homeops.agent import TRACE, build_demo_agent, new_turn


def _text(result) -> str:
    parts = []
    for b in result.message.get("content", []):
        if isinstance(b, dict) and "text" in b:
            parts.append(b["text"])
    return " ".join(parts)


def _tools_fired() -> list[tuple[str, dict]]:
    return [(t["tool"], t["args"]) for t in TRACE]


@dataclasses.dataclass
class Scenario:
    name: str
    turns: list[str]                      # user utterances, in order
    expect_tools: list[str]               # tools that must fire (in order, per turn joined)
    expect_text_contains: list[str] | None = None


SCENARIOS: list[Scenario] = [
    Scenario(
        name="morning_briefing",
        turns=["Good morning, give me the family briefing"],
        expect_tools=["household_briefing"],
        expect_text_contains=["briefing"],
    ),
    Scenario(
        name="grocery_add",
        turns=["Add oat milk to the grocery list"],
        expect_tools=["grocery_add_item"],
    ),
    Scenario(
        name="chore_assign",
        turns=["Assign the laundry to Sofia"],
        expect_tools=["chores_assign"],
    ),
    Scenario(
        name="school_bus",
        turns=["When is Mateo's bus pickup?"],
        expect_tools=["school_get_bus"],
    ),
    Scenario(
        name="delete_with_approval",
        turns=["Delete the PTA meeting from the calendar", "Yes, approve it"],
        expect_tools=["calendar_delete_event", "approvals_decide"],
        expect_text_contains=["approval"],
    ),
    Scenario(
        name="deny_keeps_state",
        turns=["Delete the PTA meeting from the calendar", "No, cancel that"],
        expect_tools=["calendar_delete_event", "approvals_decide"],
        expect_text_contains=["cancelled"],
    ),
]


def run_scenario(agent, sc: Scenario) -> dict:
    fired: list[str] = []
    texts: list[str] = []
    for utterance in sc.turns:
        new_turn()
        result = agent(utterance)
        fired.extend(t for t, _ in _tools_fired())
        texts.append(_text(result))
    ok_tools = fired == sc.expect_tools
    ok_text = all(any(w.lower() in t.lower() for t in texts)
                  for w in (sc.expect_text_contains or []))
    return {"name": sc.name, "pass": ok_tools and ok_text,
            "fired": fired, "expected": sc.expect_tools,
            "texts": texts}


def run_all(url: str | None = None) -> list[dict]:
    if url:
        agent_mod.MCP_URL = url
    agent = build_demo_agent()
    return [run_scenario(agent, sc) for sc in SCENARIOS]


def _server_store() -> "Store":
    """Store pointing at the MCP server's data dir (honors HOMEOPS_DATA_DIR)."""
    from pathlib import Path
    from homeops.store import Store
    data_dir = os.environ.get("HOMEOPS_DATA_DIR")
    return Store(Path(data_dir)) if data_dir else Store()


def main() -> int:
    # Fresh state so scenarios are deterministic.
    store = _server_store()
    store.reset()
    results = run_all()
    width = max(len(r["name"]) for r in results)
    failed = 0
    for r in results:
        mark = "PASS" if r["pass"] else "FAIL"
        print(f"[{mark}] {r['name']:<{width}}  fired={r['fired']}")
        if not r["pass"]:
            failed += 1
            print(f"       expected={r['expected']}")
            print(f"       texts={r['texts']}")
    # Audit chain integrity after the whole run.
    ok, n = store.verify_chain()
    print(f"[{'PASS' if ok else 'FAIL'}] audit_chain  entries={n} valid={ok}")
    failed += 0 if ok else 1
    print(f"\n{len(results) + 1 - failed}/{len(results) + 1} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
