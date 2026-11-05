import threading
from datetime import timedelta

import pytest

from app.services import automation_service
from app.services.automation_service import AutomationService as Auto, _one, now
from app.services import content_guard


def comment(key="c1", text="Ótimo ponto", status="proposed", target_id=1, rank=10):
    return Auto.create_action("comment", key, "Post", f"https://www.linkedin.com/feed/update/urn:li:activity:{key}/",
                              {"text": text, "post_head": "Post", "post_url": "x"}, status=status, target_type="engagement", target_id=target_id, rank=rank)


def queued_follow(key="f1"):
    return Auto.create_action("follow", key, "Empresa", f"https://www.linkedin.com/company/{key}", {"url": key}, status="queued")


def claim(lane="linkedin_write"):
    return Auto.claim(lane, "test")


def status_of(action_id):
    return _one("SELECT status FROM public.automation_actions WHERE id = %s", (action_id,))["status"]


# ── Approval ─────────────────────────────────────────────────────────────
def test_nothing_runs_without_approval(db):
    comment()
    assert claim()["action"] is None


def test_approved_goes_with_what_you_approved(db):
    a = comment()
    Auto.approve(a["id"], "Texto editado por você")
    got = claim()["action"]
    assert got["id"] == a["id"] and got["payload"]["text"] == "Texto editado por você"


def test_same_thing_is_proposed_only_once(db):
    assert comment("same") and comment("same") is None


def test_a_tampered_action_is_refused(db, sql):
    a = comment()
    Auto.approve(a["id"])
    sql("""UPDATE public.automation_actions SET payload = jsonb_set(payload, '{text}', '"outro texto"') WHERE id = %s""", (a["id"],))
    assert claim() == {"action": None, "reason": "payload_changed"}
    assert status_of(a["id"]) == "needs_user"


def test_approving_a_forbidden_text_is_refused(db):
    a = comment(text="Trabalhei com solid waste")
    with pytest.raises(content_guard.BlockedContent):
        Auto.approve(a["id"])
    assert status_of(a["id"]) == "proposed"


def test_forbidden_text_is_caught_again_when_it_runs(db, add_job, sql):
    job = add_job(resume="CV com sanitary landfill")
    a = Auto.propose_job(job)
    sql("UPDATE public.automation_actions SET status = 'queued' WHERE id = %s", (a["id"],))
    assert claim()["reason"] == "content_blocked"
    assert status_of(a["id"]) == "needs_user"


def test_approving_a_job_brings_it_to_the_board(db, add_job, sql):
    job = add_job()
    Auto.approve(Auto.propose_job(job)["id"])
    assert sql("SELECT status FROM public.job_listings WHERE id = %s", (job["id"],))[0]["status"] == "new"


def test_rejecting_a_job_never_brings_it_back(db, add_job, sql):
    from app.services.job_search_service import JobSearchService
    job = add_job("777")
    Auto.reject(Auto.propose_job(job)["id"])
    assert sql("SELECT status FROM public.job_listings WHERE id = %s", (job["id"],))[0]["status"] == "archived"
    assert JobSearchService.unseen(["777", "778"])["unseen"] == ["778"]


# ── What stops it ────────────────────────────────────────────────────────
def test_off_hands_out_nothing(db):
    Auto.update_state(mode="off")
    queued_follow()
    assert claim() == {"action": None, "reason": "off"}


def test_halt_stops_everything_until_you_resume(db):
    queued_follow()
    Auto.halt("Parado por você")
    assert claim()["reason"] == "halted"
    assert claim("ats")["reason"] == "halted"
    Auto.resume()
    assert claim()["action"]


