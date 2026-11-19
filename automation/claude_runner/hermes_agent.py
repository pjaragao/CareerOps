"""The apply agent on Lolo's Hermes (2026-11-16): Lolo's own agent, on the free Nous model it is configured with, works one
escalated form through the bridge (mcp_bridge.py). The runner keeps everything else: it claims the action, opens it on the
bridge, reads the bridge's log of every call (with full arguments) for the audit, and falls back to the Claude chain when
Hermes does not finish.

Hermes's API server (POST /v1/runs) runs only the bridge's MCP tools on Lolo's `api_server` platform; WhatsApp, cron and
CLI keep `no_mcp`, so the Lolo you talk to never sees the browser."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

TERMINAL = {"completed", "failed", "cancelled", "interrupted", "expired"}

OUTPUT_RULES = """

FINAL ANSWER: when you stop, reply with ONLY one JSON object, no other text:
{"status": "done" | "needs_user" | "job_closed" | "already_applied", "summary": "<what you did and where it stopped, in Portuguese>",
 "questions": [{"label": "<question the candidate must answer>", "type": "text|select|radio|checkbox", "options": ["..."]}]}
TOOL NAMES: here the browser tools are named {browser}X (mcp__playwright__X in the rules above means {browser}X; the other
browser's tools are refused for this task), and the careerops tools {careerops}X (mcp__careerops__X in the rules above).
A tool answer that starts with "REFUSED by CareerOps" did nothing: do not repeat that call."""


def _http(method: str, url: str, token: str, body: Optional[dict] = None, timeout: int = 30) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        raw = res.read().decode("utf-8", "replace")
    return json.loads(raw) if raw.strip() else {}


def configured(env: dict) -> bool:
    return bool(env.get("CAREEROPS_HERMES_URL") and env.get("CAREEROPS_HERMES_KEY") and env.get("CAREEROPS_BRIDGE_TOKEN"))


def bridge_ready(env: dict) -> bool:
    port = int(env.get("CAREEROPS_BRIDGE_CONTROL_PORT") or 18934)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as res:
            return res.status == 200
    except (OSError, ValueError):
        return False


def to_parsed(calls: list, status: dict, model_hint: str = "") -> Dict[str, Any]:
    """The bridge's log and Hermes's run status, in the shape run.outcome() reads (as parse_stream gives for Claude)."""
    out_calls = [{"id": f"h{i}", "name": c.get("name"), "input": c.get("input") or {}, "refused": bool(c.get("refused"))}
                 for i, c in enumerate(calls or [])]
    text = str(status.get("output") or status.get("error") or "")
    from hydrogen_agent import _extract_final_json
    answer = _extract_final_json(text)
    # a run cut at the step limit still says where it stopped: its answer counts (2026-11-17: Workday runs at 60 steps)
    failed = status.get("status") != "completed" and not answer
    usage = status.get("usage") or {}
    runtime = status.get("runtime") or {}
    model = runtime.get("model") or model_hint or "hermes"
    final = {
        "is_error": failed,
        "result": (text or status.get("status") or "")[:3000],
        "structured_output": answer,
        "usage": {"input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
                  "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)},
        "modelUsage": {f"hermes:{model}": {}},
    }
    return {"calls": out_calls, "final": final}


def slot_of(action: dict, env: dict) -> str:
    """The bridge slot of this run: ats, ats2 (the second company-site runner, --slot 2) or linkedin."""
    if action.get("lane") != "ats":
        return "linkedin"
    return "ats2" if str(env.get("CAREEROPS_RUNNER_SLOT") or "1") == "2" else "ats"


# The apply subagent's model (2026-11-19, user: "a parte de apply num subagent com o modelo free da Nous hy4 flash"):
# every apply run asks Lolo for it, while Lolo's own default model (WhatsApp, cron) stays as configured there.
# CAREEROPS_HERMES_MODEL=default gives the runs Lolo's default back.
APPLY_MODEL = "tencent/hy4-flash:free"
APPLY_PROVIDER = "nous"


def model_fields(env: dict) -> dict:
    model = (env.get("CAREEROPS_HERMES_MODEL") or APPLY_MODEL).strip()
    if model.lower() in ("default", "lolo", "off"):
        return {}
    return {"model": model, "provider": (env.get("CAREEROPS_HERMES_PROVIDER") or APPLY_PROVIDER).strip()}


PREFIXES = {"ats": ("mcp__careerops_browser__", "mcp__careerops__"), "ats2": ("mcp__careerops_browser2__", "mcp__careerops2__"),
            "linkedin": ("mcp__careerops_linkedin__", "mcp__careerops_li__")}


def run_hermes(action: dict, system: str, prompt: str, env: dict, timeout_s: int = 480) -> Tuple[Dict[str, Any], int]:
    """(parsed, returncode) like run._claude_attempt. Never raises: a Hermes that is down reads as a failed attempt."""
    base = env["CAREEROPS_HERMES_URL"].rstrip("/")
    key = env["CAREEROPS_HERMES_KEY"]
    bridge = f"http://127.0.0.1:{int(env.get('CAREEROPS_BRIDGE_CONTROL_PORT') or 18934)}"
    btoken = env["CAREEROPS_BRIDGE_TOKEN"]
    status: dict = {}
    calls: list = []
    try:
        slot = slot_of(action, env)
        _http("POST", f"{bridge}/run", btoken, {"action": action, "slot": slot})
    except (OSError, ValueError) as exc:
        return {"calls": [], "final": {"is_error": True, "result": f"bridge unreachable: {exc}"}}, 1
    run_id = ""
    try:
        started = _http("POST", f"{base}/v1/runs", key, {
            "input": prompt + OUTPUT_RULES.replace("{browser}", PREFIXES[slot][0]).replace("{careerops}", PREFIXES[slot][1]),
            "instructions": system,
            "session_id": f"careerops-apply-{action.get('id')}-{action.get('run_id') or int(time.time())}",
            "model_options": {"reasoning_effort": "low"},   # a form needs steps, not long thinking: fewer output tokens
            **model_fields(env),
        })
        run_id = started.get("run_id") or ""
        if not run_id:
            raise ValueError(f"no run_id: {str(started)[:200]}")
        deadline = time.monotonic() + timeout_s
        beat = 0.0
        while time.monotonic() < deadline:
            time.sleep(4)
            if time.monotonic() - beat > 60:   # keeps the action's lease while Hermes works (a long form outlives 12 min)
                beat = time.monotonic()
                try:
                    import ats_helpers
                    ats_helpers._api_call(f"/automation/actions/{int(action['id'])}/heartbeat", {}, env)
                except Exception:
                    pass
            try:
                status = _http("GET", f"{base}/v1/runs/{run_id}", key)
            except (OSError, ValueError):
                continue
            if status.get("status") in TERMINAL:
                break
        else:
            try:
                _http("POST", f"{base}/v1/runs/{run_id}/stop", key, {})
            except (OSError, ValueError):
                pass
            status = {**status, "status": "failed", "error": f"Hermes passou de {timeout_s}s"}
    except (OSError, ValueError) as exc:
        status = {"status": "failed", "error": f"Hermes unreachable: {exc}"}
    finally:
        try:
            calls = _http("POST", f"{bridge}/end", btoken, {"slot": slot_of(action, env)}).get("calls") or []
        except (OSError, ValueError):
            calls = []
    parsed = to_parsed(calls, status, model_fields(env).get("model") or "lolo")
    return parsed, 0 if status.get("status") == "completed" else 1
