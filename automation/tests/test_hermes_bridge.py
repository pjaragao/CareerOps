"""Lolo's Hermes as the first apply agent (2026-11-16): the bridge refuses what the audit would flag BEFORE it runs, logs
every call, and the runner reads Hermes's run like a Claude run."""
import json
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "claude_runner"))

import hermes_agent  # noqa: E402
import mcp_bridge  # noqa: E402
import run  # noqa: E402

ACTION = {"id": 7, "run_id": 70, "kind": "apply", "lane": "ats", "target_url": "https://boards.greenhouse.io/acme/jobs/1",
          "dossier": {"files": {"resume": "/data/run/7/cv.pdf"}}}
TOKEN = "t" * 32


def test_guard_refuses_without_a_task_and_off_target():
    assert mcp_bridge.guard(None, "mcp__playwright__browser_click", {}) == "nenhuma tarefa aberta pelo CareerOps"
    assert mcp_bridge.guard(ACTION, "mcp__playwright__browser_click", {"ref": "e1"}) is None
    assert mcp_bridge.guard(ACTION, "mcp__playwright__browser_navigate", {"url": "https://boards.greenhouse.io/acme/jobs/1"}) is None
    assert "fora do alvo" in mcp_bridge.guard(ACTION, "mcp__playwright__browser_navigate", {"url": "https://www.linkedin.com/feed/"})
    assert "não permitida" in mcp_bridge.guard(ACTION, "mcp__playwright__browser_evaluate", {"function": "() => 1"})
    assert "outro arquivo" in mcp_bridge.guard(ACTION, "mcp__playwright__browser_file_upload", {"paths": ["/etc/passwd"]})
    assert mcp_bridge.guard(ACTION, "mcp__careerops__check_email", {"domain": "greenhouse.io"}) is None


def test_hermes_ends_only_on_a_real_outcome():
    assert run.hermes_ends({"status": "done"}) and run.hermes_ends({"status": "job_closed"})
    assert run.hermes_ends({"status": "needs_user", "questions": [{"label": "Salary?"}]})
    assert not run.hermes_ends({"status": "needs_user", "questions": []})
    assert not run.hermes_ends({"status": "failed"})
    assert run.hermes_ends({"status": "failed", "audit_flags": ["x"]})


def test_hermes_run_reads_like_a_claude_run():
    calls = [{"name": "mcp__playwright__browser_snapshot", "input": {}},
             {"name": "mcp__playwright__browser_navigate", "input": {"url": "https://www.linkedin.com/feed/"}, "refused": True}]
    status = {"status": "completed", "output": 'ok ```json\n{"status": "done", "summary": "Enviado"}\n```',
              "usage": {"input_tokens": 900, "output_tokens": 40}, "runtime": {"model": "tencent/hy4-flash:free"}}
    res = run.outcome(hermes_agent.to_parsed(calls, status), 0, ACTION)
    assert res["status"] == "done" and res["summary"].startswith("Enviado")
    assert res["audit_flags"] == []                      # the refused call did nothing
    assert "mcp__playwright__browser_navigate" in res["transcript"]["refused"]
    assert res["usage"]["input_tokens"] == 900 and "hermes:tencent/hy4-flash:free" in res["usage"]["model"]
    failed = run.outcome(hermes_agent.to_parsed([], {"status": "failed", "error": "rate limit"}), 1, ACTION)
    assert failed["status"] == "failed"


