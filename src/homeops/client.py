"""MCP client for the HomeOps server — Streamable HTTP, MCP spec 2025-11-25+.

The Strands agent below drives the household tools through this client, so the
Alexa+ track tech (MCP) is genuinely invoked at runtime, not just mentioned.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_URL = os.environ.get("HOMEOPS_MCP_URL", "http://127.0.0.1:8765/mcp")


def _http_client():
    """Localhost MCP traffic must not go through proxy env vars.

    The SDK's default client honors proxy env; in sandboxed environments the
    NO_PROXY list can contain IPv6 literals (``[::1]``) that httpx2 fails to
    parse, breaking even plain localhost connections. We connect to our own
    server, so bypassing proxy env is correct here.
    """
    import httpx2
    return httpx2.AsyncClient(
        trust_env=False, follow_redirects=True,
        timeout=httpx2.Timeout(30.0, read=300.0))


class HomeOpsClient:
    """Async MCP client. Use as ``async with HomeOpsClient() as c:``."""

    def __init__(self, url: str = DEFAULT_URL):
        self.url = url
        self._stack = None
        self.session: ClientSession | None = None

    async def __aenter__(self) -> "HomeOpsClient":
        from contextlib import AsyncExitStack
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        http = await self._stack.enter_async_context(_http_client())
        read, write, *_ = await self._stack.enter_async_context(
            streamable_http_client(self.url, http_client=http))
        self.session = ClientSession(read, write)
        await self._stack.enter_async_context(self.session)
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc):
        if self._stack:
            await self._stack.__aexit__(*exc)
        self.session = None

    async def list_tools(self) -> list[dict]:
        result = await self.session.list_tools()
        return [{"name": t.name, "description": t.description,
                 "inputSchema": t.input_schema} for t in result.tools]

    async def call_tool(self, name: str, args: dict) -> dict:
        """Call a tool; returns the parsed JSON result (or raw text fallback)."""
        import json
        result = await self.session.call_tool(name, args or {})
        texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
        raw = "\n".join(texts)
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return {"status": "ok" if not result.isError else "error",
                    "raw": raw}


@asynccontextmanager
async def connect(url: str = DEFAULT_URL):
    async with HomeOpsClient(url) as client:
        yield client
