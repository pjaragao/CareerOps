#!/usr/bin/env python3
"""OpenAI-compatible shim in front of the Claude Code CLI, so the backend (a container, with no `claude`) can write
documents (CV, cover letter, CV review) with Claude Sonnet 5.5 at medium effort on the Claude subscription, not on AGY.

Each request is ONE stateless `claude -p` run in an empty temp dir with every tool disabled: text in, text out.
Model ids are `<model>[-<effort>]`, e.g. `claude-sonnet-5-5-medium` -> --model claude-sonnet-5-5 --effort medium.
Listens on the docker bridge (default 172.26.0.1:8788); bearer token required (CLAUDE_SHIM_TOKEN, else AGY_SHIM_TOKEN).
"""
from __future__ import annotations

import hmac
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("CLAUDE_SHIM_HOST", "172.26.0.1")
PORT = int(os.environ.get("CLAUDE_SHIM_PORT", "8788"))
TOKEN = os.environ.get("CLAUDE_SHIM_TOKEN") or os.environ.get("AGY_SHIM_TOKEN", "")
CLAUDE = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
DEFAULT_MODEL = os.environ.get("CLAUDE_SHIM_MODEL", "claude-sonnet-5-5-medium")
TIMEOUT = int(os.environ.get("CLAUDE_SHIM_TIMEOUT", "420"))
EFFORTS = ("low", "medium", "high", "xhigh", "max")
_slots = threading.Semaphore(int(os.environ.get("CLAUDE_SHIM_PARALLEL", "3")))


def split_model(model_id: str) -> tuple:
    name, _, tail = (model_id or DEFAULT_MODEL).rpartition("-")
    return (name, tail) if tail in EFFORTS and name else (model_id or DEFAULT_MODEL, "")


def render(messages: list) -> str:
    parts = []
    for m in messages or []:
        content = m.get("content")
        if isinstance(content, list):
            content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
        parts.append(str(content or ""))
    return "\n\n".join(p for p in parts if p)


def run_claude(prompt: str, model_id: str) -> str:
    model, effort = split_model(model_id)
    cmd = [CLAUDE, "-p", prompt, "--model", model, "--tools", "", "--no-session-persistence", "--output-format", "json"]
    if effort:
        cmd += ["--effort", effort]
    with _slots, tempfile.TemporaryDirectory(prefix="claude-shim-") as cwd:
        done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT)
    try:
        data = json.loads(done.stdout)
    except ValueError:
        raise RuntimeError(f"claude exit {done.returncode}: {(done.stderr or done.stdout)[:300]}")
    if data.get("is_error") or not (data.get("result") or "").strip():
        raise RuntimeError(f"claude error: {str(data.get('result') or data)[:300]}")
    return data["result"].strip()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self) -> bool:
        got = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        return bool(TOKEN) and hmac.compare_digest(got, TOKEN)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True})
        if not self._authorized():
            return self._send(401, {"error": {"message": "unauthorized"}})
        if self.path.rstrip("/") == "/v1/models":
            return self._send(200, {"object": "list", "data": [{"id": f"claude-sonnet-5-5-{e}", "object": "model"} for e in ("low", "medium", "high")]})
        self._send(404, {"error": {"message": "not found"}})

    def do_POST(self):
        if not self._authorized():
            return self._send(401, {"error": {"message": "unauthorized"}})
        if self.path.rstrip("/") != "/v1/chat/completions":
            return self._send(404, {"error": {"message": "not found"}})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            model_id = body.get("model") or DEFAULT_MODEL
            text = run_claude(render(body.get("messages")), model_id)
        except Exception as e:
            return self._send(502, {"error": {"message": f"claude: {e}", "type": "upstream_error"}})
        self._send(200, {"id": f"chatcmpl-{uuid.uuid4().hex[:12]}", "object": "chat.completion", "created": int(time.time()), "model": model_id,
                         "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]})

    def log_message(self, fmt, *args):
        print(f"{self.log_date_time_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("CLAUDE_SHIM_TOKEN (or AGY_SHIM_TOKEN) is required")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
