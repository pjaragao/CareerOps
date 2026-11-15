"""Tests for external ATS apply robustness: persistent accounts, email OTPs, fallback answers, and lifecycle."""
import hashlib
import uuid
import pytest

from app.services.ats_auth_service import AtsAuthService, extract_verification
from app.services.automation_service import AutomationService as Auto, _one, question_key
from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot
from tests.conftest import WORKER

EMPTY_PAYLOAD_HASH = hashlib.sha256(b"{}").hexdigest()


def _seed_ats_action(sql, target_url="https://jobs.ashbyhq.com/acme/1"):
    row = sql(
        """INSERT INTO public.automation_actions (kind, lane, status, target_url, title, rank, payload, payload_hash, idempotency_key, approved_at)
           VALUES ('apply', 'ats', 'queued', %s, 'ATS Apply', 10, '{}', %s, %s, NOW())
           RETURNING *""",
        (target_url, EMPTY_PAYLOAD_HASH, uuid.uuid4().hex),
    )[0]
    return row


def test_extract_verification_parses_otp_and_link():
    otp_subject = "Verify your application to Acme"
    otp_body = "Use security code A7K9P2Q1 to continue your application at https://jobs.ashbyhq.com/verify?token=abc123"
    extracted = extract_verification(otp_subject, otp_body)
    assert extracted["code"] == "A7K9P2Q1"
    assert any("jobs.ashbyhq.com/verify?token=abc123" in u for u in extracted["links"])

    num_code = extract_verification("Código de acesso", "654321 é o seu código de verificação")
    assert num_code["code"] == "654321"


def test_site_account_lifecycle_and_endpoint(db, client):
    r = client.post("/api/automation/site-accounts", json={"domain": "https://wd5.myworkdayjobs.com/acme"}, headers=WORKER)
    assert r.status_code == 200
    created = r.json()
    assert created["domain"] == "wd5.myworkdayjobs.com"
    assert created["email"]
    assert len(created["password"]) >= 16

    r2 = client.post("/api/automation/site-accounts", json={"domain": "wd5.myworkdayjobs.com"}, headers=WORKER)
    assert r2.status_code == 200
    assert r2.json()["password"] == created["password"]

    r3 = client.post("/api/automation/site-accounts", json={
        "domain": "wd5.myworkdayjobs.com",
        "password": "NewStrong!Password99",
        "notes": "reset ok",
    }, headers=WORKER)
    assert r3.status_code == 200
    assert r3.json()["password"] == "NewStrong!Password99"
    assert AtsAuthService.get_or_create_account("wd5.myworkdayjobs.com")["notes"] == "reset ok"

    # Worker token required
    assert client.post("/api/automation/site-accounts", json={"domain": "wd5.myworkdayjobs.com"}).status_code == 401


def test_email_verification_ingest_and_lookup_endpoints(db, client):
    ing = client.post("/api/automation/email/verification/ingest", json={
        "message_id": "msg-e2e-ashby-1",
        "sender": "no-reply@ashbyhq.com",
        "subject": "Ashby verification code",
        "body": "Enter verification code 849201 to finish applying at https://jobs.ashbyhq.com/verify?c=1",
    }, headers=WORKER)
    assert ing.status_code == 200
    assert ing.json()["code"] == "849201"

    found = client.post("/api/automation/email/verification", json={"query_hint": "ashbyhq", "since_seconds": 900}, headers=WORKER)
    assert found.status_code == 200
    data = found.json()
    assert data["found"] is True
    assert data["code"] == "849201"
    assert any("jobs.ashbyhq.com/verify" in u for u in data["links"])


def test_known_answer_cross_type_fallback(db, sql):
    sql(
        """INSERT INTO public.automation_answers (question_norm, question, field_type, answer)
           VALUES (%s, 'Are you authorized to work in Brazil?', 'select', 'Yes')""",
        (question_key("Are you authorized to work in Brazil?"),),
    )
    assert Auto.known_answer("Are you authorized to work in Brazil?", "select") == "Yes"
    assert Auto.known_answer("Are you authorized to work in Brazil?", "radio") == "Yes"
    assert Auto.known_answer("Are you authorized to work in Brazil?", "text") == "Yes"


def test_ats_account_and_email_verification_escalate_instead_of_needs_user(db, sql):
    db["jobs"]["external_apply"] = True
    ats = _seed_ats_action(sql, "https://wd5.myworkdayjobs.com/acme/job/1")
    claimed = Auto.claim("ats", "w1")["action"]
    assert claimed["id"] == ats["id"]
    Auto.escalate(ats["id"], "account_required", "Portal pede cadastro")
    assert _one("SELECT status, error_code FROM public.automation_actions WHERE id = %s", (ats["id"],))["status"] == "escalated"

    # Second ATS stop on email_verification also routes to escalated
    ats2 = _seed_ats_action(sql, "https://jobs.ashbyhq.com/acme/2")
    Auto.claim("ats", "w1")
    Auto.escalate(ats2["id"], "email_verification", "OTP solicitado")
    assert _one("SELECT status FROM public.automation_actions WHERE id = %s", (ats2["id"],))["status"] == "escalated"

    # LinkedIn write lane keeps stopping to user
    li = sql(
        """INSERT INTO public.automation_actions (kind, lane, status, target_url, title, rank, payload, payload_hash, idempotency_key, approved_at)
           VALUES ('apply', 'linkedin_write', 'queued', 'https://www.linkedin.com/jobs/view/1/', 'LI', 10, '{}', %s, %s, NOW())
           RETURNING *""",
        (EMPTY_PAYLOAD_HASH, uuid.uuid4().hex),
    )[0]
    Auto.claim("linkedin_write", "w1")
    Auto.escalate(li["id"], "account_required", "Login needed")
    assert _one("SELECT status FROM public.automation_actions WHERE id = %s", (li["id"],))["status"] == "needs_user"


