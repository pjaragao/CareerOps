"""Tests for external ATS runner extensions: host allowlist, audit separation, MCP tools, S22 helper, and Hydrogen agent."""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "claude_runner"))
import ats_helpers  # noqa: E402
import hydrogen_agent  # noqa: E402
import run  # noqa: E402


ATS_ACTION = {
    "id": 99,
    "run_id": 12,
    "kind": "apply",
    "lane": "ats",
    "target_url": "https://company-careers.example.com/jobs/123",
    "dossier": {
        "job": {"url": "https://jobs.ashbyhq.com/acme/123"},
        "files": {"resume": "/tmp/careerops-run/99/cv.pdf"},
    },
}

LI_ACTION = {
    "id": 100,
    "run_id": 13,
    "kind": "follow",
    "lane": "linkedin_write",
    "target_url": "https://www.linkedin.com/in/example/",
    "dossier": {"files": {}},
}


def test_ats_audit_allows_known_ats_portals_and_blocks_evil_or_linkedin():
    ok_calls = [
        {"name": "mcp__playwright__browser_navigate", "input": {"url": "https://jobs.ashbyhq.com/acme/apply"}},
        {"name": "mcp__playwright__browser_navigate", "input": {"url": "https://wd5.myworkdayjobs.com/acme/job/1"}},
        {"name": "mcp__playwright__browser_navigate", "input": {"url": "https://apply.company-careers.example.com/start"}},
        {"name": "mcp__careerops__site_account", "input": {"op": "get_or_create", "domain": "wd5.myworkdayjobs.com"}},
        {"name": "mcp__careerops__check_email", "input": {"domain": "jobs.ashbyhq.com"}},
    ]
    assert run.audit(ok_calls, ATS_ACTION) == []

    bad_evil = [{"name": "mcp__playwright__browser_navigate", "input": {"url": "https://evil.example/steal"}}]
    assert len(run.audit(bad_evil, ATS_ACTION)) == 1

    bad_li = [{"name": "mcp__playwright__browser_navigate", "input": {"url": "https://www.linkedin.com/feed/"}}]
    assert len(run.audit(bad_li, ATS_ACTION)) == 1

    # CareerOps helpers are NOT allowed on non-ATS LinkedIn lane
    bad_helper = [{"name": "mcp__careerops__check_email", "input": {"domain": "linkedin.com"}}]
    assert len(run.audit(bad_helper, LI_ACTION)) == 1


def test_outcome_separates_helper_tools_and_accepts_closed_status():
    parsed = {
        "calls": [
            {"id": "1", "name": "mcp__playwright__browser_snapshot", "input": {}},
            {"id": "2", "name": "mcp__careerops__check_email", "input": {"domain": "jobs.ashbyhq.com"}},
        ],
        "final": {
            "is_error": False,
            "total_cost_usd": 0.01,
            "structured_output": {"status": "job_closed", "summary": "Vaga encerrada"},
        },
    }
    res = run.outcome(parsed, 0, ATS_ACTION)
    assert res["status"] == "job_closed"
    assert res["transcript"]["tools"] == ["mcp__playwright__browser_snapshot"]
    assert res["transcript"]["helper_tools"] == ["mcp__careerops__check_email"]


def test_careerops_mcp_server_dispatch_roundtrip(monkeypatch):
    monkeypatch.setattr(ats_helpers, "_api_call", lambda path, payload, env, timeout=15: (
        {"found": True, "code": "998877", "link": ""} if "verification" in path else {"domain": payload["domain"], "email": "p@e.com", "password": "pw"}
    ))
    with ats_helpers.CareerOpsMcpServer({"CAREEROPS_ENV_FILES": ""}) as srv:
        with hydrogen_agent.McpHttpClient(srv.url) as mcp:
            names = {t["name"] for t in mcp.list_tools()}
            assert names == {"check_email", "site_account", "write_answer", "lookup_answer", "wait_for_human", "ask_candidate"}
            out_email, err1 = mcp.call_tool("check_email", {"domain": "jobs.ashbyhq.com"})
            assert not err1 and json.loads(out_email)["code"] == "998877"
            out_acc, err2 = mcp.call_tool("site_account", {"op": "get_or_create", "domain": "jobs.ashbyhq.com"})
            assert not err2 and json.loads(out_acc)["password"] == "pw"


