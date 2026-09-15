"""Web bridge: serves the simulated Alexa+ experience and drives the demo agent.

Run:
    python -m homeops.server &   # MCP server on :8765
    python web/bridge.py         # demo UI on http://127.0.0.1:8080

The UI is a simulation of the Alexa+ experience; every assistant turn runs the
real Strands agent → real MCP tools → real MCP server. Only the LLM is
scripted (ScriptedModel) so the demo works with no AWS credentials; the
production agent swaps in Bedrock with zero tool-path changes.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import homeops.agent as agent_mod
from homeops.agent import TRACE, build_demo_agent, new_turn

WEB_DIR = Path(__file__).resolve().parent
_agent = build_demo_agent()
_agent_lock = threading.Lock()


def _agent_text(result) -> str:
    return " ".join(b.get("text", "") for b in result.message.get("content", [])
                    if isinstance(b, dict) and "text" in b)


class Handler(BaseHTTPRequestHandler):
    server_version = "HomeOpsBridge/0.1"

    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, ctype: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            return self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        # Static demo assets bundled in web/ (e.g. the demo video at
        # ./homeops-demo.mp4, copied from ../assets/). Served here so the
        # local path behaves exactly like the Vercel deployment.
        if parsed.path == "/homeops-demo.mp4":
            video = WEB_DIR / "homeops-demo.mp4"
            if video.exists():
                return self._send_file(video, "video/mp4")
            self._send(404, {"error": "demo video not found"})
            return
        if parsed.path == "/api/health":
            return self._send(200, {"ok": True, "mcp_url": agent_mod.MCP_URL})
        if parsed.path == "/api/audit":
            from homeops.client import connect
            import asyncio

            async def _go():
                async with connect(agent_mod.MCP_URL) as c:
                    return await c.call_tool("audit_get_log", {"limit": 25})

            loop = asyncio.new_event_loop()
            try:
                data = loop.run_until_complete(_go())
            finally:
                loop.close()
            return self._send(200, data)
        self._send(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")

        if parsed.path == "/api/chat":
            text = payload.get("text", "")
            with _agent_lock:
                new_turn()
                result = _agent(text)
                reply = _agent_text(result)
                trace = list(TRACE)
            approval = next(
                ({"approval_id": t["approval_id"], "reason": t["reason"],
                  "tool": t["tool"]}
                 for t in trace if t.get("approval_id")), None)
            return self._send(200, {"reply": reply, "trace": trace,
                                    "approval": approval})

        if parsed.path == "/api/reset":
            global _agent
            with _agent_lock:
                _agent = build_demo_agent()
            return self._send(200, {"ok": True})

        self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass  # quiet


def main() -> None:
    port = int(__import__("os").environ.get("HOMEOPS_WEB_PORT", "8080"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"HomeOps demo UI: http://127.0.0.1:{port}  (MCP: {agent_mod.MCP_URL})")
    server.serve_forever()


if __name__ == "__main__":
    main()