@pytest.mark.parametrize("result_status,expected_code", [
    ("job_closed", "job_closed"),
    ("already_applied", "already_applied"),
])
def test_claude_result_discards_closed_or_already_applied_ats_jobs(db, sql, result_status, expected_code):
    db["jobs"]["external_apply"] = True
    ats = _seed_ats_action(sql, "https://jobs.ashbyhq.com/acme/closed")
    Auto.claim("ats", "w1")
    Auto.escalate(ats["id"], "external_form_unfinished", "0 fields")
    claimed = Auto.claude_claim("runner-1")["action"]
    assert claimed["id"] == ats["id"]
    Auto.claude_result(ats["id"], claimed["run_id"], result_status, f"Detected {result_status}")
    row = _one("SELECT status, error_code FROM public.automation_actions WHERE id = %s", (ats["id"],))
    assert row["status"] == "discarded"
    assert row["error_code"] == expected_code


def test_copilot_facts_overlays_profile_phone_and_address(db, sql, monkeypatch):
    from app.services import cv_format
    sql(
        """INSERT INTO public.automation_answers (question_norm, question, field_type, answer)
           VALUES (%s, 'Street Address', 'text', 'Rua Exemplo 100'),
                  (%s, 'Zip/Postal Code', 'text', '88015-000')""",
        (question_key("Street Address"), question_key("Zip/Postal Code")),
    )
    monkeypatch.setattr(cv_format, "_personal", lambda: {
        "name": "Paulo Roberto Test",
        "email": "paulo@example.com",
        "phone": "+55 48 98404-4819",
        "location": "Florianopolis, SC",
        "linkedin": "https://linkedin.com/in/paulotest",
        "github": "https://github.com/paulotest",
        "portfolio": "https://portfolio.example.com",
    })
    facts = Copilot._facts()
    assert facts["contact"]["phone"] == "+55 48 98404-4819"
    assert facts["contact"]["first_name"] == "Paulo"
    assert facts["contact"]["last_name"] == "Roberto Test"
    assert facts["contact"]["street_address"] == "Rua Exemplo 100"
    assert facts["contact"]["zip_code"] == "88015-000"


def test_quota_502_auto_retries_and_notifies_lolobot_once(db, sql):
    db["jobs"]["external_apply"] = True
    _seed_ats_action(sql, "https://jobs.ashbyhq.com/acme/q1")
    _seed_ats_action(sql, "https://jobs.ashbyhq.com/acme/q2")

    id1 = Auto.claim("ats", "w1")["action"]["id"]
    Auto.escalate(id1, "external_form_unfinished", "0 fields")
    c1 = Auto.claude_claim("r1")["action"]
    assert c1 and c1["id"] == id1
    Auto.claude_result(id1, c1["run_id"], "failed", "HTTP Error 502: Bad Gateway - agy: cota do modelo esgotada. Resets in 10m")

    id2 = Auto.claim("ats", "w1")["action"]["id"]
    Auto.escalate(id2, "external_form_unfinished", "0 fields")
    c2 = Auto.claude_claim("r1")["action"]
    assert c2 and c2["id"] == id2
    Auto.claude_result(id2, c2["run_id"], "failed", "HTTP Error 502: Bad Gateway - quota reached. Resets in 10m")

    r1 = _one("SELECT status, error_code, scheduled_for FROM public.automation_actions WHERE id = %s", (id1,))
    r2 = _one("SELECT status, error_code, scheduled_for FROM public.automation_actions WHERE id = %s", (id2,))
    assert r1["status"] == "escalated" and r1["error_code"] == "auto_retry"
    assert r2["status"] == "escalated" and r2["error_code"] == "auto_retry"
    assert Auto.claude_claim("r1")["action"] is None
    notices = sql("SELECT * FROM public.bot_notifications WHERE dedupe_key LIKE %s", ("quota_retry:%",))
    assert len(notices) == 1