def test_s22_micro_respects_endpoint_and_constraints(tmp_path):
    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_POST(self):
            captured["auth"] = self.headers.get("Authorization")
            length = int(self.headers.get("Content-Length") or 0)
            captured["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
            resp = json.dumps({"choices": [{"message": {"content": '{"closed": true}'}}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        key_file = tmp_path / "llm-api-key.txt"
        key_file.write_text("test-s22-key\n", encoding="utf-8")
        out = ats_helpers.call_s22_micro(
            "Classify page.",
            "This position has been closed.",
            max_tokens=2048,
            env={"CAREEROPS_ENV_FILES": "", "S22_LLM_KEY_FILE": str(key_file), "S22_LLM_BASE_URL": f"http://127.0.0.1:{srv.server_address[1]}/v1"},
        )
        assert out == '{"closed": true}'
        assert captured["auth"] == "Bearer test-s22-key"
        assert captured["body"]["model"] == "gemma-4-E2B-litert"
        assert captured["body"]["stream"] is False
        assert captured["body"]["max_tokens"] <= 1024
        assert captured["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    finally:
        srv.shutdown()
        srv.server_close()


def test_hydrogen_agent_executes_tools_and_blocks_disallowed_nav():
    # Mock both a Streamable HTTP Playwright MCP server and an OpenAI agy_shim server
    step = {"i": 0}
    mcp_calls = []

    class FakeMcp(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_DELETE(self):
            self.send_response(200)
            self.end_headers()

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            m = req.get("method")
            if req.get("id") is None:
                self.send_response(202)
                self.end_headers()
                return
            if m == "initialize":
                res = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "pw", "version": "1"}}
            elif m == "tools/list":
                res = {"tools": [
                    {"name": "browser_snapshot", "description": "snap", "inputSchema": {"type": "object", "properties": {}}},
                    {"name": "browser_navigate", "description": "nav", "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}}},
                ]}
            else:
                mcp_calls.append(req["params"])
                res = {"content": [{"type": "text", "text": "Thank you for applying!"}], "isError": False}
            raw = json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": res}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Mcp-Session-Id", "pw-1")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    class FakeHydrogen(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_POST(self):
            _ = self.rfile.read(int(self.headers["Content-Length"]))
            step["i"] += 1
            if step["i"] == 1:
                msg = {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "browser_snapshot", "arguments": "{}"}},
                ]}
            else:
                msg = {"role": "assistant", "content": '{"status": "done", "summary": "Applied via Hydrogen", "questions": []}'}
            raw = json.dumps({"choices": [{"message": msg}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    pw_srv = HTTPServer(("127.0.0.1", 0), FakeMcp)
    hy_srv = HTTPServer(("127.0.0.1", 0), FakeHydrogen)
    threading.Thread(target=pw_srv.serve_forever, daemon=True).start()
    threading.Thread(target=hy_srv.serve_forever, daemon=True).start()
    try:
        res, tr = hydrogen_agent.run_hydrogen_agent(
            ATS_ACTION,
            "Finish this ATS form",
            f"http://127.0.0.1:{pw_srv.server_address[1]}/mcp",
            run.TOOLS,
            {"CAREEROPS_ENV_FILES": "", "CAREEROPS_HYDROGEN_BASE_URL": f"http://127.0.0.1:{hy_srv.server_address[1]}/v1", "CAREEROPS_HYDROGEN_TOKEN": "tok"},
        )
        assert res["status"] == "done"
        assert tr["tools"] == [{"tool": "mcp__playwright__browser_snapshot", "input": {}}]
        assert mcp_calls[0]["name"] == "browser_snapshot"
    finally:
        pw_srv.shutdown()
        pw_srv.server_close()
        hy_srv.shutdown()
        hy_srv.server_close()


def test_verify_external_sent_checks_successfully_modifier_and_other_page_frames():
    import asyncio
    from types import ModuleType, SimpleNamespace
    injected = []
    try:
        import playwright.async_api  # noqa: F401
    except ModuleNotFoundError:
        pw_mod = ModuleType("playwright")
        pw_async = ModuleType("playwright.async_api")
        pw_async.Error = Exception
        pw_mod.async_api = pw_async
        sys.modules["playwright"] = pw_mod
        sys.modules["playwright.async_api"] = pw_async
        injected = ["playwright", "playwright.async_api"]
    try:
        from worker import verify

        assert verify.external_sent_in("Thank you, your application has been successfully submitted to us.")
        assert verify.external_sent_in("Candidatura enviada com sucesso!")

        class FakeFrame:
            def __init__(self, url, text):
                self.url = url
                self._text = text

            async def evaluate(self, _script):
                return self._text

        class FakePage:
            def __init__(self, url, text, frames=()):
                self.url = url
                self._text = text
                self.frames = list(frames)
                self.main_frame = None
                self.context = None

            def is_closed(self):
                return False

            async def evaluate(self, _script):
                return self._text

        blank = FakePage("about:blank", "")
        confirm = FakePage(
            "https://career.skybornrenewables.com/Vacancies/995/Submit",
            "",
            frames=[FakeFrame("https://career.skybornrenewables.com/Vacancies/995/Done", "Thank you, your application has been successfully submitted to us.")],
        )
        blank.context = SimpleNamespace(pages=[confirm, blank])
        proof, ev = asyncio.run(verify.prove(blank, {"kind": "apply", "lane": "ats", "target_url": "https://career.skybornrenewables.com/Vacancies/995/Description/2"}))
        assert proof is True
        assert ev["url"] == "https://career.skybornrenewables.com/Vacancies/995/Done"
        # another company's tab showing "submitted" is not proof for this job
        other_job = FakePage("https://job-boards.greenhouse.io/acme/confirmation", "Thank you, your application has been successfully submitted to us.")
        blank2 = FakePage("about:blank", "")
        blank2.context = SimpleNamespace(pages=[other_job, blank2])
        proof2, _ = asyncio.run(verify.prove(blank2, {"kind": "apply", "lane": "ats", "target_url": "https://app.ashbyhq.com/citizen/1"}))
        assert proof2 is False
    finally:
        for mod in injected:
            sys.modules.pop(mod, None)


def test_hydrogen_agent_retries_transient_502_and_fails_over(monkeypatch):
    seen_models = []
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    class FakeMcp(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_DELETE(self):
            self.send_response(200)
            self.end_headers()

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            if req.get("id") is None:
                self.send_response(202)
                self.end_headers()
                return
            m = req.get("method")
            if m == "initialize":
                res = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "pw", "version": "1"}}
            elif m == "tools/list":
                res = {"tools": [{"name": "browser_snapshot", "description": "snap", "inputSchema": {"type": "object", "properties": {}}}]}
            else:
                res = {"content": [{"type": "text", "text": "ok"}], "isError": False}
            raw = json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": res}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Mcp-Session-Id", "pw-retry")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    class FlakyHydrogen(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            model = req.get("model")
            seen_models.append(model)
            if model == "gemini-4-hydrogen-low":
                self.send_response(502)
                self.end_headers()
                self.wfile.write(b"Bad Gateway")
                return
            payload = json.dumps({
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"status": "done", "summary": "Submitted ok", "questions": []}),
                    }
                }]
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    mcp_srv = HTTPServer(("127.0.0.1", 0), FakeMcp)
    llm_srv = HTTPServer(("127.0.0.1", 0), FlakyHydrogen)
    threading.Thread(target=mcp_srv.serve_forever, daemon=True).start()
    threading.Thread(target=llm_srv.serve_forever, daemon=True).start()
    try:
        res, tr = hydrogen_agent.run_hydrogen_agent(
            ATS_ACTION,
            "Finish applying",
            f"http://127.0.0.1:{mcp_srv.server_address[1]}/mcp",
            run.TOOLS,
            {
                "CAREEROPS_ENV_FILES": "",
                "CAREEROPS_HYDROGEN_BASE_URL": f"http://127.0.0.1:{llm_srv.server_address[1]}/v1",
                "CAREEROPS_HYDROGEN_TOKEN": "test-tok",
            },
        )
        assert res["status"] == "done"
        assert seen_models == [
            "gemini-4-hydrogen-low",
            "gemini-4-hydrogen-low",
            "gemini-4-hydrogen-medium",
        ]
        assert sleeps == [1.5]
        assert isinstance(tr, dict)
    finally:
        mcp_srv.shutdown()
        mcp_srv.server_close()
        llm_srv.shutdown()
        llm_srv.server_close()


def test_claim_and_run_handles_exception_and_waits_for_verify(monkeypatch):
    calls = []
    monkeypatch.setattr("time.sleep", lambda _s: None)

    class BackendStub(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_GET(self):
            calls.append(("GET", self.path, None))
            get_count = sum(1 for m, _, _ in calls if m == "GET")
            status = "unknown_outcome" if get_count == 1 else "done"
            raw = json.dumps({"status": status}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            calls.append(("POST", self.path, body))
            if self.path == "/automation/escalated/claim":
                raw = json.dumps({"action": ATS_ACTION}).encode("utf-8")
            else:
                raw = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    srv = HTTPServer(("127.0.0.1", 0), BackendStub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        env = {"CAREEROPS_API_BASE": f"http://127.0.0.1:{srv.server_address[1]}", "CAREEROPS_WORKER_TOKEN": "tok"}

        # Case 1: unhandled error still reports 'failed' instead of stalling in running_claude
        monkeypatch.setattr(run, "_run_action", lambda _a, _e: (_ for _ in ()).throw(RuntimeError("upstream 502")))
        assert run._claim_and_run(env, wait_verify=True) == 0
        post_result = [b for m, p, b in calls if m == "POST" and p == "/automation/actions/99/claude-result"][-1]
        assert post_result["status"] == "failed"
        assert "upstream 502" in post_result["summary"]
        assert not any(m == "GET" for m, _, _ in calls)

        # Case 2: 'done' result with wait_verify=True polls GET /run until worker verifies
        calls.clear()
        monkeypatch.setattr(run, "_run_action", lambda _a, _e: ({"status": "done", "summary": "Applied", "questions": [], "audit_flags": [], "cost_usd": None, "transcript": {}}, 3))
        assert run._claim_and_run(env, wait_verify=True) == 0
        get_paths = [p for m, p, _ in calls if m == "GET"]
        assert get_paths == ["/automation/actions/99/run", "/automation/actions/99/run"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_ats_sibling_subdomain_allowlist_and_cctld():
    bain_action = {"lane": "ats", "target_url": "https://www.bain.com/careers/find-a-role/position/?jobid=102641", "dossier": {}}
    bain_hosts = ats_helpers.allowed_hosts_for_action(bain_action)
    assert ats_helpers.is_host_allowed("careers.bain.com", "ats", bain_hosts) is True
    assert ats_helpers.is_host_allowed("evil.com", "ats", bain_hosts) is False
    assert ats_helpers.is_host_allowed("www.linkedin.com", "ats", bain_hosts) is False

    cap_action = {"lane": "ats", "target_url": "https://www.capgemini.com/jobs/123", "dossier": {"job": {"url": "https://www.linkedin.com/jobs/view/999"}}}
    cap_hosts = ats_helpers.allowed_hosts_for_action(cap_action)
    assert ats_helpers.is_host_allowed("careers.capgemini.com", "ats", cap_hosts) is True
    assert "linkedin.com" not in cap_hosts

    br_action = {"lane": "ats", "target_url": "https://vagas.acme.com.br/job/1", "dossier": {}}
    br_hosts = ats_helpers.allowed_hosts_for_action(br_action)
    assert ats_helpers.is_host_allowed("apply.acme.com.br", "ats", br_hosts) is True
    assert ats_helpers.is_host_allowed("evil.com.br", "ats", br_hosts) is False


def test_hydrogen_trim_messages_inserts_checkpoint_after_10_tool_rounds():
    msgs = [
        {"role": "system", "content": "System rules"},
        {"role": "user", "content": "DOSSIER payload"},
    ]
    for i in range(22):
        msgs.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": f"tc-{i}", "type": "function", "function": {"name": "browser_click", "arguments": json.dumps({"element": f"btn-{i}"})}}],
        })
        msgs.append({"role": "tool", "tool_call_id": f"tc-{i}", "content": f"snap-{i} " + ("x" * 1000)})

    trimmed = hydrogen_agent._trim_messages(msgs)
    assert trimmed[0]["content"] == "System rules"
    assert trimmed[1]["content"] == "DOSSIER payload"
    last_user_idx = max(i for i, m in enumerate(trimmed) if m.get("role") == "user")
    assert "Progress checkpoint" in trimmed[last_user_idx]["content"]
    assert "btn-0" in trimmed[last_user_idx]["content"]
    tc_after_user = sum(1 for m in trimmed[last_user_idx + 1:] if m.get("role") == "assistant" and m.get("tool_calls"))
    assert tc_after_user <= 10
    assert tc_after_user == 8
    tool_outputs = [m["content"] for m in trimmed if m.get("role") == "tool"]
    assert len([c for c in tool_outputs if "...[earlier snapshot compressed]..." in c]) == 6
    assert "snap-21" in tool_outputs[-1]


def test_hydrogen_extract_inline_tool_call():
    leaked = 'TOOL_CALL {"name": "browser_click", "arguments": {"target": "f3e136", "element": "Country"}}Commonly used: Brazil.'
    parsed = hydrogen_agent._extract_inline_tool_call(leaked)
    assert parsed == {
        "name": "browser_click",
        "arguments": {"target": "f3e136", "element": "Country"},
    }
    assert hydrogen_agent._extract_inline_tool_call('{"status": "done"}') is None


def test_hydrogen_ensure_target_tab_navigates_away_from_stale_tab():
    calls = []

    class StubMcp:
        def __init__(self, current_url):
            self.current_url = current_url

        def call_tool(self, name, args):
            calls.append((name, args))
            if name == "browser_tabs":
                return f"### Open tabs\n- 0: (current) [Old] ({self.current_url})", False
            return "ok", False

    flowgen_action = {
        "lane": "ats",
        "target_url": "https://jobs.ashbyhq.com/FlowGen%20Labs/abc/application",
        "dossier": {},
    }
    hosts = ats_helpers.allowed_hosts_for_action(flowgen_action)

    # Different Ashby customer path -> must navigate to target_url
    calls.clear()
    hydrogen_agent._ensure_target_tab(
        StubMcp("https://jobs.ashbyhq.com/reflectionai/123/application"),
        {"browser_tabs", "browser_navigate"},
        flowgen_action,
        "ats",
        hosts,
    )
    assert calls == [
        ("browser_tabs", {"action": "list"}),
        ("browser_navigate", {"url": flowgen_action["target_url"]}),
    ]

    # Same Ashby customer path (decoded space or encoded) -> stay on tab
    calls.clear()
    hydrogen_agent._ensure_target_tab(
        StubMcp("https://jobs.ashbyhq.com/FlowGen%20Labs/abc/application"),
        {"browser_tabs", "browser_navigate"},
        flowgen_action,
        "ats",
        hosts,
    )
    assert calls == [("browser_tabs", {"action": "list"})]


def test_extract_verification_text_greenhouse_and_mixed_codes():
    code, link = ats_helpers.extract_verification_text(
        "Security code for your application to Bot Auto",
        "Copy and paste this code into the security code field on your application: 17985286 After you enter the code, resubmit your application.",
    )
    assert code == "17985286"
    assert link == ""

    code_alpha, _ = ats_helpers.extract_verification_text(
        "Security code for your application to ExampleCo",
        "Copy and paste this code into the security code field on your application: aB3dE9fG",
    )
    assert code_alpha == "aB3dE9fG"

    code_fallback, _ = ats_helpers.extract_verification_text(
        "Verify your identity",
        "Please verify your application using:\n\n47368198\n\nValid for 15 minutes.",
    )
    assert code_fallback == "47368198"


def test_mark_read_and_archive_gmail_sends_modify_request():
    captured = {}

    class FakeGmail(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_POST(self):
            captured["path"] = self.path
            captured["auth"] = self.headers.get("Authorization")
            captured["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            raw = json.dumps({"id": "msg-42", "labelIds": []}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    srv = HTTPServer(("127.0.0.1", 0), FakeGmail)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    orig_json_req = ats_helpers._json_request

    def redirected(url, data=None, headers=None, timeout=15):
        url = url.replace("https://gmail.googleapis.com", f"http://127.0.0.1:{srv.server_address[1]}")
        return orig_json_req(url, data=data, headers=headers, timeout=timeout)

    ats_helpers._json_request = redirected
    try:
        ok = ats_helpers._mark_read_and_archive_gmail("msg-42", {"Authorization": "Bearer fake-tok"})
        assert ok is True
        assert captured["path"] == "/gmail/v1/users/me/messages/msg-42/modify"
        assert captured["auth"] == "Bearer fake-tok"
        assert captured["body"] == {"removeLabelIds": ["UNREAD", "INBOX"]}
    finally:
        ats_helpers._json_request = orig_json_req
        srv.shutdown()
        srv.server_close()


def test_hydrogen_agent_fails_over_on_502_quota_and_promotes_working_model():
    models_seen = []

    class FakeMcp(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            m = req.get("method")
            if req.get("id") is None:
                self.send_response(202)
                self.end_headers()
                return
            if m == "initialize":
                res = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "pw", "version": "1"}}
            elif m == "tools/list":
                res = {"tools": [{"name": "browser_snapshot", "description": "snap", "inputSchema": {"type": "object", "properties": {}}}]}
            else:
                res = {"content": [{"type": "text", "text": "ok"}], "isError": False}
            raw = json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": res}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Mcp-Session-Id", "pw-1")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    class FakeQuotaHydrogen(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            model = req.get("model")
            models_seen.append(model)
            if model == "gemini-4-hydrogen-low":
                err = json.dumps({"error": {"message": "agy: cota do modelo gemini-4-hydrogen-low esgotada"}}).encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return
            if len([m for m in models_seen if m == model]) == 1:
                msg = {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "browser_snapshot", "arguments": "{}"}},
                ]}
            else:
                msg = {"role": "assistant", "content": '{"status": "done", "summary": "Applied via failover", "questions": []}'}
            raw = json.dumps({"choices": [{"message": msg}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    pw_srv = HTTPServer(("127.0.0.1", 0), FakeMcp)
    hy_srv = HTTPServer(("127.0.0.1", 0), FakeQuotaHydrogen)
    threading.Thread(target=pw_srv.serve_forever, daemon=True).start()
    threading.Thread(target=hy_srv.serve_forever, daemon=True).start()
    try:
        res, tr = hydrogen_agent.run_hydrogen_agent(
            ATS_ACTION,
            "Finish this ATS form",
            f"http://127.0.0.1:{pw_srv.server_address[1]}/mcp",
            run.TOOLS,
            {
                "CAREEROPS_ENV_FILES": "",
                "CAREEROPS_HYDROGEN_BASE_URL": f"http://127.0.0.1:{hy_srv.server_address[1]}/v1",
                "CAREEROPS_HYDROGEN_TOKEN": "tok",
                "CAREEROPS_HYDROGEN_MODEL": "gemini-4-hydrogen-low",
            },
        )
        assert res["status"] == "done"
        assert tr["provider"] == "gemini-4-hydrogen-medium"
        # Exhausted model tried only once on step 1 and skipped on step 2
        assert models_seen == ["gemini-4-hydrogen-low", "gemini-4-hydrogen-medium", "gemini-4-hydrogen-medium"]
    finally:
        pw_srv.shutdown()
        pw_srv.server_close()
        hy_srv.shutdown()
        hy_srv.server_close()

