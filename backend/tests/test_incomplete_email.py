"""A company writes that the application was started and not sent (2026-11-19, GHD on Oracle: "Continue to apply for the
job …", with a "complete" link and a "delete the data" link side by side): the apply agent takes the form up again."""
import hashlib
import json
import uuid

from app.services import email_monitor_service as em
from app.services.automation_service import AutomationService as Auto
from app.services.email_monitor_service import EmailMonitorService as Monitor, safe_resume_link

ORACLE = "https://ejov.fa.ca2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/job/29336"
CONTINUE = "https://ejov.fa.ca2.oraclecloud.com/hcmUI/CandidateExperience/s/2yVmNEyruG"
DELETE = "https://ejov.fa.ca2.oraclecloud.com/hcmUI/CandidateExperience/s/9tqP4k4tMj"
BODY = (f"Hello Paulo, Just a reminder about your draft job application for the job Asset Management, Senior Advisor - Water (US). "
        f"We invite you to complete and submit your [job application]({CONTINUE}). If you decide to no longer apply for this job, "
        f"you can [delete the data]({DELETE}) you entered.")


def add_apply(sql, job, status, url=ORACLE):
    return sql("""INSERT INTO public.automation_actions (kind, lane, status, target_type, target_id, target_url, title, rank, payload,
                                                           payload_hash, idempotency_key, approved_at, claude_attempts)
                  VALUES ('apply', 'ats', %s, 'job', %s, %s, 'GHD', 10, '{}', %s, %s, NOW(), 1) RETURNING *""",
               (status, job["id"], url, hashlib.sha256(b"{}").hexdigest(), uuid.uuid4().hex))[0]


def reader(monkeypatch, link=CONTINUE):
    async def run_skill(path, context, response_format="json"):
        return {"classification": "incomplete", "confidence": 0.95, "summary": "Lembrete: candidatura em rascunho, falta enviar",
                "evidence": "Just a reminder about your draft job application", "resume_link": link, "feedback": []}
    monkeypatch.setattr(em.SkillService, "run_skill", staticmethod(run_skill))


def ghd_mail(mid="<ghd@x>"):
    return {"message_id": mid, "sender": "GHD Talent Acquisition Team <talentacquisition.noreply@ghd.com>",
            "subject": "Continue to apply for the job Asset Management, Senior Advisor - Water (US)", "body": BODY}


def test_the_reminder_is_a_candidate_for_the_reader():
    assert em.is_candidate("x <noreply@other.com>", "Continue to apply for the job X", "", [])
    assert em.KEYWORDS.search("Please finish your application")


def test_only_the_continue_link_passes():
    assert safe_resume_link(CONTINUE, BODY) == CONTINUE
    assert safe_resume_link(DELETE, BODY) == ""                       # "[delete the data](…)" right before it
    assert safe_resume_link("https://evil.example/x", BODY) == ""     # not in the message
    assert safe_resume_link("https://x.example/withdraw?id=1", "see https://x.example/withdraw?id=1") == ""


def test_a_stuck_application_goes_back_to_the_agent_with_the_link(db, sql, add_job, monkeypatch):
    job = add_job(company="GHD", title="Asset Management, Senior Advisor - Water (US)", status="new")
    action = add_apply(sql, job, "needs_user")
    reader(monkeypatch)
    Monitor.process([ghd_mail()], source="lolo")
    row = sql("SELECT * FROM public.automation_actions WHERE id = %s", (action["id"],))[0]
    assert row["status"] == "escalated" and row["error_code"] == "incomplete_by_email" and row["claude_attempts"] == 0
    assert CONTINUE in row["error_text"] and DELETE not in row["error_text"]
    note = sql("SELECT text FROM public.bot_notifications WHERE kind = 'email_incomplete'")[0]["text"]
    assert "agente" in note and "não concluída" in note


def test_a_done_application_is_reopened_and_the_job_is_no_longer_applied(db, sql, add_job, monkeypatch):
    job = add_job(company="GHD", title="Asset Management, Senior Advisor - Water (US)", status="applied")
    action = add_apply(sql, job, "done")
    reader(monkeypatch)
    Monitor.process([ghd_mail()], source="lolo")
    assert sql("SELECT status FROM public.automation_actions WHERE id = %s", (action["id"],))[0]["status"] == "escalated"
    assert sql("SELECT status FROM public.job_listings WHERE id = %s", (job["id"],))[0]["status"] == "new"


def test_a_cancelled_application_stays_cancelled(db, sql, add_job, monkeypatch):
    job = add_job(company="GHD", title="Asset Management, Senior Advisor - Water (US)", status="new")
    action = add_apply(sql, job, "cancelled")
    reader(monkeypatch)
    Monitor.process([ghd_mail()], source="lolo")
    assert sql("SELECT status FROM public.automation_actions WHERE id = %s", (action["id"],))[0]["status"] == "cancelled"


def test_a_link_on_another_site_is_not_given_to_the_agent(db, sql, add_job):
    job = add_job(company="GHD", status="new")
    action = add_apply(sql, job, "needs_user")
    out = Auto.reopen_by_email(job["id"], None, "rascunho", "https://click.mailer.example/abc")
    assert out["outcome"] == "reopened" and out["link"] == ""
    assert "mailer.example" not in sql("SELECT error_text FROM public.automation_actions WHERE id = %s", (action["id"],))[0]["error_text"]


def test_after_two_reopenings_it_stays_with_you(db, sql, add_job):
    job = add_job(company="GHD", status="new")
    action = add_apply(sql, job, "needs_user")
    for _ in range(2):
        assert Auto.reopen_by_email(job["id"], None, "rascunho", CONTINUE)["outcome"] == "reopened"
        sql("UPDATE public.automation_actions SET status = 'needs_user' WHERE id = %s", (action["id"],))
    assert Auto.reopen_by_email(job["id"], None, "rascunho", CONTINUE)["outcome"] == "to_user"
    row = sql("SELECT status, error_code FROM public.automation_actions WHERE id = %s", (action["id"],))[0]
    assert row["status"] == "needs_user" and row["error_code"] == "incomplete_by_email"


def test_an_application_already_in_the_queue_is_left_alone(db, sql, add_job):
    job = add_job(company="GHD", status="new")
    action = add_apply(sql, job, "escalated")
    assert Auto.reopen_by_email(job["id"], None, "rascunho", CONTINUE)["outcome"] == "running"
    assert sql("SELECT claude_attempts FROM public.automation_actions WHERE id = %s", (action["id"],))[0]["claude_attempts"] == 1