class FakeBrowser(BaseHTTPRequestHandler):
    """A Playwright MCP stand-in: answers initialize, tools/list and tools/call in SSE like the real one."""
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if req.get("id") is None:
            self.send_response(202); self.end_headers(); return
        if req["method"] == "tools/list":
            result = {"tools": [{"name": n, "inputSchema": {"type": "object"}} for n in ("browser_click", "browser_evaluate", "browser_snapshot")]}
        elif req["method"] == "tools/call":
            FakeBrowser.seen.append(req["params"]["name"])
            result = {"content": [{"type": "text", "text": "clicked"}]}
        else:
            result = {}
        body = f"event: message\ndata: {json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': result})}\n\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Mcp-Session-Id", "s1")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _post(url, body, token=TOKEN):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def test_bridge_end_to_end(tmp_path, monkeypatch):
    up = ThreadingHTTPServer(("127.0.0.1", 0), FakeBrowser)
    threading.Thread(target=up.serve_forever, daemon=True).start()
    monkeypatch.setattr(mcp_bridge, "TOOLS_CACHE", tmp_path / "tools.json")
    env = {"CAREEROPS_BRIDGE_TOKEN": TOKEN, "CAREEROPS_BRIDGE_HOST": "127.0.0.1", "CAREEROPS_BRIDGE_PORT": "0",
           "CAREEROPS_BRIDGE_CONTROL_PORT": "0", "CAREEROPS_MCP_PORT_ATS": str(up.server_address[1])}
    public, control, tasks = mcp_bridge.serve(env)
    pub = f"http://127.0.0.1:{public.server_address[1]}"
    ctl = f"http://127.0.0.1:{control.server_address[1]}"
    try:
        # only the runner's tools are listed; a wrong token gets nothing
        listed = _post(f"{pub}/browser/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
        assert [t["name"] for t in listed] == ["browser_click", "browser_snapshot"]
        try:
            _post(f"{pub}/browser/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, token="x" * 32)
            assert False, "a wrong token must be refused"
        except urllib.error.HTTPError as e:
            assert e.code == 401
        click = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "browser_click", "arguments": {"ref": "e1"}}}
        # no task open: refused, nothing reaches the browser
        assert _post(f"{pub}/browser/mcp", click)["result"]["isError"] and FakeBrowser.seen == []
        _post(f"{ctl}/run", {"action": ACTION})
        assert _post(f"{pub}/browser/mcp", click)["result"]["content"][0]["text"] == "clicked"
        other = _post(f"{pub}/linkedin/mcp", click)["result"]
        assert other["isError"] and "REFUSED" in other["content"][0]["text"]   # no LinkedIn task open
        evil = {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "browser_evaluate", "arguments": {"function": "x"}}}
        assert "REFUSED" in _post(f"{pub}/browser/mcp", evil)["result"]["content"][0]["text"]
        assert FakeBrowser.seen == ["browser_click"]
        calls = _post(f"{ctl}/end", {"lane": "ats"})["calls"]
        assert [(c["name"], c["refused"]) for c in calls] == [("mcp__playwright__browser_click", False), ("mcp__playwright__browser_evaluate", True)]
        assert tasks["ats"].action is None and tasks["linkedin"].action is None
    finally:
        public.shutdown(); control.shutdown(); up.shutdown()


def test_snapshot_compaction_keeps_every_named_ref():
    snap = "\n".join([
        "### Page", "- Page URL: https://jobs.example.com/apply?" + "x" * 300,
        "- generic [ref=e1]:", "  - generic [ref=e2]:", "    - emphasis [ref=e3]", "    - generic [ref=e4]: ",
        '    - textbox "First name" [ref=e5] [cursor=pointer]', '    - button "Submit application" [ref=e6] [cursor=pointer]:',
        "    - generic [ref=e7]: Required", '    - img "Company logo" [ref=e8]'])
    out = mcp_bridge.compact(snap)
    for ref in ("e5", "e6", "e7", "e8"):
        assert f"ref={ref}]" in out
    for ref in ("e1", "e2", "e3", "e4"):
        assert f"ref={ref}]" not in out
    assert "[cursor=pointer]" not in out and "x" * 100 not in out
    long = mcp_bridge.compact("\n".join(f'- button "b{i}" [ref=e{i}]' for i in range(5000)))
    assert len(long) < mcp_bridge.SNAPSHOT_MAX + 300 and "browser_find" in long


