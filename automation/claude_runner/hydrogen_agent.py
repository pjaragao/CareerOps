"""Gemini 4 Hydrogen fallback/alternate agent driving Playwright MCP over Streamable HTTP."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import ats_helpers


VALID_STATUSES = {"done", "needs_user", "job_closed", "already_applied"}
MAX_STEPS = 40
DEFAULT_AGY_URL = "http://172.26.0.1:8787/v1"
DEFAULT_MODELS = ("gemini-4-hydrogen-low", "gemini-4-hydrogen-medium", "gemini-3.8-flash-high", "gemini-flash-latest")


class McpHttpClient:
    """Minimal Streamable HTTP client for playwright-mcp."""

    def __init__(self, url: str):
        self.url = url
        self.session_id: Optional[str] = None
        self._req_id = 0

    def _post(self, method: str, params: Optional[Dict[str, Any]] = None, notify: bool = False) -> Any:
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not notify:
            self._req_id += 1
            payload["id"] = self._req_id
        if params is not None:
            payload["params"] = params
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            if not self.session_id:
                self.session_id = resp.headers.get("Mcp-Session-Id")
            raw = resp.read().decode("utf-8", "ignore")
            if notify or not raw.strip():
                return {}
            return self._parse_mcp_body(raw)

    @staticmethod
    def _parse_mcp_body(raw: str) -> Dict[str, Any]:
        stripped = raw.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
        last: Dict[str, Any] = {}
        for line in stripped.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk and chunk != "[DONE]":
                    try:
                        last = json.loads(chunk)
                    except ValueError:
                        pass
        return last

    def __enter__(self) -> "McpHttpClient":
        self._post("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "careerops-hydrogen", "version": "1.0"},
        })
        self._post("notifications/initialized", notify=True)
        return self

    def list_tools(self) -> List[Dict[str, Any]]:
        res = self._post("tools/list", {})
        return ((res.get("result") or {}).get("tools") or [])

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Tuple[str, bool]:
        res = self._post("tools/call", {"name": name, "arguments": arguments})
        if res.get("error"):
            return json.dumps(res["error"]), True
        r = res.get("result") or {}
        parts = []
        for item in r.get("content") or []:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            elif isinstance(item, dict):
                parts.append(json.dumps(item))
        return "\n".join(parts) or json.dumps(r), bool(r.get("isError"))

    def __exit__(self, *args: Any) -> None:
        if self.session_id:
            req = urllib.request.Request(self.url, headers={"Mcp-Session-Id": self.session_id}, method="DELETE")
            try:
                urllib.request.urlopen(req, timeout=5).close()
            except Exception:
                pass


def _to_openai_tool(name: str, description: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    clean_schema = dict(schema or {"type": "object", "properties": {}})
    clean_schema.pop("$schema", None)
    clean_schema.pop("additionalProperties", None)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": (description or "")[:600],
            "parameters": clean_schema,
        },
    }


def _trim_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keeps system/user messages and only the latest 2 bulky tool outputs in full."""
    tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    keep_full = set(tool_indices[-2:])
    trimmed: List[Dict[str, Any]] = []
    for i, m in enumerate(messages):
        if m.get("role") != "tool" or i in keep_full:
            content = str(m.get("content") or "")
            if m.get("role") == "tool" and len(content) > 16000:
                trimmed.append({**m, "content": content[:16000] + "\n...[truncated]..."})
            else:
                trimmed.append(m)
        else:
            content = str(m.get("content") or "")
            if len(content) > 600:
                trimmed.append({**m, "content": content[:400] + "\n...[earlier snapshot compressed]..."})
            else:
                trimmed.append(m)
    return trimmed


def _extract_final_json(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.S)
    candidate = fenced.group(1) if fenced else raw
    if not candidate.startswith("{"):
        m = re.search(r"\{.*\}", candidate, re.S)
        if m:
            candidate = m.group(0)
    try:
        parsed = json.loads(candidate)
    except ValueError:
        return None
    if isinstance(parsed, dict) and parsed.get("status") in VALID_STATUSES:
        return parsed
    return None


def _chat_completion(base_url: str, token: str, model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.1,
    }
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{url}/chat/completions", data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def _local_careerops_tools() -> List[Dict[str, Any]]:
    return [
        _to_openai_tool(
            "careerops_check_email",
            "Search Gmail & CareerOps DB for a verification OTP code, magic link, or password reset email.",
            {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "query": {"type": "string"},
                    "since_minutes": {"type": "integer"},
                },
                "required": ["domain"],
            },
        ),
        _to_openai_tool(
            "careerops_site_account",
            "Get, create, or update persistent ATS portal login credentials in CareerOps.",
            {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "enum": ["get", "get_or_create", "update"]},
                    "domain": {"type": "string"},
                    "email": {"type": "string"},
                    "password": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["op", "domain"],
            },
        ),
    ]


