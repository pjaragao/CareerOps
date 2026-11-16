#!/usr/bin/env python3
"""The bridge between Lolo's Hermes (in a container) and the apply tools on the host (2026-11-16).

Hermes runs the apply agent on a free Nous model, but the browser (the worker's Playwright MCP, 127.0.0.1 only) and the
careerops tools (mailbox, portal passwords, answers) live on the host. This bridge serves both to the containers' network
(the docker gateway, 172.26.0.1), behind a token, and stays the gatekeeper:

  * it only works while the runner has opened a task (POST /run on the control port); outside a task every call is refused
  * every browser call is checked BEFORE it runs, with the runner's own audit (allowed tools, target host, allowed files):
    a call off the task is refused and never reaches the browser
  * every call is logged with its full arguments, and the runner reads the log to audit and report the run
  * the bridge keeps its own session with the browser and reconnects when the worker restarts it

Public  (CAREEROPS_BRIDGE_HOST:CAREEROPS_BRIDGE_PORT, Bearer token):  /browser/mcp  and  /careerops/mcp
Control (127.0.0.1:CAREEROPS_BRIDGE_CONTROL_PORT, Bearer token):     POST /run, GET /calls, POST /end, GET /health

Only the standard library. Runs as a systemd user service (careerops-mcp-bridge.service)."""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DIR = str(Path(__file__).resolve().parent)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import ats_helpers  # noqa: E402
import run as runner  # noqa: E402



