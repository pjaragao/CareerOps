"""The approval link (2026-11-22): jobs approved from the phone with a token that only does that; Lolo never approves a job by reply."""
from urllib.parse import parse_qs, urlparse

from app.services.approval_link_service import ApprovalLinkService as Links
from app.services.automation_service import AutomationService as Auto
from app.services.bot_service import BotService
from tests.conftest import APPROVER, BOT


def token_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["t"][0]


def proposed_job(add_job, sql, job_id="100", score=80, company="Acme"):
    job = add_job(job_id=job_id, status="discovered", company=company)
    sql("UPDATE public.job_listings SET triage_score = %s WHERE id = %s", (score, job["id"]))
    return Auto.propose_job(job)


def test_the_link_is_public_without_the_port_and_keeps_only_a_hash(db, sql):
    url = Links.create_link()
    assert url.startswith("https://") and ":5174" not in url and "/aprovar?t=" in url   # the Funnel's port, never the app's
    row = sql("SELECT token_hash, expires_at - created_at AS life FROM public.approval_links")[0]
    assert token_of(url) not in row["token_hash"] and round(row["life"].total_seconds() / 86400) == 7


def test_the_page_lists_and_approves_jobs_with_the_token(db, sql, add_job, client):
    a1, a2 = proposed_job(add_job, sql, "1", 90), proposed_job(add_job, sql, "2", 75, "Beta")
    t = {"X-Approval-Token": token_of(Links.create_link())}
    page = client.get("/aprovar")
    assert page.status_code == 200 and page.headers["referrer-policy"] == "no-referrer" and "nonce-" in page.headers["content-security-policy"]
    items = client.get("/aprovar/api/jobs", headers=t).json()["items"]
    assert [i["id"] for i in items] == [a1["id"], a2["id"]] and items[0]["source_label"] == "LinkedIn"
    assert client.post(f"/aprovar/api/jobs/{a1['id']}/approve", headers=t).json()["status"] == "approved"
    assert client.post(f"/aprovar/api/jobs/{a2['id']}/reject", headers=t).status_code == 200
    assert client.post(f"/aprovar/api/jobs/{a2['id']}/approve", headers=t).status_code == 409
    events = sql("SELECT event FROM public.automation_events WHERE action_id = %s ORDER BY id", (a1["id"],))
    assert [e["event"] for e in events][-1] == "approved_by_link"


def test_the_token_does_nothing_else(db, sql, add_job, client):
    comment = Auto.create_action("comment", "c1", "Ana", "https://www.linkedin.com/posts/x", {"text": "Oi"}, target_type="engagement", target_id=1)
    t = {"X-Approval-Token": token_of(Links.create_link())}
    assert client.post(f"/aprovar/api/jobs/{comment['id']}/approve", headers=t).status_code == 409
    assert client.get("/api/automation/status", headers={"X-CareerOps-Token": t["X-Approval-Token"]}).status_code == 401
    assert client.get("/aprovar/api/jobs", headers={"X-Approval-Token": "x" * 40}).status_code == 401
    assert client.get("/aprovar/api/jobs").status_code == 401


def test_revoked_or_expired_links_stop(db, sql, client):
    t = {"X-Approval-Token": token_of(Links.create_link())}
    assert client.get("/aprovar/api/jobs", headers=t).status_code == 200
    assert client.delete("/api/automation/approval-links", headers=APPROVER).json()["revoked"] == 1
    assert client.get("/aprovar/api/jobs", headers=t).status_code == 401
    t2 = {"X-Approval-Token": token_of(Links.create_link())}
    sql("UPDATE public.approval_links SET expires_at = NOW() - INTERVAL '1 minute' WHERE revoked_at IS NULL")
    assert client.get("/aprovar/api/jobs", headers=t2).status_code == 401


def test_approve_all_above_a_score(db, sql, add_job, client):
    hi, lo = proposed_job(add_job, sql, "1", 91), proposed_job(add_job, sql, "2", 72, "Beta")
    t = {"X-Approval-Token": token_of(Links.create_link())}
    assert client.post("/aprovar/api/approve-above", json={"min_score": 85}, headers=t).json()["approved"] == [hi["id"]]
    assert sql("SELECT status FROM public.automation_actions WHERE id = %s", (lo["id"],))[0]["status"] == "proposed"


def test_lolo_never_approves_or_discards_a_job(db, sql, add_job, client):
    job = proposed_job(add_job, sql)
    comment = Auto.create_action("comment", "c1", "Ana", "https://www.linkedin.com/posts/x", {"text": "Oi"}, target_type="engagement", target_id=1)
    assert client.post(f"/api/automation/actions/{job['id']}/approve", json={}, headers=BOT).status_code == 403
    assert client.post(f"/api/automation/actions/{job['id']}/reject", headers=BOT).status_code == 403
    out = client.post("/api/automation/approve-batch", json={"ids": [job["id"], comment["id"]]}, headers=BOT).json()
    assert out == {"approved": [comment["id"]], "refused": [job["id"]]}
    assert client.post(f"/api/automation/actions/{job['id']}/approve", json={}, headers=APPROVER).status_code == 200   # the app still can
    assert client.post("/api/automation/approval-links", headers=BOT).json()["url"].count("/aprovar?t=") == 1


def test_lolos_list_has_no_jobs_only_the_link(db, sql, add_job):
    proposed_job(add_job, sql)
    Auto.create_action("comment", "c1", "Ana", "https://www.linkedin.com/posts/x", {"text": "Oi"}, target_type="engagement", target_id=1)
    text, ids = BotService.inbox()
    assert len(ids) == 1 and "Financial Modeling" not in text and "1 vaga(s) para aprovar pelo link: https://" in text
    only_jobs = BotService.inbox(kind="apply")
    assert only_jobs[1] == [] and "/aprovar?t=" in only_jobs[0]


def test_from_the_internet_only_the_page_answers(db, client):
    funnel = {"Tailscale-Funnel-Request": "?1"}
    assert client.get("/aprovar", headers=funnel).status_code == 200
    assert client.get("/aprovar/api/jobs", headers=funnel).status_code == 401
    assert client.get("/api/automation/status", headers={**funnel, **APPROVER}).status_code == 404
    assert client.get("/health", headers=funnel).status_code == 404
    assert client.get("/aprovarx", headers=funnel).status_code == 404
