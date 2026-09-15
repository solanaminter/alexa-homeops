"""Agent eval tests: scenario assertions run as pytest."""

from __future__ import annotations

import pytest

import homeops.agent as agent_mod
from homeops.evals import SCENARIOS, run_scenario
from homeops.agent import build_demo_agent
from homeops.store import Store


@pytest.fixture(scope="module")
def agent(server_url):
    agent_mod.MCP_URL = server_url
    # NOTE: the server seeds itself from sample_data/ into its own tmp data dir
    # on first boot, so every pytest session starts from deterministic state.
    return build_demo_agent()


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_scenario(agent, sc):
    result = run_scenario(agent, sc)
    assert result["pass"], (
        f"scenario {sc.name}: fired={result['fired']} "
        f"expected={result['expected']} texts={result['texts']}"
    )


def test_agent_actually_invokes_mcp_track_tech(agent, server_url):
    """Guard: the agent path must call the MCP server at runtime."""
    from homeops.agent import TRACE, new_turn
    new_turn()
    agent("What is on the grocery list?")
    assert TRACE, "no MCP tool calls recorded"
    assert TRACE[0]["tool"] == "grocery_list"