def test_tool_schemas_are_slim_but_complete():
    click = {"name": "browser_click", "description": "Perform click on a web page",
             "inputSchema": {"$schema": "x", "type": "object", "additionalProperties": False, "required": ["target"],
                             "properties": {"target": {"type": "string", "description": "Exact target element reference from the page snapshot, or a unique element selector"},
                                            "doubleClick": {"type": "boolean"}, "modifiers": {"type": "array"}}},
             "annotations": {"title": "Click"}}
    slim = mcp_bridge.slim_tool(click)
    assert slim == {"name": "browser_click", "description": "Perform click on a web page",
                    "inputSchema": {"type": "object", "properties": {"target": {"type": "string", "description": "ref from the snapshot, e.g. e12"}},
                                    "required": ["target"]}}


def _fake_action(**kw):
    return {**ACTION, "dossier": {"kind": "apply", "files": {"resume": "/data/run/7/cv.pdf"}}, **kw}


def test_hermes_tokens_stay_off_the_budget_and_wait_for_claude_during_the_breaker(monkeypatch):
    status = {"status": "completed", "output": '{"status": "needs_user", "summary": "parei", "questions": []}',
              "usage": {"input_tokens": 50000, "output_tokens": 900}}
    monkeypatch.setattr(run.hermes_agent, "configured", lambda env: True)
    monkeypatch.setattr(run.hermes_agent, "bridge_ready", lambda env: True)
    monkeypatch.setattr(run.hermes_agent, "run_hermes", lambda *a, **k: (hermes_agent.to_parsed([], status), 0))
    monkeypatch.setattr(run.ats_helpers, "probe_mcp_http", lambda *a, **k: True)
    monkeypatch.setattr(run, "server_tools", lambda port: ["browser_click"])
    res, _ = run._run_action(_fake_action(claude_paused=True), {"CAREEROPS_RUNNER_PROVIDER": "auto"})
    assert res["status"] == "deferred"                                    # Claude takes it after the pause
    assert not any(res["usage"].get(k) for k in ("input_tokens", "output_tokens"))   # free tokens: not in the budget
    assert res["transcript"]["hermes_usage"]["input_tokens"] == 50000