class Task:
    """The one task the runner opened. One at a time: the runner holds a lock and runs a batch in sequence."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.action: Optional[dict] = None
        self.calls: List[dict] = []
        self.careerops: Optional[ats_helpers.CareerOpsMcpServer] = None
        self.opened_at = 0.0

    def open(self, action: dict, env: dict) -> None:
        with self.lock:
            self.action = action
            self.calls = []
            self.opened_at = time.time()
            self.careerops = ats_helpers.CareerOpsMcpServer(env, context={**(action.get("dossier") or {}), "_action_id": action.get("id")})

    def close(self) -> List[dict]:
        with self.lock:
            calls, self.action, self.careerops, self.calls = self.calls, None, None, []
            return calls

    def log(self, call: dict) -> None:
        with self.lock:
            if len(self.calls) < 600:
                self.calls.append(call)


TOOLS_CACHE = Path(os.environ.get("CAREEROPS_BRIDGE_TOOLS_CACHE", Path.home() / ".config" / "careerops" / "bridge-browser-tools.json"))


class BrowserUpstream:
    """The bridge's own MCP session with the worker's Playwright server. Hermes keeps one stable session with the bridge;
    this side reconnects when the worker restarts the browser (it closes it when idle), so a restart never costs Hermes
    its tools. The tool list is cached on disk, so Hermes gets it even if it boots while the browser is down."""

    def __init__(self, url: str):
        self.url = url
        self.session: Optional[str] = None
        self.lock = threading.Lock()
        self._id = 0

    def _post(self, method: str, params: Optional[dict] = None, notify: bool = False, timeout: int = 300) -> dict:
        import urllib.request
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not notify:
            self._id += 1
            payload["id"] = self._id
        if params is not None:
            payload["params"] = params
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as res:
            self.session = res.headers.get("Mcp-Session-Id") or self.session
            raw = res.read().decode("utf-8", "replace")
        if notify or not raw.strip():
            return {}
        body = raw.strip()
        if body.startswith("{"):
            return json.loads(body)
        last: dict = {}
        for line in body.splitlines():
            if line.startswith("data:") and line[5:].strip():
                try:
                    last = json.loads(line[5:].strip())
                except ValueError:
                    pass
        return last

    def _connect(self) -> None:
        self.session = None
        self._post("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                  "clientInfo": {"name": "careerops-bridge", "version": "1"}}, timeout=20)
        self._post("notifications/initialized", notify=True, timeout=20)

    def reset(self) -> None:
        with self.lock:
            self.session = None

    def tools(self) -> List[dict]:
        """The runner's browser tools only (runner.TOOLS), live when the browser answers, else from the cache."""
        try:
            with self.lock:
                if not self.session:
                    self._connect()
                listed = ((self._post("tools/list", {}, timeout=20).get("result") or {}).get("tools")) or []
            keep = [t for t in listed if t.get("name") in runner.TOOLS]
            if keep:
                try:
                    TOOLS_CACHE.parent.mkdir(parents=True, exist_ok=True)
                    TOOLS_CACHE.write_text(json.dumps(keep), encoding="utf-8")
                except OSError:
                    pass
                return keep
        except Exception:
            self.session = None
        try:
            return json.loads(TOOLS_CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def call(self, name: str, args: dict) -> dict:
        """The JSON-RPC result of one call. Reconnects and retries only when the call surely never ran (no session, the
        server refused the connection or forgot the session); a timeout is never retried (a click may have happened)."""
        import urllib.error
        with self.lock:
            for attempt in range(2):
                try:
                    if not self.session:
                        self._connect()
                    res = self._post("tools/call", {"name": name, "arguments": args})
                    if res.get("error"):
                        return {"content": [{"type": "text", "text": json.dumps(res["error"])}], "isError": True}
                    return res.get("result") or {"content": [], "isError": False}
                except urllib.error.HTTPError as exc:
                    self.session = None
                    if exc.code in (400, 404) and attempt == 0:
                        continue
                    return {"content": [{"type": "text", "text": f"browser tools error: HTTP {exc.code}"}], "isError": True}
                except (ConnectionRefusedError, urllib.error.URLError) as exc:
                    self.session = None
                    if attempt == 0 and isinstance(getattr(exc, "reason", exc), ConnectionRefusedError):
                        time.sleep(3)
                        continue
                    return {"content": [{"type": "text", "text": f"browser tools unreachable: {exc}"}], "isError": True}
            return {"content": [{"type": "text", "text": "browser tools unreachable"}], "isError": True}


# ── Token economy (2026-11-16): a page snapshot is ~38k characters and every later turn sends it again. What the agent
# never needs goes: wrapper lines with no text, icon glyphs, "[cursor=pointer]", long URLs, deep indentation. Every ref
# that names something (a field, a button, a label, a text) stays. A page still too long is cut, with a pointer to
# browser_find, never silently.
SNAPSHOT_MAX = int(os.environ.get("CAREEROPS_BRIDGE_SNAPSHOT_MAX") or 24000)
_WRAPPER = re.compile(r"^\s*- (generic|group|list|listitem|emphasis|strong|paragraph|region|navigation|banner|contentinfo|main|"
                      r"complementary|article|section|figure|img|separator|presentation|none)( \[[^\]]*\])*:?\s*$")
_ICON_ONLY = re.compile(r"^\s*- [a-z]+( \[[^\]]*\])*:\s*[-\s.·•|]*$")
_URL = re.compile(r"(https?://[^\s\)\]\"']{70})[^\s\)\]\"']+")


# options the task never needs (and "filename" would write files): left out of the schemas the model sees
SCHEMA_DROP = {"filename", "boxes", "doubleClick", "modifiers", "button", "depth"}
SHORT = {"element": "what the element is", "target": "ref from the snapshot, e.g. e12",
         "value": "text; checkbox: true/false; combobox: the option text", "ref": "ref from the snapshot, e.g. e12"}


def slim_tool(tool: dict) -> dict:
    """A browser tool's schema with what costs tokens on every turn and helps no one: JSON-schema plumbing, annotations,
    rarely useful options, long wording. Names, types, enums and required fields stay as they are."""
    schema = dict(tool.get("inputSchema") or {"type": "object", "properties": {}})
    required = set(schema.get("required") or [])

    def slim_props(props: dict) -> dict:
        out = {}
        for key, spec in (props or {}).items():
            if key in SCHEMA_DROP and key not in required:
                continue
            spec = dict(spec)
            if key in SHORT:
                spec["description"] = SHORT[key]
            elif spec.get("description"):
                first = spec["description"].split(". ")[0]
                spec["description"] = first if len(first) <= 90 else first[:first.rfind(" ", 0, 90)]
            if spec.get("type") == "array" and isinstance(spec.get("items"), dict) and spec["items"].get("properties"):
                items = dict(spec["items"])
                items["properties"] = slim_props(items["properties"])
                items.pop("additionalProperties", None)
                spec["items"] = items
            out[key] = spec
        return out
    slim = {"type": "object", "properties": slim_props(schema.get("properties") or {})}
    if schema.get("required"):
        slim["required"] = schema["required"]
    first = (tool.get("description") or "").split(". ")[0]
    desc = first if len(first) <= 140 else first[:first.rfind(" ", 0, 140)]
    return {"name": tool["name"], "description": desc, "inputSchema": slim}


def compact(text: str) -> str:
    out = []
    for line in (text or "").splitlines():
        if _WRAPPER.match(line) or _ICON_ONLY.match(line):
            continue
        line = line.replace(" [cursor=pointer]", "").replace(" [aria-hidden]", "")
        line = _URL.sub(r"\1…", line)
        stripped = line.lstrip(" ")
        depth = (len(line) - len(stripped)) // 2
        out.append(" " * min(depth, 12) + stripped)
    text = "\n".join(out)
    if len(text) > SNAPSHOT_MAX:
        text = (text[:SNAPSHOT_MAX] + f"\n[... page cut at {SNAPSHOT_MAX} characters to save tokens: use browser_find(text) "
                "to get the ref of anything further down, or scroll and snapshot again]")
    return text


def compact_result(result: dict) -> dict:
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            item["text"] = compact(item["text"])
    return result


def guard(task_action: Optional[dict], name: str, args: dict) -> Optional[str]:
    """Why this call must not run, or None. `name` is the runner's full tool name (mcp__playwright__browser_click)."""
    if not task_action:
        return "nenhuma tarefa aberta pelo CareerOps"
    flags = runner.audit([{"name": name, "input": args or {}}], task_action)
    return "; ".join(flags) if flags else None


def refusal(req_id: Any, reason: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id,
            "result": {"content": [{"type": "text", "text": f"REFUSED by CareerOps (nothing was done): {reason}"}], "isError": True}}


def make_public_handler(task: Task, token: str, browser: "BrowserUpstream"):

    class Handler(BaseHTTPRequestHandler):
        server_version = "careerops-bridge/1"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authorized(self) -> bool:
            if self.headers.get("Authorization", "") == f"Bearer {token}":
                return True
            self._json(401, {"error": "unauthorized"})
            return False

        def _json(self, code: int, payload: Optional[dict], extra: Optional[Dict[str, str]] = None) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else b""
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            if raw:
                self.wfile.write(raw)

        def _body(self) -> bytes:
            length = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(length) if length else b""

        # ── careerops tools ──
        def _careerops(self) -> None:
            raw = self._body()
            try:
                req = json.loads(raw.decode("utf-8")) if raw else {}
            except ValueError:
                return self._json(400, {"error": "invalid json"})
            server = task.careerops
            session = {"Mcp-Session-Id": "careerops-bridge"}
            if req.get("method") == "tools/call":
                params = req.get("params") or {}
                name = f"mcp__careerops__{params.get('name', '')}"
                args = params.get("arguments") or {}
                why = guard(task.action, name, args) if server else "nenhuma tarefa aberta pelo CareerOps"
                task.log({"name": name, "input": args, "refused": bool(why), "reason": why or "", "at": time.time()})
                if why:
                    return self._json(200, refusal(req.get("id"), why), session)
            if server is None:   # initialize / tools/list work without a task (Hermes connects at boot)
                server = ats_helpers.CareerOpsMcpServer({})
            code, payload = server.rpc(req)
            self._json(code, payload, session)

        # ── browser (worker's Playwright MCP, through BrowserUpstream) ──
        def _browser(self, method: str) -> None:
            if method == "DELETE":
                return self._json(200, {"ok": True})
            if method != "POST":
                return self._json(405, {"error": "method not allowed"})
            raw = self._body()
            try:
                req = json.loads(raw.decode("utf-8")) if raw else {}
            except ValueError:
                return self._json(400, {"error": "invalid json"})
            m, req_id = req.get("method"), req.get("id")
            session = {"Mcp-Session-Id": "careerops-browser"}
            if req_id is None and str(m).startswith("notifications/"):
                return self._json(202, None, session)
            if m == "initialize":
                return self._json(200, {"jsonrpc": "2.0", "id": req_id, "result": {
                    "protocolVersion": (req.get("params") or {}).get("protocolVersion") or "2025-03-26",
                    "capabilities": {"tools": {}}, "serverInfo": {"name": "careerops-browser", "version": "1"}}}, session)
            if m == "ping":
                return self._json(200, {"jsonrpc": "2.0", "id": req_id, "result": {}}, session)
            if m == "tools/list":
                return self._json(200, {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [slim_tool(t) for t in browser.tools()]}}, session)
            if m == "tools/call":
                params = req.get("params") or {}
                tool = str(params.get("name") or "")
                args = params.get("arguments") or {}
                name = f"mcp__playwright__{tool}"
                why = guard(task.action, name, args)
                task.log({"name": name, "input": args, "refused": bool(why), "reason": why or "", "at": time.time()})
                if why:
                    return self._json(200, refusal(req_id, why), session)
                args = {k: v for k, v in args.items() if k != "filename"}   # never writes files in the worker
                return self._json(200, {"jsonrpc": "2.0", "id": req_id, "result": compact_result(browser.call(tool, args))}, session)
            return self._json(200, {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {m}"}}, session)

        def _route(self, method: str) -> None:
            if not self._authorized():
                return
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/careerops/mcp":
                if method == "POST":
                    return self._careerops()
                if method == "DELETE":
                    return self._json(200, {"ok": True})
                return self._json(405, {"error": "method not allowed"})
            if path == "/browser/mcp":
                return self._browser(method)
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            self._route("POST")

        def do_GET(self) -> None:
            self._route("GET")

        def do_DELETE(self) -> None:
            self._route("DELETE")

    return Handler


def make_control_handler(task: Task, token: str, env_loader, browser: "BrowserUpstream"):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _json(self, code: int, payload: dict) -> None:
            raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _ok(self) -> bool:
            if self.headers.get("Authorization", "") == f"Bearer {token}":
                return True
            self._json(401, {"error": "unauthorized"})
            return False

        def do_GET(self) -> None:
            if self.path == "/health":
                return self._json(200, {"ok": True, "task": (task.action or {}).get("id")})
            if not self._ok():
                return
            if self.path == "/calls":
                with task.lock:
                    return self._json(200, {"action_id": (task.action or {}).get("id"), "calls": list(task.calls)})
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._ok():
                return
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if self.path == "/run":
                action = body.get("action") or {}
                if not action.get("id"):
                    return self._json(400, {"error": "action required"})
                task.open(action, env_loader())
                browser.reset()   # a fresh browser session per task, like a new Claude run
                return self._json(200, {"ok": True, "action_id": action["id"]})
            if self.path == "/end":
                return self._json(200, {"calls": task.close()})
            self._json(404, {"error": "not found"})

    return Handler


def serve(env: Optional[dict] = None) -> Tuple[ThreadingHTTPServer, ThreadingHTTPServer, Task]:
    env = env or ats_helpers.load_runtime_env(runner.load_env())
    token = env.get("CAREEROPS_BRIDGE_TOKEN") or ""
    if len(token) < 16:
        raise SystemExit("CAREEROPS_BRIDGE_TOKEN missing or too short (runner.env)")
    task = Task()
    browser = BrowserUpstream(f"http://127.0.0.1:{int(env.get('CAREEROPS_MCP_PORT_ATS') or 8932)}/mcp")
    public = ThreadingHTTPServer((env.get("CAREEROPS_BRIDGE_HOST") or "172.26.0.1", int(env.get("CAREEROPS_BRIDGE_PORT") or 18933)),
                                 make_public_handler(task, token, browser))
    control = ThreadingHTTPServer(("127.0.0.1", int(env.get("CAREEROPS_BRIDGE_CONTROL_PORT") or 18934)),
                                  make_control_handler(task, token, lambda: ats_helpers.load_runtime_env(runner.load_env()), browser))
    for srv in (public, control):
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    return public, control, task


def main() -> int:
    public, control, _ = serve()
    print(f"careerops bridge on {public.server_address} (control {control.server_address})", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
