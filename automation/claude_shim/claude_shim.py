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
import re
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


# Model "hermes-vision" (2026-11-19): the CAPTCHA solver's image questions. The messages go as they are (with the image)
# to Lolo's API, pinned to a free Nous model that sees images; nothing is flattened to text.
VISION_MODEL = os.environ.get("HERMES_VISION_MODEL", "tencent/hy4-flash:free")
VISION_PROVIDER = os.environ.get("HERMES_VISION_PROVIDER", "nous")


LOCAL_VISION_TIMEOUT = int(os.environ.get("LOCAL_VISION_TIMEOUT", "45"))   # the S22's E4B answers a grid in 15-19 s


def run_local_vision(messages: list, env: dict) -> str:
    """A local OpenAI-compatible vision model first, when the runner env names one (CAREEROPS_VISION_LOCAL_URL/_KEY/_MODEL,
    e.g. the S22's Gemma once its server takes images): seconds instead of the free tier's 15-130 s. An answer with no
    [list] (2026-11-19: the S22 server is text-only and says "Please provide the picture") counts as none."""
    import urllib.request
    url = env.get("CAREEROPS_VISION_LOCAL_URL")
    if not url:
        return ""
    # the S22's Gemma ignores a system message and writes prose; with the picture first and the format asked at the end of
    # the user's text it answers with the list (2026-11-19, E4B: "[1, 3, 7]" instead of a paragraph)
    images, texts = [], []
    for m in messages:
        if m.get("role") != "user":
            continue
        parts = m.get("content") if isinstance(m.get("content"), list) else [{"type": "text", "text": str(m.get("content") or "")}]
        for c in parts:
            (images if c.get("type") == "image_url" else texts).append(c)
    question = " ".join(str(c.get("text") or "") for c in texts).strip()
    local_messages = [{"role": "user", "content": images + [{"type": "text", "text": question +
                       "\nReply with ONLY the cell numbers as a JSON list, like [2, 6]. [] if none. No other words."}]}]
    body = {"model": env.get("CAREEROPS_VISION_LOCAL_MODEL") or "local", "messages": local_messages, "temperature": 0, "max_tokens": 40}
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": f"Bearer {env.get('CAREEROPS_VISION_LOCAL_KEY') or ''}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=LOCAL_VISION_TIMEOUT) as res:
            data = json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"local vision failed: {e}", flush=True)
        return ""
    text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    # only a list counts: numbers in prose may be the ones it repeats from the question ("cells 1-9")
    m = re.search(r"\[[\d,\s]*\]", text)
    return m.group(0) if m else ""


def run_hermes_vision(messages: list) -> str:
    import urllib.request
    env = _hermes_env()
    local = run_local_vision([m for m in (messages or []) if isinstance(m, dict)], env)
    if local:
        return local
    url, key = env.get("CAREEROPS_HERMES_URL"), env.get("CAREEROPS_HERMES_KEY")
    if not url or not key:
        raise RuntimeError("Hermes not configured (CAREEROPS_HERMES_URL/KEY in the runner env)")
    rules = HERMES_RULES + " You can see the image in the message."
    msgs = [{"role": "system", "content": rules}] + [m for m in (messages or []) if isinstance(m, dict)]
    body = {"model": VISION_MODEL, "provider": VISION_PROVIDER, "messages": msgs, "stream": False,
            "model_options": {"reasoning_effort": "none"}}   # 13 s vs 15 s an image, same answers (2026-11-19)
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with _hermes_slots:
        with urllib.request.urlopen(req, timeout=HERMES_TIMEOUT) as res:
            data = json.loads(res.read().decode("utf-8"))
    text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError(f"Hermes vision gave no text: {str(data)[:200]}")
    return text


# Model "captcha-reason" (2026-11-19): hcaptcha-challenger's questions (screenshots + its instructions + a JSON schema). The
# library is built for Gemini's spatial reasoning; the small models answer, but rarely right. In order:
# 1. Gemini, when the runner env has CAREEROPS_CAPTCHA_GEMINI_KEY (model CAREEROPS_CAPTCHA_GEMINI_MODEL, default below),
#    through Google's OpenAI-compatible endpoint;
# 1b. the Nous Portal through Lolo (below);
# 2. any OpenAI-compatible vision model: CAREEROPS_CAPTCHA_REASON_URL/_MODEL/_KEY (OpenRouter, a local server…);
# 3. the S22 (CAREEROPS_VISION_LOCAL_*). Lolo's free model is left out: 15-130 s a call, too slow for these.
GEMINI_OPENAI = "https://generativelanguage.googleapis.com/v1beta/openai"
CAPTCHA_GEMINI_MODEL = "gemini-2.5-flash"
CAPTCHA_NOUS_MODEL = "google/gemini-4-argon"   # 2026-11-19 demo: its clicks looked right (3.8 Flash missed); 60-100 s a call
REASON_TIMEOUT = int(os.environ.get("CAPTCHA_REASON_TIMEOUT", "120"))


