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


# Model "hermes" (2026-11-17): the text goes to Lolo's Hermes (a free Nous model), through its API on this host. Its
# address and key come from the CareerOps runner's env (the same file the apply runner reads), so nothing is copied.
HERMES_ENV = os.path.expanduser(os.environ.get("CAREEROPS_RUNNER_ENV", "~/.config/careerops/runner.env"))
HERMES_TIMEOUT = int(os.environ.get("HERMES_SHIM_TIMEOUT", "300"))
_hermes_slots = threading.Semaphore(int(os.environ.get("HERMES_SHIM_PARALLEL", "4")))
HERMES_RULES = ("You are a text engine for CareerOps, not an assistant in a chat. Do NOT call any tool. Read the request "
                "below and answer it directly, in exactly the format it asks for (JSON when it asks for JSON).")


def _hermes_env() -> dict:
    out = {}
    try:
        for line in open(HERMES_ENV, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return out


def run_hermes(prompt: str) -> str:
    import urllib.request
    env = _hermes_env()
    url, key = env.get("CAREEROPS_HERMES_URL"), env.get("CAREEROPS_HERMES_KEY")
    if not url or not key:
        raise RuntimeError("Hermes not configured (CAREEROPS_HERMES_URL/KEY in the runner env)")
    body = {"model": "hermes-agent", "messages": [{"role": "system", "content": HERMES_RULES}, {"role": "user", "content": prompt}],
            "stream": False, "model_options": {"reasoning_effort": "low"}}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with _hermes_slots:
        with urllib.request.urlopen(req, timeout=HERMES_TIMEOUT) as res:
            data = json.loads(res.read().decode("utf-8"))
    text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError(f"Hermes gave no text: {str(data)[:200]}")
    return text


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
            if model_id.startswith("hermes"):
                text = run_hermes(render(body.get("messages")))
            else:
                text = run_claude(render(body.get("messages")), model_id)
        except Exception as e:
            who = "hermes" if str(model_id).startswith("hermes") else "claude"
            return self._send(502, {"error": {"message": f"{who}: {e}", "type": "upstream_error"}})
        self._send(200, {"id": f"chatcmpl-{uuid.uuid4().hex[:12]}", "object": "chat.completion", "created": int(time.time()), "model": model_id,
                         "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]})

    def log_message(self, fmt, *args):
        print(f"{self.log_date_time_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("CLAUDE_SHIM_TOKEN (or AGY_SHIM_TOKEN) is required")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