def test_resolve_before_user_handles_closed_external_answers_and_keeps_captcha(db, sql, add_job, monkeypatch):
    from app.services.ai_service import AIService
    db["jobs"]["external_apply"] = True

    # 1. Closed job is discarded rather than sent to user
    ats_closed = _seed_ats_action(sql, "https://jobs.ashbyhq.com/acme/closed2")
    Auto.claim("ats", "w1")
    Auto.escalate(ats_closed["id"], "unexpected_layout", "This job is no longer available")
    assert _one("SELECT status, error_code FROM public.automation_actions WHERE id = %s", (ats_closed["id"],))["status"] == "discarded"

    # 2. External manual redirect on linkedin_write moves to ats queued
    li_ext = sql(
        """INSERT INTO public.automation_actions (kind, lane, status, target_url, title, rank, payload, payload_hash, idempotency_key, approved_at)
           VALUES ('apply', 'linkedin_write', 'queued', 'https://www.linkedin.com/jobs/view/999/', 'Ext', 10, '{}', %s, %s, NOW())
           RETURNING *""",
        (EMPTY_PAYLOAD_HASH, uuid.uuid4().hex),
    )[0]
    Auto.claim("linkedin_write", "w1")
    Auto.escalate(li_ext["id"], "external_manual", "Candidatura no site da empresa: https://boards.greenhouse.io/acme/jobs/77")
    li_row = _one("SELECT lane, status, target_url FROM public.automation_actions WHERE id = %s", (li_ext["id"],))
    assert (li_row["lane"], li_row["status"]) == ("ats", "queued")
    assert "boards.greenhouse.io" in li_row["target_url"]

    # 3. Deterministic screening questions are saved and auto-requeued
    job = add_job("301")
    ap = Auto.propose_job(job)
    sql("UPDATE public.automation_actions SET status = 'queued' WHERE id = %s", (ap["id"],))
    Auto.claim("linkedin_write", "w1")
    Auto.escalate(ap["id"], "unknown_required_question", "Perguntas obrigatórias", [{"label": "What is your notice period?"}, {"label": "Do you have a valid driver's license?"}])
    ap_row = _one("SELECT status, error_code FROM public.automation_actions WHERE id = %s", (ap["id"],))
    assert ap_row["status"] == "queued" and ap_row["error_code"] == "auto_answered"
    assert Auto.known_answer("What is your notice period?", "text") == "3 weeks"
    assert Auto.known_answer("Do you have a valid driver's license?", "text") == "Yes"

    # 4. AI fallback answers custom derivable question and requeues; unanswerable stays needs_user
    class StubProvider:
        def generate_json(self, prompt, model=None, temperature=0.1):
            return {"can_answer": True, "answers": [{"question": "How many years of Terraform?", "answer": "4"}]}

    monkeypatch.setattr(AIService, "get_provider", staticmethod(lambda key=None: StubProvider()))
    sql("UPDATE public.automation_actions SET scheduled_for = NOW() WHERE id = %s", (ap["id"],))
    Auto.claim("linkedin_write", "w1")
    Auto.escalate(ap["id"], "unknown_required_question", "Falta pergunta", [{"label": "How many years of Terraform?"}])
    assert Auto.known_answer("How many years of Terraform?", "text") == "4"
    assert _one("SELECT status FROM public.automation_actions WHERE id = %s", (ap["id"],))["status"] == "queued"

    # 5. Real CAPTCHA strictly remains needs_user (never bypassed)
    sql("UPDATE public.automation_actions SET scheduled_for = NOW() WHERE id = %s", (ap["id"],))
    Auto.claim("linkedin_write", "w1")
    Auto.escalate(ap["id"], "captcha", "Please complete Cloudflare Turnstile CAPTCHA")
    assert _one("SELECT status, error_code FROM public.automation_actions WHERE id = %s", (ap["id"],))["status"] == "needs_user"

    # 6. Hydrogen connection errors auto-retry; read scans retry once then discard instead of needs_user
    ats_conn = _seed_ats_action(sql, "https://jobs.ashbyhq.com/acme/conn")
    Auto.claim("ats", "w1")
    Auto.escalate(ats_conn["id"], "external_form_unfinished", "0 fields")
    c_conn = Auto.claude_claim("r1")["action"]
    Auto.claude_result(ats_conn["id"], c_conn["run_id"], "failed", "Hydrogen execution error: <urlopen error [Errno 111] Connection refused>")
    conn_row = _one("SELECT status, error_code FROM public.automation_actions WHERE id = %s", (ats_conn["id"],))
    assert (conn_row["status"], conn_row["error_code"]) == ("escalated", "auto_retry")

    scan = Auto.create_action("reply_scan", "reply-test", "Respostas", "https://www.linkedin.com/notifications/", {}, status="queued")
    Auto.claim("linkedin_read", "w1")
    Auto.escalate(scan["id"], "unexpected_layout", "Página de notificações não reconhecida")
    assert _one("SELECT status FROM public.automation_actions WHERE id = %s", (scan["id"],))["status"] == "queued"
    sql("UPDATE public.automation_actions SET scheduled_for = NOW() WHERE id = %s", (scan["id"],))
    Auto.claim("linkedin_read", "w1")
    Auto.escalate(scan["id"], "unexpected_layout", "Página de notificações não reconhecida")
    assert _one("SELECT status, error_code FROM public.automation_actions WHERE id = %s", (scan["id"],)) == {"status": "discarded", "error_code": "superseded"}