def run_hydrogen_agent(
    action: Dict[str, Any],
    prompt: str,
    mcp_url: str,
    allowed_playwright_tools: List[str],
    env: Dict[str, str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Executes one stuck automation action using Gemini 4 Hydrogen + Playwright MCP."""
    cfg = ats_helpers.load_runtime_env(env)
    base_url = cfg.get("CAREEROPS_HYDROGEN_BASE_URL") or cfg.get("AGY_SHIM_URL") or cfg.get("AGY_BASE_URL") or DEFAULT_AGY_URL
    token = cfg.get("CAREEROPS_HYDROGEN_TOKEN") or cfg.get("AGY_SHIM_TOKEN") or ""
    primary_model = cfg.get("CAREEROPS_HYDROGEN_MODEL") or DEFAULT_MODELS[0]
    models = (primary_model,) + tuple(m for m in DEFAULT_MODELS if m != primary_model)

    lane = action.get("lane", "")
    seeded_hosts = ats_helpers.allowed_hosts_for_action(action)
    tool_calls_log: List[Dict[str, Any]] = []
    helper_calls_log: List[Dict[str, Any]] = []
    violations: List[str] = []
    t0 = time.monotonic()

    with McpHttpClient(mcp_url) as mcp:
        offered = mcp.list_tools()
        openai_tools = [
            _to_openai_tool(t["name"], t.get("description", ""), t.get("inputSchema") or {})
            for t in offered
            if t.get("name") in allowed_playwright_tools
        ]
        if lane == "ats":
            openai_tools.extend(_local_careerops_tools())

        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You automate ONE browser job task cleanly. You may batch multiple browser_type or browser_select_option "
                    "calls targeting the same snapshot in one turn to save turns, then verify with browser_snapshot. "
                    "Use one navigation/submit click at a time. "
                    "When completely finished or blocked, respond WITHOUT tool calls using strictly this JSON object:\n"
                    '{"status": "done"|"needs_user"|"job_closed"|"already_applied", "summary": "...", "questions": []}'
                ),
            },
            {"role": "user", "content": prompt},
        ]

        final_answer: Optional[Dict[str, Any]] = None
        last_text = ""
        used_model = models[0]
        turns = 0

        for step in range(MAX_STEPS):
            turns = step + 1
            resp = None
            last_err: Optional[Exception] = None
            for cand_model in models:
                for attempt in range(2):
                    try:
                        resp = _chat_completion(base_url, token, cand_model, _trim_messages(messages), openai_tools)
                        used_model = cand_model
                        break
                    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
                        last_err = exc
                        transient = (
                            exc.code in (429, 500, 502, 503, 504)
                            if isinstance(exc, urllib.error.HTTPError)
                            else isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError))
                        )
                        if attempt == 0 and transient:
                            time.sleep(1.5)
                            continue
                        break
                if resp is not None:
                    break
            if resp is None:
                raise RuntimeError(f"Hydrogen upstream failed: {last_err}")

            choice = (resp.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            content = str(msg.get("content") or "")
            calls = msg.get("tool_calls") or []
            if content:
                last_text = content

            if not calls:
                final_answer = _extract_final_json(content)
                if final_answer or step >= MAX_STEPS - 2:
                    break
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": 'Return strictly valid JSON: {"status": "done"|"needs_user"|"job_closed"|"already_applied", "summary": "...", "questions": []}',
                })
                continue

            messages.append({"role": "assistant", "content": content or None, "tool_calls": calls})
            for call in calls:
                fn = call.get("function") or {}
                tname = str(fn.get("name") or "")
                try:
                    targs = json.loads(fn.get("arguments") or "{}")
                    if not isinstance(targs, dict):
                        targs = {}
                except ValueError:
                    targs = {}

                if tname == "careerops_check_email" and lane == "ats":
                    helper_calls_log.append({"tool": "mcp__careerops__check_email", "input": targs})
                    out = json.dumps(ats_helpers.check_email_verification(
                        domain=str(targs.get("domain") or ""),
                        query=str(targs.get("query") or ""),
                        since_minutes=int(targs.get("since_minutes") or 20),
                        env=cfg,
                    ), ensure_ascii=False)
                elif tname == "careerops_site_account" and lane == "ats":
                    helper_calls_log.append({"tool": "mcp__careerops__site_account", "input": targs})
                    out = json.dumps(ats_helpers.manage_site_account(
                        op=str(targs.get("op") or "get"),
                        domain=str(targs.get("domain") or ""),
                        email=str(targs.get("email") or ""),
                        password=str(targs.get("password") or ""),
                        notes=str(targs.get("notes") or ""),
                        env=cfg,
                    ), ensure_ascii=False)
                elif tname in allowed_playwright_tools:
                    if tname == "browser_navigate":
                        nav_host = urllib.parse.urlparse(str(targs.get("url") or "")).hostname
                        if not ats_helpers.is_host_allowed(nav_host, lane, seeded_hosts):
                            violations.append(f"navigation to {targs.get('url')}")
                            out = f"Blocked: host {nav_host} is not allowed for lane {lane}"
                            messages.append({"role": "tool", "tool_call_id": call.get("id") or "call", "content": out})
                            continue
                    tool_calls_log.append({"tool": f"mcp__playwright__{tname}", "input": targs})
                    out, _is_err = mcp.call_tool(tname, targs)
                else:
                    violations.append(f"tool {tname} outside the allowed set")
                    out = f"Blocked: tool {tname} is not allowed"

                messages.append({"role": "tool", "tool_call_id": call.get("id") or "call", "content": out[:16000]})

    duration_ms = int((time.monotonic() - t0) * 1000)
    transcript: Dict[str, Any] = {
        "provider": used_model,
        "duration_ms": duration_ms,
        "turns": turns,
        "tools": tool_calls_log,
        "helper_tools": helper_calls_log,
        "violations": violations,
    }
    if violations:
        return {"status": "failed", "summary": f"Hydrogen audit stopped the run: {violations[0]}", "questions": []}, transcript
    if not final_answer:
        return {"status": "needs_user", "summary": (last_text or "Hydrogen finished without a valid status payload.")[:2500], "questions": []}, transcript
    return {
        "status": final_answer["status"],
        "summary": str(final_answer.get("summary") or "")[:2500],
        "questions": final_answer.get("questions") or [],
    }, transcript