def test_outside_the_window_nothing_is_claimed(db, monkeypatch):
    cfg = {**db, "automation": {**db["automation"], "window": {"start_hour": 3, "end_hour": 3}}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    queued_follow()
    assert claim()["reason"] == "outside_window"


def test_a_warning_from_linkedin_stops_the_lanes_and_lowers_the_ramp(db):
    queued_follow("a")
    got = claim()["action"]
    Auto.escalate(got["id"], "checkpoint", "tela de verificação", source="worker")
    state = Auto.state()
    assert set(state["halted_lanes"]) == {"linkedin_read", "linkedin_write"} and state["ramp_step"] == 1
    assert claim()["reason"] == "halted" and claim("linkedin_read")["reason"] == "halted"
    assert claim("ats")["reason"] != "halted"   # company sites don't use the LinkedIn session
    assert status_of(got["id"]) == "queued"


def test_session_lost_opens_the_login_for_you(db):
    got = (queued_follow(), claim()["action"])[1]
    Auto.escalate(got["id"], "session_expired", source="worker")
    assert Auto.state()["session_status"] == "logged_out"


def test_writes_keep_a_gap(db, monkeypatch):
    cfg = {**db, "automation": {**db["automation"], "write_gap_minutes": [5, 20]}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    queued_follow("a"), queued_follow("b")
    first = claim()["action"]
    Auto.complete(first["id"], "dry_run")
    assert claim()["reason"] == "gap"
    assert timedelta(minutes=4) < Auto.state()["next_write_at"] - now() <= timedelta(minutes=21)


def test_one_write_at_a_time(db):
    queued_follow("a"), queued_follow("b")
    assert claim()["action"]
    assert claim()["reason"] == "lane_busy"


def test_daily_limit(db, sql):
    sql("UPDATE public.automation_limits SET step2 = 1 WHERE kind = 'follow'")
    try:
        queued_follow("a"), queued_follow("b")
        Auto.complete(claim()["action"]["id"], "dry_run")
        assert claim() == {"action": None, "reason": "empty"}
        assert next(l for l in Auto.limits() if l["kind"] == "follow")["left"] == 0
    finally:
        sql("UPDATE public.automation_limits SET step2 = 10 WHERE kind = 'follow'")


def test_a_write_that_stopped_before_the_final_click_does_not_use_the_limit(db, sql):
    sql("UPDATE public.automation_limits SET step2 = 1 WHERE kind = 'follow'")
    try:
        queued_follow("a"), queued_follow("b")
        Auto.escalate(claim()["action"]["id"], "selector_not_found", "sem botão")   # nothing was clicked
        assert next(l for l in Auto.limits() if l["kind"] == "follow")["left"] == 1
        got = claim()["action"]
        assert next(l for l in Auto.limits() if l["kind"] == "follow")["left"] == 0   # running counts
        Auto.complete(got["id"], "executed")
        Auto.verify(got["id"], False)   # clicked, not seen yet: it may have gone out
        assert next(l for l in Auto.limits() if l["kind"] == "follow")["left"] == 0
    finally:
        sql("UPDATE public.automation_limits SET step2 = 10 WHERE kind = 'follow'")


def test_ramp_goes_by_steps(db, sql):
    sql("UPDATE public.automation_state SET ramp_step = 0")
    assert next(l for l in Auto.limits() if l["kind"] == "apply")["limit"] == 3
    sql("UPDATE public.automation_state SET ramp_step_at = NOW() - INTERVAL '8 days'")
    Auto.housekeeping()
    assert Auto.state()["ramp_step"] == 1


def test_the_step_you_pick_stays_when_the_climb_is_off(db, sql, client):
    from tests.conftest import APPROVER, BOT
    assert client.patch("/api/automation/state", json={"ramp_step": 0, "ramp_auto": False}, headers=BOT).status_code == 401
    assert client.patch("/api/automation/state", json={"ramp_step": 0, "ramp_auto": False}, headers=APPROVER).status_code == 200
    assert next(l for l in Auto.limits() if l["kind"] == "apply")["limit"] == 3
    sql("UPDATE public.automation_state SET ramp_step_at = NOW() - INTERVAL '8 days'")
    Auto.housekeeping()
    assert Auto.state()["ramp_step"] == 0
    Auto.update_state(ramp_auto=True)
    Auto.housekeeping()
    assert Auto.state()["ramp_step"] == 1


def test_you_set_each_step_of_a_limit(db, sql, client):
    from tests.conftest import APPROVER
    try:
        assert client.put("/api/automation/limits/comment", json={"step0": 1, "step1": 2, "step2": 4}, headers=APPROVER).status_code == 200
        assert next(l for l in Auto.limits() if l["kind"] == "comment")["limit"] == 4   # tests run on step 2
        assert client.put("/api/automation/limits/nope", json={"step0": 1, "step1": 2, "step2": 4}, headers=APPROVER).status_code == 404
    finally:
        sql("UPDATE public.automation_limits SET step0 = 3, step1 = 5, step2 = 10 WHERE kind = 'comment'")


def test_ramp_does_not_climb_while_halted(db, sql):
    sql("UPDATE public.automation_state SET ramp_step = 0, ramp_step_at = NOW() - INTERVAL '8 days', halted_at = NOW()")
    Auto.housekeeping()
    assert Auto.state()["ramp_step"] == 0


def test_invites_stop_for_a_week_at_the_limit_and_the_rest_goes_on(db, sql):
    a = Auto.create_action("connect", "p1", "Ana", "https://www.linkedin.com/in/ana", {}, status="queued", target_type="prospect", target_id=1)
    got = claim()["action"]
    Auto.escalate(got["id"], "weekly_invite_limit")
    assert Auto.state()["invites_paused_until"] > now() + timedelta(days=6)
    assert status_of(a["id"]) == "queued"
    Auto.create_action("connect", "p2", "Bia", "https://www.linkedin.com/in/bia", {}, status="queued", target_type="prospect", target_id=2)
    queued_follow("still-goes")
    assert claim()["action"]["kind"] == "follow"


def test_concurrent_claims_never_hand_the_same_action_twice(db, monkeypatch):
    for i in range(6):
        Auto.create_action("search", f"s{i}", "busca", "u", {}, status="queued")
    cfg = {**db, "automation": {**db["automation"], "lanes": {"linkedin_read": 6}, "max_windows": 6}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    got, lock = [], threading.Lock()

    def work():
        action = Auto.claim("linkedin_read", "t")["action"]
        with lock:
            got.append(action and action["id"])

    threads = [threading.Thread(target=work) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    ids = [g for g in got if g]
    assert len(ids) == 6 and len(set(ids)) == 6


# ── The final click ──────────────────────────────────────────────────────
def state(**kw):
    return {"mode": "live", "account_kind": "main", "allow_final_submit": True, "confirm_submit_left": 0, "halted_lanes": [], **kw}


def test_a_test_account_never_submits(db):
    assert Auto._allow_final(state(account_kind="test"), "apply", None) is False


def test_submit_needs_all_the_locks(db, monkeypatch):
    assert Auto._allow_final(state(), "apply", None) is True
    assert Auto._allow_final(state(mode="dry_run"), "apply", None) is False
    assert Auto._allow_final(state(allow_final_submit=False), "apply", None) is False
    monkeypatch.setattr(automation_service.settings, "AUTOMATION_ALLOW_FINAL_SUBMIT", False)
    assert Auto._allow_final(state(), "apply", None) is False


def test_test_account_only_touches_allowed_targets(db, monkeypatch):
    cfg = {**db, "test_account": {"allowed_targets": ["https://www.linkedin.com/feed/update/mine/"]}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    assert Auto._allow_final(state(account_kind="test"), "comment", "https://www.linkedin.com/feed/update/mine/") is True
    assert Auto._allow_final(state(account_kind="test"), "comment", "https://www.linkedin.com/feed/update/theirs/") is False
    assert Auto._allow_final(state(account_kind="test"), "connect", "https://www.linkedin.com/in/stranger") is False


def test_an_executed_report_without_permission_stops_everything(db):
    Auto.update_state(account_kind="test")
    queued_follow()
    got = claim()["action"]
    Auto.update_state(mode="dry_run")
    Auto.complete(got["id"], "executed", {})
    assert "all" in Auto.state()["halted_lanes"]


def test_first_submissions_wait_for_your_click(db, add_job, sql):
    sql("UPDATE public.automation_state SET confirm_submit_left = 3")
    job = add_job()
    a = Auto.propose_job(job)
    sql("UPDATE public.automation_actions SET status = 'queued' WHERE id = %s", (a["id"],))
    got = claim()["action"]
    assert got["allow_final"] and got["confirm_required"]
    Auto.ready_to_submit(got["id"], [{"label": "x", "value": "y"}])
    assert status_of(got["id"]) == "awaiting_confirm"
    info = Auto.run_info(got["id"])
    assert info["confirm_required"] and not info["confirmed"]
    Auto.confirm_submit(got["id"])
    info = Auto.run_info(got["id"])
    assert info["confirmed"] and not info["confirm_required"]
    assert Auto.state()["confirm_submit_left"] == 2


def test_your_ok_after_the_wait_ran_out_sends_it_without_another_wait(db, add_job, sql):
    sql("UPDATE public.automation_state SET confirm_submit_left = 3")
    a = Auto.propose_job(add_job())
    sql("UPDATE public.automation_actions SET status = 'queued' WHERE id = %s", (a["id"],))
    got = claim()["action"]
    Auto.ready_to_submit(got["id"], [])
    sql("UPDATE public.automation_actions SET status = 'needs_user', error_code = 'confirm_timeout' WHERE id = %s", (got["id"],))
    assert Auto.confirm_submit(got["id"])["status"] == "queued"
    again = claim()["action"]
    assert again["id"] == got["id"] and not again["confirm_required"] and again["confirmed"]
    assert Auto.state()["confirm_submit_left"] == 2   # one OK, counted once


def test_nonce_is_required_for_the_extension(db):
    queued_follow()
    got = claim()["action"]
    assert Auto.run_info(got["id"], "wrong") is None
    assert Auto.run_info(got["id"], got["nonce"])["id"] == got["id"]


# ── Never twice ──────────────────────────────────────────────────────────
def test_done_only_after_the_page_shows_it(db, add_job, sql):
    job = add_job()
    a = Auto.propose_job(job)
    sql("UPDATE public.automation_actions SET status = 'queued' WHERE id = %s", (a["id"],))
    got = claim()["action"]
    Auto.complete(got["id"], "executed", {"fields": []})
    assert status_of(got["id"]) == "verifying"
    assert sql("SELECT status FROM public.job_listings WHERE id = %s", (job["id"],))[0]["status"] == "discovered"
    Auto.verify(got["id"], True, {"url": "x"})
    assert status_of(got["id"]) == "done"
    row = sql("SELECT status, applied_via_bot, applied_at FROM public.job_listings WHERE id = %s", (job["id"],))[0]
    assert row["status"] == "applied" and row["applied_via_bot"] and row["applied_at"]


def test_clicked_but_not_seen_is_looked_at_again_then_asks_you_never_repeats(db, sql):
    queued_follow()
    got = claim()["action"]
    Auto.complete(got["id"], "executed")
    Auto.verify(got["id"], False)
    assert status_of(got["id"]) == "unknown_outcome"
    sql("UPDATE public.automation_actions SET scheduled_for = NULL WHERE id = %s", (got["id"],))
    again = claim()["action"]
    assert again["verify_only"] is True
    Auto.verify(again["id"], False)
    assert status_of(got["id"]) == "needs_user"
    assert _one("SELECT attempts FROM public.automation_actions WHERE id = %s", (got["id"],))["attempts"] == 1


def test_a_crash_is_never_assumed_either_way(db, sql):
    queued_follow()
    got = claim()["action"]
    sql("UPDATE public.automation_actions SET lease_until = NOW() - INTERVAL '1 minute' WHERE id = %s", (got["id"],))
    Auto.housekeeping()
    assert status_of(got["id"]) == "unknown_outcome"
    again = claim()["action"]
    assert again["verify_only"] is True and again["id"] == got["id"]
    Auto.verify(got["id"], True, {})
    assert status_of(got["id"]) == "done"


def test_crash_before_the_click_runs_again_only_after_looking(db, sql):
    queued_follow()
    got = claim()["action"]
    Auto.abort(got["id"], "docker kill")
    assert status_of(got["id"]) == "unknown_outcome"
    assert claim()["action"]["verify_only"] is True
    Auto.verify(got["id"], False)
    assert status_of(got["id"]) == "queued"
    assert _one("SELECT scheduled_for FROM public.automation_actions WHERE id = %s", (got["id"],))["scheduled_for"] > now()


def test_what_may_have_gone_out_never_goes_to_claude(db):
    queued_follow()
    got = claim()["action"]
    Auto.complete(got["id"], "executed")
    Auto.escalate(got["id"], "unexpected_layout", "o navegador caiu", source="worker")
    row = _one("SELECT status, error_text FROM public.automation_actions WHERE id = %s", (got["id"],))
    assert row["status"] == "needs_user" and "Pode já ter sido enviado" in row["error_text"]
    assert Auto.claude_claim("r")["action"] is None


def test_a_retry_after_keeps_it_out_of_the_queue_for_a_while(db):
    queued_follow()
    got = claim()["action"]
    Auto.abort(got["id"], "no browser", 120)
    assert status_of(got["id"]) == "unknown_outcome"
    assert claim()["action"] is None


def test_a_read_that_crashes_just_runs_again(db, sql):
    a = Auto.create_action("search", "s", "busca", "u", {}, status="queued")
    got = claim("linkedin_read")["action"]
    sql("UPDATE public.automation_actions SET lease_until = NOW() - INTERVAL '1 minute' WHERE id = %s", (got["id"],))
    Auto.housekeeping()
    assert status_of(a["id"]) == "queued"


def test_a_dry_run_changes_nothing_else(db, add_job, sql):
    job = add_job()
    a = Auto.propose_job(job)
    sql("UPDATE public.automation_actions SET status = 'queued' WHERE id = %s", (a["id"],))
    got = claim()["action"]
    Auto.complete(got["id"], "dry_run", {"reached_final_step": True})
    assert status_of(got["id"]) == "done"
    assert sql("SELECT status FROM public.job_listings WHERE id = %s", (job["id"],))[0]["status"] == "discovered"


# ── Where a failure goes ─────────────────────────────────────────────────
@pytest.mark.parametrize("code,expected", [("selector_not_found", "escalated"), ("step_stuck", "escalated"), ("unknown_required_question", "needs_user"),
                                           ("captcha", "needs_user"), ("account_required", "needs_user"), ("whatever_else", "needs_user"),
                                           ("already_following", "discarded"), ("post_deleted", "discarded")])
def test_routing(db, code, expected):
    queued_follow()
    got = claim()["action"]
    Auto.escalate(got["id"], code, "x")
    assert status_of(got["id"]) == expected


def test_already_applied_marks_the_job(db, add_job, sql):
    job = add_job()
    a = Auto.propose_job(job)
    sql("UPDATE public.automation_actions SET status = 'queued' WHERE id = %s", (a["id"],))
    Auto.escalate(claim()["action"]["id"], "already_applied")
    assert sql("SELECT status FROM public.job_listings WHERE id = %s", (job["id"],))[0]["status"] == "applied"


def test_an_answer_goes_to_the_bank_and_back_to_the_queue(db, sql):
    queued_follow()
    got = claim()["action"]
    Auto.escalate(got["id"], "unknown_required_question", "x", [{"label": "Notice period?"}])
    Auto.answer(got["id"], [{"question": "Notice period?", "answer": "30 days"}])
    assert status_of(got["id"]) == "queued"
    assert Auto.known_answer("Notice period? *", "text") == "30 days"


def test_handoff_stays_with_you_while_company_sites_are_off(db):
    queued_follow()
    got = claim()["action"]
    Auto.handoff(got["id"], "https://boards.greenhouse.io/acme/jobs/1")
    row = _one("SELECT status, error_code FROM public.automation_actions WHERE id = %s", (got["id"],))
    assert row["status"] == "needs_user" and row["error_code"] == "external_manual"


def test_handoff_moves_to_the_browser_without_your_session(db, monkeypatch):
    cfg = {**db, "jobs": {**db["jobs"], "external_apply": True}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    queued_follow()
    got = claim()["action"]
    Auto.handoff(got["id"], "https://boards.greenhouse.io/acme/jobs/1")
    row = _one("SELECT status, lane, target_url FROM public.automation_actions WHERE id = %s", (got["id"],))
    assert (row["status"], row["lane"]) == ("queued", "ats") and "greenhouse" in row["target_url"]


# ── Claude fallback ──────────────────────────────────────────────────────
def stuck():
    queued_follow()
    got = claim()["action"]
    Auto.escalate(got["id"], "selector_not_found", "sem botão")
    return got


def test_claude_takes_what_is_stuck_once(db):
    got = stuck()
    first = Auto.claude_claim("r")["action"]
    assert first["id"] == got["id"] and first["dossier"]["why_stuck"] == "sem botão"
    assert Auto.claude_claim("r") == {"action": None, "reason": "empty"}
    Auto.claude_result(got["id"], first["run_id"], "failed", "não deu")
    assert status_of(got["id"]) == "needs_user"


def test_claude_saying_done_is_not_enough(db):
    got = stuck()
    first = Auto.claude_claim("r")["action"]
    Auto.claude_result(got["id"], first["run_id"], "done", "feito")
    assert status_of(got["id"]) == "unknown_outcome"
    check = claim()["action"]
    assert check["verify_only"] is True
    Auto.verify(check["id"], False)
    assert status_of(got["id"]) == "unknown_outcome"   # one more look; never a second click


def test_claude_going_off_target_stops_the_lane(db):
    got = stuck()
    first = Auto.claude_claim("r")["action"]
    Auto.claude_result(got["id"], first["run_id"], "done", "feito", audit_flags=["navegou para fora do alvo"])
    assert status_of(got["id"]) == "needs_user"
    assert "linkedin_write" in Auto.state()["halted_lanes"]


def test_claude_daily_cap(db, monkeypatch, sql):
    cfg = {**db, "claude": {"per_day": 1, "lanes": ["linkedin_write"]}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    got = stuck()
    Auto.claude_result(got["id"], Auto.claude_claim("r")["action"]["run_id"], "failed", "x")
    assert Auto.claude_claim("r") == {"action": None, "reason": "daily_cap"}


def test_a_stuck_action_goes_to_you_when_claude_is_off_for_that_lane(db, monkeypatch):
    cfg = {**db, "claude": {"per_day": 15, "lanes": ["ats"]}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    got = stuck()
    assert status_of(got["id"]) == "needs_user"


def test_the_dossier_carries_no_secrets(db, add_job, sql):
    job = add_job()
    a = Auto.propose_job(job)
    sql("UPDATE public.automation_actions SET status = 'queued' WHERE id = %s", (a["id"],))
    got = claim()["action"]
    Auto.escalate(got["id"], "step_stuck", "x")
    dossier = Auto.claude_claim("r")["action"]["dossier"]
    text = str(dossier)
    assert "worker-token" not in text and "approver-token" not in text
    assert dossier["facts"]["salary_expectation"]["abroad_usd_monthly"] == 7000
    assert dossier["files"]["resume"].startswith(f"/tmp/careerops-run/{got['id']}/")


# ── Proposals and expiry ─────────────────────────────────────────────────
def test_proposals_come_from_what_is_ready(db, sql, add_job):
    sql("INSERT INTO public.linkedin_prospects (profile_url, name, fit, status) VALUES ('https://www.linkedin.com/in/ana', 'Ana', 80, 'to_contact'), (NULL, 'Sem link', 90, 'to_contact')")
    sql("INSERT INTO public.linkedin_engagement (post_url, post_text, comment_draft, relevance) VALUES ('https://www.linkedin.com/feed/update/urn:li:activity:1/', 'Texto do post aqui', 'Comentário', 70), (NULL, 'Sem link no post', 'Comentário', 70)")
    add_job("200", status="new", resume=None, cover=None)
    add_job("201", status="applied")
    assert Auto.sync_proposals() == 3
    assert Auto.sync_proposals() == 0
    box = Auto.inbox()
    assert len(box["connect"]) == 1 and len(box["comment"]) == 1 and len(box["apply"]) == 1


def test_newest_job_first(db, add_job):
    old = add_job("1", posted_at=now() - timedelta(hours=40))
    new = add_job("2", posted_at=now() - timedelta(hours=2))
    Auto.propose_job(old), Auto.propose_job(new)
    assert [a["target_id"] for a in Auto.inbox()["apply"]] == [new["id"], old["id"]]


def test_approval_expires(db, sql):
    a = comment()
    Auto.approve(a["id"])
    sql("UPDATE public.automation_actions SET expires_at = NOW() - INTERVAL '1 minute' WHERE id = %s", (a["id"],))
    assert claim()["action"] is None
    Auto.housekeeping()
    assert status_of(a["id"]) == "expired"


def test_documents_are_made_only_after_approval_and_then_it_queues(db, add_job, sql, monkeypatch):
    calls = []

    async def fake_docs(job_id):
        calls.append(job_id)
        sql("UPDATE public.job_listings SET resume_markdown = 'CV gerado', cover_letter = 'Carta' WHERE id = %s", (job_id,))

    monkeypatch.setattr("app.services.job_pipeline_service.JobPipelineService.generate_docs", staticmethod(fake_docs))
    job = add_job(resume=None, cover=None)
    a = Auto.propose_job(job)
    Auto.prepare_documents()
    assert calls == []
    Auto.approve(a["id"])
    Auto.prepare_documents()
    assert calls == [job["id"]] and status_of(a["id"]) == "queued"


def test_first_cvs_wait_for_your_reading(db, add_job, sql, monkeypatch):
    async def fake_docs(job_id):
        pass

    monkeypatch.setattr("app.services.job_pipeline_service.JobPipelineService.generate_docs", staticmethod(fake_docs))
    sql("UPDATE public.automation_state SET review_cv_left = 20")
    a = Auto.propose_job(add_job())
    Auto.approve(a["id"])
    Auto.prepare_documents()
    assert status_of(a["id"]) == "review_docs"
    Auto.approve_docs(a["id"])
    assert status_of(a["id"]) == "queued" and Auto.state()["review_cv_left"] == 19


def test_documents_that_fail_come_to_you(db, add_job, sql, monkeypatch):
    async def boom(job_id):
        raise content_guard.BlockedContent("cita assunto protegido")

    monkeypatch.setattr("app.services.job_pipeline_service.JobPipelineService.generate_docs", staticmethod(boom))
    a = Auto.propose_job(add_job(resume=None))
    Auto.approve(a["id"])
    Auto.prepare_documents()
    assert status_of(a["id"]) == "needs_user"


def test_tick_does_only_the_books_while_off(db, sql):
    from app.services.job_search_service import JobSearchService
    JobSearchService.ensure_seeds()
    Auto.update_state(mode="off")
    Auto.tick()
    assert sql("SELECT COUNT(*) AS n FROM public.automation_actions")[0]["n"] == 0


def test_a_login_link_works_once(db, client):
    from tests.conftest import APPROVER, BOT
    assert client.post("/api/automation/login-links", headers=BOT).status_code == 401
    url = client.post("/api/automation/login-links", headers=APPROVER).json()["url"]
    code = url.split("codigo=")[1]
    first = client.post("/api/automation/login-links/redeem", json={"code": code})
    assert first.status_code == 200 and first.json()["token"] == APPROVER["X-CareerOps-Token"]
    assert client.post("/api/automation/login-links/redeem", json={"code": code}).status_code == 410


def test_an_expired_login_link_gives_nothing(db, client, sql):
    url = Auto.login_link()
    sql("UPDATE public.automation_login_links SET expires_at = NOW() - INTERVAL '1 minute'")
    assert client.post("/api/automation/login-links/redeem", json={"code": url.split("codigo=")[1]}).status_code == 410


# ── Revising a comment with the AI before approving ─────────────────────
def test_the_ai_rewrites_a_comment_from_your_edit_and_it_waits_again(db, sql, monkeypatch):
    import asyncio
    seen = {}

    async def fake_skill(path, context, model_key="ai_model_writing"):
        seen.update(context)
        return {"relevance": 80, "reason": "Tema seu", "comment": "Versão mais curta"}

    monkeypatch.setattr("app.services.linkedin_copilot_service._skill", fake_skill)
    url = "https://www.linkedin.com/feed/update/urn:li:activity:9/"
    eid = _one("INSERT INTO public.linkedin_engagement (post_url, post_text, comment_draft, relevance, status) "
               "VALUES (%s, 'Texto do post', 'Rascunho', 60, 'pending') RETURNING id", (url,))["id"]
    a = comment(target_id=eid)
    out = asyncio.run(Auto.revise(a["id"], "mais curto", "Meu texto editado"))
    assert seen["instruction"] == "mais curto" and seen["previous_draft"] == "Meu texto editado"
    assert out["payload"]["text"] == "Versão mais curta" and out["fit"] == 80 and out["status"] == "proposed"
    assert _one("SELECT comment_draft FROM public.linkedin_engagement WHERE id = %s", (eid,))["comment_draft"] == "Versão mais curta"


def test_every_kind_of_comment_comes_from_one_call_and_switching_is_free(db, sql, monkeypatch):
    import asyncio
    from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot, COMMENT_ANGLES
    calls = []

    async def fake_skill(path, context, model_key="ai_model_writing"):
        calls.append(context)
        return {"relevance": 80, "reason": "Tema seu", "comment": "Técnico v1",
                "variants": {k: f"{k} v{len(calls)}" for k in COMMENT_ANGLES} | {"tecnico": f"Técnico v{len(calls)}", "intruso": "x"}}

    monkeypatch.setattr("app.services.linkedin_copilot_service._skill", fake_skill)
    url = "https://www.linkedin.com/feed/update/urn:li:activity:7/"
    item = asyncio.run(Copilot.add_engagement("Um post sobre modelos de dados", url))
    assert len(calls) == 1 and [k for k, *_ in calls[0]["angles"]] == list(COMMENT_ANGLES)
    assert item["comment_draft"] == "Técnico v1" and set(item["comment_variants"]) == set(COMMENT_ANGLES)
    Auto.sync_proposals()
    a = _one("SELECT * FROM public.automation_actions WHERE kind = 'comment'")
    assert a["payload"]["variants"]["elogio"] == "elogio v1" and a["payload"]["post_full"] == "Um post sobre modelos de dados"
    # another kind: already drafted, no new AI call
    out = asyncio.run(Auto.revise(a["id"], "", angle="elogio"))
    assert len(calls) == 1 and out["payload"]["text"] == "elogio v1"
    # a request of yours: a new call, all the versions again
    out = asyncio.run(Auto.revise(a["id"], "mais curto"))
    assert len(calls) == 2 and out["payload"]["variants"]["pergunta"] == "pergunta v2"


def test_only_a_comment_still_to_approve_can_be_revised(db):
    import asyncio
    a = comment(status="queued")
    assert asyncio.run(Auto.revise(a["id"], "mais curto")) is None


def test_outside_the_window_what_you_approved_goes_and_executar_agora_goes_first(db, monkeypatch):
    cfg = {**db, "automation": {**db["automation"], "window": {"start_hour": 3, "end_hour": 3}}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    later, now_ = comment("later"), comment("now")
    Auto.approve(later["id"])
    Auto.approve(now_["id"], run_now=True)
    got = claim()["action"]
    assert got["id"] == now_["id"]
    assert status_of(later["id"]) == "queued"


def test_executar_agora_still_respects_the_stop(db, monkeypatch):
    cfg = {**db, "automation": {**db["automation"], "window": {"start_hour": 3, "end_hour": 3}}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    Auto.approve(comment()["id"], run_now=True)
    Auto.halt("teste")
    assert claim()["reason"] == "halted"


def test_batch_approval_can_run_now(db, client):
    from tests.conftest import APPROVER
    a, b = comment("a"), comment("b")
    r = client.post("/api/automation/approve-batch", json={"ids": [a["id"], b["id"]], "run_now": True}, headers=APPROVER)
    assert r.json()["approved"] == [a["id"], b["id"]]
    assert _one("SELECT COUNT(*) AS n FROM public.automation_actions WHERE run_now")["n"] == 2


def test_what_you_approve_or_retry_ignores_the_window_and_the_limit(db, sql, monkeypatch):
    """The window and the limits hold back only the automations (2026-11-04)."""
    sql("UPDATE public.automation_limits SET step2 = 1 WHERE kind = 'follow'")
    try:
        Auto.complete((queued_follow("auto1"), claim()["action"])[1]["id"], "dry_run")   # the automation used the limit
        queued_follow("auto2")
        mine = comment("mine", status="proposed")
        cfg = {**db, "automation": {**db["automation"], "window": {"start_hour": 3, "end_hour": 3}}}
        monkeypatch.setattr(automation_service, "config", lambda: cfg)
        Auto.approve(mine["id"])
        got = claim()["action"]
        assert got["id"] == mine["id"]
        Auto.complete(got["id"], "dry_run")
        assert next(l for l in Auto.limits() if l["kind"] == "comment")["used"] == 0
        assert claim()["reason"] == "outside_window"   # the automation still waits
        mine_follow = queued_follow("mine2")
        sql(f"UPDATE public.automation_actions SET status = 'needs_user', error_code = 'selector_not_found' WHERE id = {mine_follow['id']}")
        Auto.retry(mine_follow["id"])
        assert claim()["action"]["id"] == mine_follow["id"]   # retried: past the window and the spent follow limit
    finally:
        sql("UPDATE public.automation_limits SET step2 = 10 WHERE kind = 'follow'")


def test_de_novo_after_a_failed_check_sends_again_instead_of_checking_forever(db, sql):
    got = (queued_follow("vf"), claim()["action"])[1]
    # as invite 35 on 2026-11-05: clicked by the old flow, looked at twice, nothing on the page
    sql(f"""UPDATE public.automation_actions SET status = 'needs_user', error_code = 'verify_failed', lease_owner = NULL,
              result = '{{"executed": true, "recheck": true}}' WHERE id = {got['id']}""")
    again = Auto.retry(got["id"])
    assert again["status"] == "queued" and not again["result"].get("executed") and again["result"]["previous"]["executed"]
    assert claim()["action"]["id"] == got["id"]   # a real send, not only a look