def test_hermes_only_never_runs_claude(monkeypatch):
    monkeypatch.setattr(run.hermes_agent, "configured", lambda env: True)
    monkeypatch.setattr(run.hermes_agent, "bridge_ready", lambda env: True)
    monkeypatch.setattr(run.ats_helpers, "probe_mcp_http", lambda *a, **k: True)
    monkeypatch.setattr(run, "server_tools", lambda port: ["browser_click"])
    monkeypatch.setattr(run, "_claude_attempt", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Claude ran")))
    env = {"CAREEROPS_RUNNER_PROVIDER": "hermes"}
    down = {"status": "failed", "error": "Hermes unreachable"}
    monkeypatch.setattr(run.hermes_agent, "run_hermes", lambda *a, **k: (hermes_agent.to_parsed([], down), 1))
    assert run._run_action(_fake_action(), env)[0]["status"] == "deferred"          # Hermes down: later, not to you
    stopped = {"status": "completed", "output": '{"status": "needs_user", "summary": "travou no passo 3", "questions": []}'}
    monkeypatch.setattr(run.hermes_agent, "run_hermes",
                        lambda *a, **k: (hermes_agent.to_parsed([{"name": "mcp__playwright__browser_snapshot"}], stopped), 0))
    assert run._run_action(_fake_action(), env)[0]["status"] == "needs_user"        # it worked and stopped: to you
    other = {**_fake_action(), "lane": "linkedin_read", "kind": "feed_scan"}
    assert run._run_action(other, env)[0]["status"] == "deferred"                   # not Hermes's: never a Claude run
    seen = {}
    monkeypatch.setattr(run.hermes_agent, "run_hermes", lambda action, system, prompt, *a, **k: (seen.update(prompt=prompt) or
                        (hermes_agent.to_parsed([{"name": "mcp__playwright__browser_snapshot"}], stopped), 0)))
    li_apply = {**_fake_action(), "lane": "linkedin_write", "target_url": "https://www.linkedin.com/jobs/view/1/"}
    assert run._run_action(li_apply, env)[0]["status"] == "needs_user"              # LinkedIn applications: Hermes
    assert "Easy Apply" in seen["prompt"]


def test_ask_candidate_waits_for_the_whatsapp_answer(monkeypatch):
    import ats_helpers
    monkeypatch.setattr(ats_helpers, "_api_call", lambda path, body, env, timeout=15: {"answer": "Yes", "source": "saved"})
    assert ats_helpers.ask_candidate(7, "Clean driving record?", [], "text", {})["answer"] == "Yes"
    monkeypatch.setattr(ats_helpers, "_api_call", lambda *a, **k: {"answer": None, "unavailable": "quiet hours"})
    assert ats_helpers.ask_candidate(7, "German?", [], "text", {})["answer"] is None
    monkeypatch.setattr(ats_helpers, "_api_call", lambda *a, **k: {"answer": None, "question_id": 3})
    replies = iter([b'{"answer": null}', b'{"answer": "B1"}'])

    class R:
        def __init__(self): self.body = next(replies)
        def read(self): return self.body
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(ats_helpers.urllib.request, "urlopen", lambda *a, **k: R())
    got = ats_helpers.ask_candidate(7, "German?", ["A1", "B1"], "select", {"CAREEROPS_WORKER_TOKEN": "t"}, wait_seconds=5, poll=0)
    assert got == {"answer": "B1", "source": "candidate (WhatsApp)"}
    assert mcp_bridge.guard(ACTION, "mcp__careerops__ask_candidate", {"question": "x"}) is None


def test_linkedin_applications_get_the_answer_tools_and_stay_on_the_job():
    li = {"id": 8, "kind": "apply", "lane": "linkedin_write", "target_url": "https://www.linkedin.com/jobs/view/42/", "dossier": {}}
    assert mcp_bridge.guard(li, "mcp__careerops__ask_candidate", {"question": "x"}) is None
    assert mcp_bridge.guard(li, "mcp__careerops__check_email", {"domain": "x"})                 # not on LinkedIn
    assert mcp_bridge.guard(li, "mcp__playwright__browser_navigate", {"url": "https://www.linkedin.com/jobs/view/42/"}) is None
    assert mcp_bridge.guard(li, "mcp__playwright__browser_navigate", {"url": "https://www.linkedin.com/feed/"})
    follow = {**li, "kind": "follow"}
    assert mcp_bridge.guard(follow, "mcp__careerops__ask_candidate", {"question": "x"})        # only applications


def test_the_two_lanes_run_in_parallel_each_with_its_own_task(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_bridge, "TOOLS_CACHE", tmp_path / "tools.json")
    env = {"CAREEROPS_BRIDGE_TOKEN": TOKEN, "CAREEROPS_BRIDGE_HOST": "127.0.0.1", "CAREEROPS_BRIDGE_PORT": "0",
           "CAREEROPS_BRIDGE_CONTROL_PORT": "0", "CAREEROPS_MCP_PORT_ATS": "1", "CAREEROPS_MCP_PORT_LINKEDIN": "1"}
    public, control, tasks = mcp_bridge.serve(env)
    ctl = f"http://127.0.0.1:{control.server_address[1]}"
    pub = f"http://127.0.0.1:{public.server_address[1]}"
    try:
        li = {"id": 9, "run_id": 1, "kind": "follow", "lane": "linkedin_write", "target_url": "https://www.linkedin.com/company/acme/", "dossier": {}}
        _post(f"{ctl}/run", {"action": ACTION})
        _post(f"{ctl}/run", {"action": li})
        assert tasks["ats"].action["id"] == 7 and tasks["linkedin"].action["id"] == 9      # both open at once
        ask = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "check_email", "arguments": {"domain": "x"}}}
        out = _post(f"{pub}/careerops-linkedin/mcp", ask)["result"]
        assert out["isError"] and "REFUSED" in out["content"][0]["text"]                     # the LinkedIn task's rules
        assert _post(f"{ctl}/end", {"lane": "linkedin"})["calls"][0]["name"] == "mcp__careerops__check_email"
        assert tasks["ats"].action["id"] == 7                                                 # the other lane untouched
    finally:
        public.shutdown(); control.shutdown()


