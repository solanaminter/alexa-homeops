"""Pytest fixtures: spin up real HomeOps MCP server subprocesses."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
PY = REPO / ".venv" / "bin" / "python"


def _wait_for_port(port: int, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"server on :{port} did not start")


def _start_server(port: int, data_dir: Path, extra_env: dict | None = None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env["HOMEOPS_DATA_DIR"] = str(data_dir)
    env["HOMEOPS_PORT"] = str(port)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        [str(PY), "-m", "homeops.server"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=str(REPO),
    )
    _wait_for_port(port)
    return proc


@pytest.fixture(scope="session")
def server_url(tmp_path_factory):
    """Full-grant MCP server on :8765 with isolated data dir."""
    data_dir = tmp_path_factory.mktemp("data")
    proc = _start_server(8765, data_dir)
    yield "http://127.0.0.1:8765/mcp"
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def restricted_server_url(tmp_path_factory):
    """Least-privilege MCP server on :8766 (calendar+chores read only)."""
    data_dir = tmp_path_factory.mktemp("data_restricted")
    proc = _start_server(8766, data_dir,
                         {"HOMEOPS_SCOPES": "calendar:read,chores:read"})
    yield "http://127.0.0.1:8766/mcp"
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(autouse=True)
def _src_on_path():
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
