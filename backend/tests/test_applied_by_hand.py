"""'Já me candidatei' (2026-11-23): you applied yourself, from the Precisa de você list."""
from app.services.automation_service import AutomationService as Auto
from tests.conftest import APPROVER


def stuck_apply(sql, add_job, status="needs_user"):
    job = add_job(status="new")
    action = Auto.propose_job(job)
    sql("UPDATE public.automation_actions SET status = %s, error_code = 'captcha', questions = '[{\"label\": \"x\"}]' WHERE id = %s", (status, action["id"]))
    return job, action


def test_an_application_you_did_yourself_counts_as_sent(db, sql, add_job, client):
    job, action = stuck_apply(sql, add_job)
    out = client.post(f"/api/automation/actions/{action['id']}/applied-by-hand", headers=APPROVER)
    assert out.status_code == 200 and out.json()["status"] == "done" and out.json()["error_code"] == "by_hand"
    row = sql("SELECT status, applied_via_bot, applied_at FROM public.job_listings WHERE id = %s", (job["id"],))[0]
    assert row["status"] == "applied" and row["applied_via_bot"] is False and row["applied_at"]
    assert sql("SELECT event FROM public.automation_events WHERE action_id = %s ORDER BY id DESC LIMIT 1", (action["id"],))[0]["event"] == "applied_by_hand"
    assert client.post(f"/api/automation/actions/{action['id']}/applied-by-hand", headers=APPROVER).status_code == 404   # once


def test_not_while_the_browser_works_on_it_nor_for_other_kinds(db, sql, add_job, client):
    _, running = stuck_apply(sql, add_job, "running_ext")
    assert Auto.applied_by_hand(running["id"]) is None
    comment = Auto.create_action("comment", "c1", "Ana", "https://www.linkedin.com/posts/x", {"text": "Oi"}, target_type="engagement", target_id=1)
    assert Auto.applied_by_hand(comment["id"]) is None


def test_a_job_already_in_interview_keeps_its_status(db, sql, add_job):
    job, action = stuck_apply(sql, add_job)
    sql("UPDATE public.job_listings SET status = 'interviewing' WHERE id = %s", (job["id"],))
    Auto.applied_by_hand(action["id"])
    assert sql("SELECT status FROM public.job_listings WHERE id = %s", (job["id"],))[0]["status"] == "interviewing"