def test_a_busy_lane_refuses_a_second_task(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_bridge, "TOOLS_CACHE", tmp_path / "tools.json")
    env = {"CAREEROPS_BRIDGE_TOKEN": TOKEN, "CAREEROPS_BRIDGE_HOST": "127.0.0.1", "CAREEROPS_BRIDGE_PORT": "0",
           "CAREEROPS_BRIDGE_CONTROL_PORT": "0", "CAREEROPS_MCP_PORT_ATS": "1", "CAREEROPS_MCP_PORT_LINKEDIN": "1"}
    public, control, tasks = mcp_bridge.serve(env)
    ctl = f"http://127.0.0.1:{control.server_address[1]}"
    try:
        _post(f"{ctl}/run", {"action": ACTION})
        try:
            _post(f"{ctl}/run", {"action": {**ACTION, "id": 70}})
            assert False, "a second task on a busy lane must be refused"
        except urllib.error.HTTPError as e:
            assert e.code == 409
        assert tasks["ats"].action["id"] == 7
    finally:
        public.shutdown(); control.shutdown()


def test_two_company_slots_run_side_by_side(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_bridge, "TOOLS_CACHE", tmp_path / "tools.json")
    env = {"CAREEROPS_BRIDGE_TOKEN": TOKEN, "CAREEROPS_BRIDGE_HOST": "127.0.0.1", "CAREEROPS_BRIDGE_PORT": "0",
           "CAREEROPS_BRIDGE_CONTROL_PORT": "0", "CAREEROPS_MCP_PORT_ATS": "1", "CAREEROPS_MCP_PORT_ATS2": "1", "CAREEROPS_MCP_PORT_LINKEDIN": "1"}
    public, control, tasks = mcp_bridge.serve(env)
    ctl = f"http://127.0.0.1:{control.server_address[1]}"
    try:
        _post(f"{ctl}/run", {"action": ACTION})
        _post(f"{ctl}/run", {"action": {**ACTION, "id": 71}, "slot": "ats2"})
        assert tasks["ats"].action["id"] == 7 and tasks["ats2"].action["id"] == 71
        try:
            _post(f"{ctl}/run", {"action": {**ACTION, "id": 72, "lane": "linkedin_write"}, "slot": "ats2"})
            assert False, "a LinkedIn action never runs in a company-site slot"
        except urllib.error.HTTPError as e:
            assert e.code in (400, 409)
        _post(f"{ctl}/end", {"slot": "ats2"})
        assert tasks["ats2"].action is None and tasks["ats"].action["id"] == 7
    finally:
        public.shutdown(); control.shutdown()


def test_the_runner_slot_picks_its_browser_and_tool_names():
    act = {"lane": "ats"}
    assert hermes_agent.slot_of(act, {}) == "ats" and hermes_agent.slot_of(act, {"CAREEROPS_RUNNER_SLOT": "2"}) == "ats2"
    assert hermes_agent.slot_of({"lane": "linkedin_write"}, {"CAREEROPS_RUNNER_SLOT": "2"}) == "linkedin"
    assert run.mcp_port("ats", {"CAREEROPS_RUNNER_SLOT": "2"}) == 8933 and run.mcp_port("ats", {}) == 8932


def test_apply_runs_ask_lolo_for_the_free_hy4_flash_model():
    assert hermes_agent.model_fields({}) == {"model": "tencent/hy4-flash:free", "provider": "nous"}
    assert hermes_agent.model_fields({"CAREEROPS_HERMES_MODEL": "x/y:free", "CAREEROPS_HERMES_PROVIDER": "openrouter"}) == \
        {"model": "x/y:free", "provider": "openrouter"}
    assert hermes_agent.model_fields({"CAREEROPS_HERMES_MODEL": "default"}) == {}
