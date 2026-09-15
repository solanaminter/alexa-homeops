"""Drive the canonical demo arc and print a formatted transcript.

Used to capture REAL terminal footage for the demo video. Requires the MCP
server on :8765. Resets state first so the run is deterministic.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import homeops.agent as agent_mod
from homeops.agent import TRACE, build_demo_agent, new_turn
from homeops.store import Store

SCRIPT = [
    "Good morning, give me the family briefing",
    "Add oat milk to the grocery list",
    "When is Mateo's bus pickup?",
    "Delete the PTA meeting from the calendar",
    "Yes, approve it",
    "Show me the audit log",
]


def text_of(result) -> str:
    return " ".join(b.get("text", "") for b in result.message.get("content", [])
                    if isinstance(b, dict) and "text" in b)


def main() -> None:
    Store().reset()
    agent = build_demo_agent()
    print("HomeOps · simulated Alexa+ session · MCP server:", agent_mod.MCP_URL)
    print("=" * 72)
    for utterance in SCRIPT:
        new_turn()
        print(f"\n🧑  {utterance}")
        result = agent(utterance)
        for t in TRACE:
            args = " ".join(f"{k}={v}" for k, v in t["args"].items())
            status = t.get("result_status", "ok")
            print(f"    ⚙ {t['tool']} {args} → {status} ({t['duration_ms']}ms)")
        print(f"🔵  {text_of(result)}")
    print("\n" + "=" * 72)
    print("session complete — audit chain valid:",
          Store().verify_chain()[0])


if __name__ == "__main__":
    main()