def _openai_chat(url: str, key: str, body: dict, timeout: int) -> str:
    import urllib.request
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        data = json.loads(res.read().decode("utf-8"))
    return (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()


def run_captcha_reason(messages: list) -> str:
    env = _hermes_env()
    msgs = [m for m in (messages or []) if isinstance(m, dict)]
    tried = []
    routes = []
    if env.get("CAREEROPS_CAPTCHA_GEMINI_KEY"):
        routes.append(("gemini", GEMINI_OPENAI, env["CAREEROPS_CAPTCHA_GEMINI_KEY"],
                       env.get("CAREEROPS_CAPTCHA_GEMINI_MODEL") or CAPTCHA_GEMINI_MODEL))
    # 2026-11-19: the Nous Portal's models through Lolo's API (its key stays with Lolo), Gemini by default: the user has
    # credit there. CAREEROPS_CAPTCHA_NOUS_MODEL=off skips it.
    nous_model = env.get("CAREEROPS_CAPTCHA_NOUS_MODEL") or CAPTCHA_NOUS_MODEL
    if env.get("CAREEROPS_HERMES_URL") and env.get("CAREEROPS_HERMES_KEY") and nous_model.lower() != "off":
        routes.append(("nous", env["CAREEROPS_HERMES_URL"].rstrip("/") + "/v1", env["CAREEROPS_HERMES_KEY"], nous_model))
    if env.get("CAREEROPS_CAPTCHA_REASON_URL"):
        routes.append(("reason", env["CAREEROPS_CAPTCHA_REASON_URL"], env.get("CAREEROPS_CAPTCHA_REASON_KEY") or "",
                       env.get("CAREEROPS_CAPTCHA_REASON_MODEL") or "default"))
    for name, url, key, model in routes:
        body = {"model": model, "messages": msgs, "temperature": 0}
        if name == "gemini":
            body["reasoning_effort"] = env.get("CAREEROPS_CAPTCHA_GEMINI_EFFORT") or "medium"
        elif name == "nous":
            body.update(provider="nous", stream=False, model_options={"reasoning_effort": env.get("CAREEROPS_CAPTCHA_NOUS_EFFORT") or "medium"})
            body["messages"] = [{"role": "system", "content": HERMES_RULES + " You can see the images in the message."}] + msgs
        try:
            text = _openai_chat(url, key, body, REASON_TIMEOUT)
            if text:
                return text
            tried.append(f"{name}: empty")
        except Exception as e:
            tried.append(f"{name}: {str(e)[:120]}")
            print(f"captcha reason via {name} failed: {e}", flush=True)
    # the S22: picture first, the instruction (with the schema) at the end of the user's text, no system message
    if env.get("CAREEROPS_VISION_LOCAL_URL"):
        system = " ".join(str(m.get("content") or "") for m in msgs if m.get("role") == "system")
        images, texts = [], []
        for m in msgs:
            if m.get("role") == "user":
                for c in (m.get("content") if isinstance(m.get("content"), list) else [{"type": "text", "text": str(m.get("content") or "")}]):
                    (images if c.get("type") == "image_url" else texts).append(c)
        question = (system[:6000] + "\n\n" + " ".join(str(c.get("text") or "") for c in texts)).strip()
        body = {"model": env.get("CAREEROPS_VISION_LOCAL_MODEL") or "local", "temperature": 0, "max_tokens": 800,
                "messages": [{"role": "user", "content": images + [{"type": "text", "text": question}]}]}
        try:
            text = _openai_chat(env["CAREEROPS_VISION_LOCAL_URL"], env.get("CAREEROPS_VISION_LOCAL_KEY") or "", body,
                                max(LOCAL_VISION_TIMEOUT, 60))
            if "{" in text:
                return text
            tried.append("s22: no JSON")
        except Exception as e:
            tried.append(f"s22: {str(e)[:120]}")
    raise RuntimeError("no captcha model answered (" + "; ".join(tried) + ")" if tried else "no captcha model configured")


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
            if model_id == "hermes-vision":
                text = run_hermes_vision(body.get("messages"))
            elif model_id == "captcha-reason":
                text = run_captcha_reason(body.get("messages"))
            elif model_id.startswith("hermes"):
                text = run_hermes(render(body.get("messages")))
            else:
                text = run_claude(render(body.get("messages")), model_id)
        except Exception as e:
            who = "hermes" if str(model_id).startswith("hermes") else ("captcha" if model_id == "captcha-reason" else "claude")
            return self._send(502, {"error": {"message": f"{who}: {e}", "type": "upstream_error"}})
        self._send(200, {"id": f"chatcmpl-{uuid.uuid4().hex[:12]}", "object": "chat.completion", "created": int(time.time()), "model": model_id,
                         "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]})

    def log_message(self, fmt, *args):
        print(f"{self.log_date_time_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("CLAUDE_SHIM_TOKEN (or AGY_SHIM_TOKEN) is required")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
