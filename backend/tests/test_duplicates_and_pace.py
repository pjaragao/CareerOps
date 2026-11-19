"""2026-11-19: the same job posted in many places is one job (search, intake, application); a check that never answers
does not hold the LinkedIn lane; applications keep a short gap of their own."""
from datetime import timedelta

from app.services import automation_service
from app.services.automation_service import AutomationService as Auto, _one, job_key, now
from app.services.job_search_service import JobSearchService as Search

TITLE = "AI Machine Learning Engineer - Remote - Latin America"


def ad(jid, location, company="FullStack", title=TITLE):
    return {"linkedin_job_id": jid, "title": title, "company": company, "location": location, "description": "Descrição",
            "posted": "1 hour ago", "easy_apply": True}


def test_the_key_ignores_case_and_punctuation():
    assert job_key("FullStack", TITLE) == job_key("fullstack ", "AI Machine-Learning Engineer – Remote – Latin America".replace("–", "-"))


def test_the_search_reads_one_copy_of_a_job_per_page_and_none_already_here(db, sql, add_job):
    add_job("50", company="EIB", title="Cleantech Finance Adviser")
    cards = [{"id": "1", "title": TITLE, "company": "FullStack", "location": "Curitiba, Brazil", "posted": "1 hour ago"},
             {"id": "2", "title": TITLE, "company": "FullStack", "location": "Recife, Brazil", "posted": "1 hour ago"},
             {"id": "3", "title": "Cleantech Finance Adviser", "company": "EIB", "location": "Berlin", "posted": "1 hour ago"},
             {"id": "4", "title": "Data Engineer", "company": "FullStack", "location": "Brazil", "posted": "1 hour ago"}]
    out = Search.unseen(["1", "2", "3", "4"], cards)
    assert out["unseen"] == ["1", "4"] and out["skipped"]["duplicate"] == 2


def test_a_copy_that_gets_in_enters_discarded_with_the_first_ones_id(db, sql):
    assert Search.add_discovered([ad("1", "Curitiba, Brazil"), ad("2", "Recife, Brazil")], None) == 1
    first = sql("SELECT id FROM public.job_listings WHERE linkedin_job_id = '1'")[0]["id"]
    copy = sql("SELECT triage_outcome, triage_reason FROM public.job_listings WHERE linkedin_job_id = '2'")[0]
    assert copy["triage_outcome"] == "discarded" and f"#{first}" in copy["triage_reason"]


def test_a_copy_discarded_for_its_place_does_not_hide_one_in_a_good_place(db, sql):
    sql("""INSERT INTO public.job_listings (linkedin_job_id, url, status, job_title, company, location, description, triage_score,
                                            triage_reason, triage_outcome)
           VALUES ('9', 'u', 'discovered', %s, 'FullStack', 'Toronto', 'd', 0, 'Local fora do foco da busca: Toronto', 'discarded')""", (TITLE,))
    assert Search.unseen(["1"], [{"id": "1", "title": TITLE, "company": "FullStack", "location": "Brazil", "posted": "1 hour ago"}])["unseen"] == ["1"]


def two_jobs(add_job):
    return add_job("1", status="new", company="FullStack", title=TITLE), add_job("2", status="new", company="FullStack", title=TITLE)


def test_the_same_job_in_another_place_gets_no_second_proposal(db, add_job):
    a, b = two_jobs(add_job)
    assert Auto.propose_job(a)
    assert Auto.propose_job(b) is None


def test_a_queued_twin_is_discarded_when_the_first_is_already_sent(db, sql, add_job):
    a, b = two_jobs(add_job)
    first = Auto.create_action("apply", "apply:a", "A", a["url"], {"job_id": a["id"]}, status="done", target_type="job", target_id=a["id"])
    twin = Auto.create_action("apply", "apply:b", "B", b["url"], {"job_id": b["id"]}, status="queued", target_type="job", target_id=b["id"])
    sql("UPDATE public.automation_actions SET approved_at = NOW() WHERE id = %s", (twin["id"],))
    assert Auto.claim("linkedin_write", "test")["reason"] == "duplicate"
    row = _one("SELECT status, error_code, error_text FROM public.automation_actions WHERE id = %s", (twin["id"],))
    assert row["status"] == "discarded" and row["error_code"] == "duplicate" and f"#{first['id']}" in row["error_text"]


def test_a_check_that_never_answers_goes_to_you_after_three_tries(db, sql):
    a = Auto.create_action("follow", "f1", "Empresa", "https://www.linkedin.com/company/f1", {"url": "f1"}, status="queued")
    for _ in range(3):
        sql("UPDATE public.automation_actions SET status = 'unknown_outcome', scheduled_for = NULL WHERE id = %s", (a["id"],))
        got = Auto.claim("linkedin_write", "test")["action"]
        assert got["id"] == a["id"] and got["verify_only"]
    sql("UPDATE public.automation_actions SET status = 'unknown_outcome', scheduled_for = NULL WHERE id = %s", (a["id"],))
    Auto.claim("linkedin_write", "test")
    row = _one("SELECT status, error_code FROM public.automation_actions WHERE id = %s", (a["id"],))
    assert row["status"] == "needs_user" and row["error_code"] == "verify_failed"


def test_no_browser_before_anything_is_a_new_attempt_not_a_check(db):
    a = Auto.create_action("follow", "f1", "Empresa", "https://www.linkedin.com/company/f1", {"url": "f1"}, status="queued")
    got = Auto.claim("linkedin_write", "test")["action"]
    Auto.abort(got["id"], "no browser", 0)
    assert _one("SELECT status FROM public.automation_actions WHERE id = %s", (a["id"],))["status"] == "queued"


def test_applications_keep_their_own_short_gap(db, monkeypatch, add_job):
    cfg = {**db, "automation": {**db["automation"], "write_gap_minutes": [5, 20], "apply_gap_minutes": [1, 3]}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    job = add_job("1", status="new")
    a = Auto.create_action("apply", "apply:1", "A", job["url"], {"job_id": job["id"]}, status="queued", target_type="job", target_id=job["id"])
    _one("UPDATE public.automation_actions SET approved_at = NOW() WHERE id = %s RETURNING id", (a["id"],))
    assert Auto.claim("linkedin_write", "test")["action"]["id"] == a["id"]
    assert timedelta(seconds=50) < Auto.state()["next_write_at"] - now() <= timedelta(minutes=3, seconds=5)
