"""Lolo (WhatsApp): what it is told, what it may decide for you, and what the e-mails it passes on do."""
import pytest

from app.services import bot_service
from app.services import email_monitor_service as em
from app.services.automation_service import AutomationService as Auto, _one
from app.services.bot_service import BotService, normalize_post_url, parse_post_page
from app.services.email_monitor_service import EmailMonitorService as Monitor
from tests.conftest import APPROVER, BOT


def proposed_comment(key="c1", text="Ótimo ponto"):
    return Auto.create_action("comment", key, "Ana", "https://www.linkedin.com/posts/ana_x-activity-1-a/",
                              {"text": text, "post_head": "", "post_url": "x", "author": "Ana"}, target_type="engagement", target_id=1, rank=10)


def notes(sql, kind=None):
    rows = sql("SELECT * FROM public.bot_notifications ORDER BY id")
    return [r for r in rows if kind is None or r["kind"] == kind]


@pytest.fixture
def awake(monkeypatch):
    monkeypatch.setattr(BotService, "quiet", staticmethod(lambda: False))


# ── What the bot may do ──────────────────────────────────────────────────
def test_the_bot_decides_but_never_changes_the_mode_the_account_or_the_limits(db, client):
    action = proposed_comment()
    assert client.post(f"/api/automation/actions/{action['id']}/approve", json={}, headers=BOT).status_code == 200
    assert client.patch("/api/automation/state", json={"mode": "live"}, headers=BOT).status_code == 401
    assert client.put("/api/automation/limits/apply", json={"step0": 99, "step1": 99, "step2": 99}, headers=BOT).status_code == 401
    assert client.post("/api/automation/halt", json={"reason": "pelo WhatsApp"}, headers=BOT).status_code == 200
    assert client.post("/api/automation/resume", headers=BOT).status_code == 200


def test_only_the_bot_takes_its_notifications(db, client):
    assert client.get("/api/automation/bot/notifications", headers=APPROVER).status_code == 401
    assert client.get("/api/automation/bot/notifications", headers=BOT).status_code == 200


# ── What it is told ──────────────────────────────────────────────────────
def test_new_proposals_come_together_once(db, sql, awake):
    a, b = proposed_comment("c1"), proposed_comment("c2", "Outro ponto")
    BotService.collect()
    BotService.collect()
    digest = notes(sql, "proposals")
    assert len(digest) == 1
    assert f"#{a['id']}" in digest[0]["text"] and f"#{b['id']}" in digest[0]["text"] and "Outro ponto" in digest[0]["text"]


def test_the_digest_links_to_the_approval_list(db, sql, awake):
    proposed_comment("c1")
    BotService.collect()
    assert "/automacao?tab=aprovar" in notes(sql, "proposals")[0]["text"]


def test_a_long_digest_comes_one_message_per_kind(db, sql, add_job, awake):
    comments = [proposed_comment(f"c{i}", f"Ponto {i}") for i in range(6)]
    jobs = [Auto.propose_job(add_job(job_id=str(200 + i), status="new")) for i in range(4)]
    sql("UPDATE public.job_listings SET triage_score = 88, eligibility_status = 'blocked', "
        "eligibility_issues = '[{\"type\": \"residency\", \"quote\": \"US only\"}]'::jsonb")
    BotService.collect()
    digest = notes(sql, "proposals")
    assert [d["data"]["kind"] for d in digest] == ["apply", "comment"]
    vagas, posts = digest[0]["text"], digest[1]["text"]
    assert "Vagas" in vagas and "&tipo=apply" in vagas and all(f"#{j['id']}" in vagas for j in jobs)
    assert "fit 88" in vagas and "🔴 residência" in vagas
    assert "&tipo=comment" in posts and all(f"#{c['id']}" in posts for c in comments) and "#" + str(jobs[0]["id"]) not in posts


def test_a_short_digest_stays_one_message(db, sql, add_job, awake):
    proposed_comment("c1")
    Auto.propose_job(add_job(status="new"))
    BotService.collect()
    assert len(notes(sql, "proposals")) == 1


def test_the_inbox_is_one_list_with_a_fit_for_every_kind(db, add_job):
    comment = Auto.create_action("comment", "c9", "Ana", "https://www.linkedin.com/posts/x", {"text": "Oi", "relevance": 77}, target_type="engagement", target_id=1, rank=10)
    person = Auto.create_action("connect", "p1", "Bia", "https://www.linkedin.com/in/bia", {"name": "Bia", "fit": 90}, target_type="url", rank=20)
    box = Auto.inbox()
    fits = {i["id"]: i["fit"] for i in box["items"]}
    assert fits == {comment["id"]: 77, person["id"]: 90}


def test_a_new_digest_waits_for_the_interval(db, sql, awake):
    proposed_comment("c1")
    BotService.collect()
    proposed_comment("c2")
    BotService.collect()
    assert len(notes(sql, "proposals")) == 1
    sql("UPDATE public.bot_notifications SET created_at = NOW() - INTERVAL '2 hours'")
    BotService.collect()
    assert len(notes(sql, "proposals")) == 2


def test_needs_you_is_told_once_per_time_it_happens(db, sql, awake):
    action = proposed_comment()
    Auto._to_user(action["id"], "unknown_required_question", "Pergunta nova", [{"label": "Notice period?", "options": ["30", "60"]}])
    BotService.collect()
    BotService.collect()
    told = notes(sql, "action_needs_user")
    assert len(told) == 1 and "Notice period?" in told[0]["text"] and "30, 60" in told[0]["text"]
    sql("UPDATE public.automation_actions SET status = 'queued' WHERE id = %s", (action["id"],))
    BotService.collect()
    Auto._to_user(action["id"], "unknown_required_question", "De novo")
    BotService.collect()
    assert len(notes(sql, "action_needs_user")) == 2


def test_a_cv_to_review_comes_with_its_files(db, sql, add_job, awake):
    job = add_job(status="new")
    action = Auto.propose_job(job)
    sql("UPDATE public.automation_actions SET status = 'review_docs' WHERE id = %s", (action["id"],))
    BotService.collect()
    note = notes(sql, "action_review_docs")[0]
    assert [f["path"] for f in note["data"]["files"]] == [f"/api/jobs/{job['id']}/document.pdf?kind=resume", f"/api/jobs/{job['id']}/document.pdf?kind=cover"]


def test_a_stop_is_urgent_and_told_once(db, sql):
    Auto.halt("checkpoint: verificação", ["linkedin_read", "linkedin_write"], source="worker")
    BotService.collect()
    BotService.collect()
    told = notes(sql, "halt")
    assert len(told) == 1 and told[0]["urgent"] and "religar" in told[0]["text"]


def test_at_night_only_what_is_urgent_goes(db, monkeypatch):
    BotService.notify("proposals", "para aprovar")
    BotService.notify("halt", "parou", urgent=True)
    monkeypatch.setattr(BotService, "quiet", staticmethod(lambda: True))
    assert [n["text"] for n in BotService.pending()] == ["parou"]
    monkeypatch.setattr(BotService, "quiet", staticmethod(lambda: False))
    pending = BotService.pending()
    assert len(pending) == 2
    assert BotService.ack([n["id"] for n in pending]) == 2 and BotService.pending() == []


# ── E-mails Lolo passes on ───────────────────────────────────────────────
def fake_reader(monkeypatch, reading):
    async def run_skill(path, context, response_format="json"):
        return reading
    monkeypatch.setattr(em.SkillService, "run_skill", staticmethod(run_skill))


def message(mid="<1@x>", sender="Acme Careers <careers@acme.com>", subject="Your application", body="Thank you for applying"):
    return {"message_id": mid, "sender": sender, "subject": subject, "body": body}


def test_ingest_from_the_bot_reads_like_the_mailbox(db, sql, client, add_job, monkeypatch):
    add_job(status="applied")
    fake_reader(monkeypatch, {"classification": "confirmation", "confidence": 0.9, "summary": "Recebida", "evidence": "Thank you"})
    r = client.post("/api/automation/email/ingest", json={"messages": [message()]}, headers=BOT)
    assert r.status_code == 200 and r.json()["recorded"] == 1 and r.json()["baseline"] is True
    r = client.post("/api/automation/email/ingest", json={"messages": [message(), message("<2@x>")]}, headers=BOT)
    assert r.json()["recorded"] == 1 and r.json()["baseline"] is False
    assert sql("SELECT source FROM public.job_email_events")[0]["source"] == "lolo"


def test_specific_feedback_becomes_a_grouped_suggestion(db, sql, add_job, monkeypatch, awake):
    add_job(status="applied")
    fake_reader(monkeypatch, {"classification": "rejection", "confidence": 0.95, "summary": "Não seguiram", "evidence": "We need Kubernetes",
                              "feedback": [{"target": "cv", "theme": "habilidade técnica", "suggestion": "Mostrar Kubernetes no CV",
                                            "evidence": "We need hands-on Kubernetes"},
                                           {"target": "x", "theme": "inventado", "suggestion": "Melhorar inglês falado"}]})
    stats = Monitor.process([message()])
    assert stats["feedback"] == 2
    groups = {(g["target"], g["theme"]): g["n"] for g in BotService.suggestions()}
    assert groups == {("cv", "habilidade técnica"): 1, ("me", "outro"): 1}
    told = notes(sql, "email_rejection")[0]["text"]
    assert "Mostrar Kubernetes no CV" in told and "Sugestões" in told


def test_a_generic_no_brings_no_suggestion(db, sql, add_job, monkeypatch):
    add_job(status="applied")
    fake_reader(monkeypatch, {"classification": "rejection", "confidence": 0.95, "summary": "Não seguiram", "evidence": "other candidates", "feedback": []})
    assert Monitor.process([message()])["feedback"] == 0
    assert BotService.suggestions() == []


def test_a_linkedin_warning_by_email_stops_the_linkedin_lanes(db, sql, monkeypatch):
    fake_reader(monkeypatch, {"classification": "linkedin_alert", "alert_kind": "unusual_activity", "confidence": 0.95,
                              "summary": "Atividade incomum na conta", "evidence": "unusual activity"})
    Monitor.process([message(sender="LinkedIn <security-noreply@linkedin.com>", subject="Unusual activity on your account")])
    state = Auto.state()
    assert state["halted_at"] and set(state["halted_lanes"]) == {"linkedin_read", "linkedin_write"} and state["ramp_step"] == 1
    told = notes(sql, "linkedin_alert")
    assert told[0]["urgent"] and "Parei a automação" in told[0]["text"]


def test_a_verification_code_only_tells_you(db, sql, monkeypatch):
    fake_reader(monkeypatch, {"classification": "linkedin_alert", "alert_kind": "verification_code", "confidence": 0.99, "summary": "Código"})
    Monitor.process([message(sender="security-noreply@linkedin.com", subject="Your verification code")])
    assert not Auto.state()["halted_at"]
    assert not notes(sql, "linkedin_alert")[0]["urgent"]


def test_only_linkedin_speaks_for_the_account(db, sql, monkeypatch):
    fake_reader(monkeypatch, {"classification": "linkedin_alert", "alert_kind": "restriction", "confidence": 0.99, "summary": "Conta restrita"})
    Monitor.process([message(sender="phish@linkedln-security.com", subject="Your application: account restricted")])
    assert not Auto.state()["halted_at"]
    assert sql("SELECT classification FROM public.job_email_events")[0]["classification"] == "other"


def test_the_gmail_query_names_the_companies_you_applied_to(db, add_job):
    add_job(status="applied", company="Globex Corporation")
    q = Monitor.gmail_query(3)
    assert q.startswith("newer_than:3d") and "globex" in q and "security-noreply@linkedin.com" in q


# ── A post you sent to be commented ──────────────────────────────────────
@pytest.mark.parametrize("url,expected", [
    ("https://www.linkedin.com/posts/ana_dados-activity-7123-AbCd?utm_source=share", "https://www.linkedin.com/posts/ana_dados-activity-7123-AbCd/"),
    ("linkedin.com/feed/update/urn:li:activity:7123/", "https://www.linkedin.com/feed/update/urn:li:activity:7123/"),
])
def test_post_links_are_normalized(url, expected):
    assert normalize_post_url(url) == expected


@pytest.mark.parametrize("url", ["https://evil.com/posts/x", "https://www.linkedin.com/in/ana/", "https://www.linkedin.com/pulse/artigo",
                                 "http://169.254.169.254/latest", "https://www.linkedin.com.evil.com/posts/x"])
def test_anything_but_a_post_is_refused(url):
    with pytest.raises(ValueError):
        normalize_post_url(url)


def test_the_post_text_comes_from_the_page_data():
    page = '<script type="application/ld+json">{"@type":"SocialMediaPosting","articleBody":"Dados &amp; IA","author":{"name":"Ana"}}</script>'
    assert parse_post_page(page) == {"text": "Dados & IA", "author": "Ana"}
    page = '<meta property="og:title" content="Ana Souza on LinkedIn: Dados"><meta property="og:description" content="Texto do post">'
    assert parse_post_page(page) == {"text": "Texto do post", "author": "Ana Souza"}


@pytest.fixture
def drafted(monkeypatch, sql):
    """The comment AI, replaced: it writes from your suggestion and records the post like the real one."""
    calls = []

    async def add_engagement(post_text, post_url=None, author_name=None, author_headline=None, other_comments=None, instruction=None, regenerate=False):
        calls.append({"post_text": post_text, "instruction": instruction})
        row = sql("SELECT * FROM public.linkedin_engagement WHERE post_url = %s", (post_url,))
        if row:
            return sql("UPDATE public.linkedin_engagement SET comment_draft = %s, status = 'pending' WHERE id = %s RETURNING *",
                       (f"Comentário: {instruction}", row[0]["id"]))[0]
        return sql("""INSERT INTO public.linkedin_engagement (post_url, author_name, post_text, comment_draft, status, relevance)
                      VALUES (%s, %s, %s, %s, 'pending', 80) RETURNING *""", (post_url, author_name, post_text, f"Comentário: {instruction}"))[0]

    from app.services.linkedin_copilot_service import LinkedInCopilotService
    monkeypatch.setattr(LinkedInCopilotService, "add_engagement", staticmethod(add_engagement))
    monkeypatch.setattr(bot_service, "fetch_public_post", lambda url: {"text": "Post público sobre dados", "author": "Ana"})
    return calls


URL = "https://www.linkedin.com/posts/ana_dados-activity-7123-AbCd/"


def test_a_link_with_your_idea_becomes_a_comment_to_approve(db, sql, client, drafted, awake):
    r = client.post("/api/automation/bot/comment-link", json={"url": URL + "?utm=x", "suggestion": "concordar e citar Monte Carlo"}, headers=BOT)
    body = r.json()
    assert r.status_code == 200 and body["ok"] and body["text"] == "Comentário: concordar e citar Monte Carlo" and body["author"] == "Ana"
    assert drafted[0]["post_text"] == "Post público sobre dados"
    action = _one("SELECT * FROM public.automation_actions WHERE id = %s", (body["action_id"],))
    assert action["status"] == "proposed" and action["target_url"] == URL and action["payload"]["post_head"] == ""
    BotService.collect()
    assert notes(sql, "proposals") == []   # you already saw the draft in the answer
    assert client.post(f"/api/automation/actions/{body['action_id']}/approve", json={}, headers=BOT).json()["status"] == "queued"


def test_a_link_alone_is_drafted_from_the_post(db, client, drafted):
    body = client.post("/api/automation/bot/comment-link", json={"url": URL}, headers=BOT).json()
    assert body["ok"] and drafted[0]["instruction"] == "O Paulo escolheu este post para comentar."


def test_a_post_that_needs_a_login_asks_for_the_text(db, client, drafted, monkeypatch):
    monkeypatch.setattr(bot_service, "fetch_public_post", lambda url: {})
    body = client.post("/api/automation/bot/comment-link", json={"url": URL}, headers=BOT).json()
    assert body == {"ok": False, "need": "post_text", "detail": body["detail"]} and not drafted
    body = client.post("/api/automation/bot/comment-link", json={"url": URL, "post_text": "Texto colado"}, headers=BOT).json()
    assert body["ok"] and drafted[0]["post_text"] == "Texto colado"


def test_sending_the_same_post_again_redrafts_the_same_comment(db, sql, client, drafted):
    first = client.post("/api/automation/bot/comment-link", json={"url": URL}, headers=BOT).json()
    second = client.post("/api/automation/bot/comment-link", json={"url": URL, "suggestion": "mais curto"}, headers=BOT).json()
    assert second["action_id"] == first["action_id"] and second["text"] == "Comentário: mais curto"
    assert sql("SELECT COUNT(*) AS n FROM public.automation_actions WHERE kind = 'comment'")[0]["n"] == 1
    sql("UPDATE public.automation_actions SET status = 'done'")
    again = client.post("/api/automation/bot/comment-link", json={"url": URL}, headers=BOT).json()
    assert not again["ok"] and "já comentou" in again["detail"]


def test_a_forbidden_term_never_reaches_the_queue(db, client, drafted):
    body = client.post("/api/automation/bot/comment-link", json={"url": URL, "suggestion": "falar de aterro sanitário"}, headers=BOT).json()
    r = client.post(f"/api/automation/actions/{body['action_id']}/approve", json={}, headers=BOT)
    assert r.status_code == 422


# ── What Lolo does with each message in Gmail ────────────────────────────
def test_a_confirmation_is_archived_and_listed(db, sql, client, add_job, monkeypatch, awake):
    add_job(status="applied", title="Data Analyst")
    fake_reader(monkeypatch, {"classification": "confirmation", "confidence": 0.95, "summary": "Recebida", "evidence": "Thank you"})
    sent = {"messages": [message()], "baseline": False}
    r = client.post("/api/automation/email/ingest", json=sent, headers=BOT).json()
    assert r["archive"] == ["<1@x>"]
    told = notes(sql, "email_summary")[0]["text"]
    assert "li e arquivei" in told and "Data Analyst · Acme — recebida" in told
    # not archived yet (Lolo stopped halfway): handed back on the next run, until Lolo says it is done
    assert client.post("/api/automation/email/ingest", json=sent, headers=BOT).json()["archive"] == ["<1@x>"]
    assert client.post("/api/automation/email/archived", json={"message_ids": ["<1@x>"]}, headers=BOT).json() == {"marked": 1}
    assert client.post("/api/automation/email/ingest", json=sent, headers=BOT).json()["archive"] == []


def test_a_next_step_stays_in_the_inbox_and_says_so(db, sql, client, add_job, monkeypatch, awake):
    add_job(status="applied")
    fake_reader(monkeypatch, {"classification": "interview", "confidence": 0.95, "summary": "Convite para conversa", "evidence": "schedule"})
    r = client.post("/api/automation/email/ingest", json={"messages": [message()], "baseline": False}, headers=BOT).json()
    assert r["archive"] == []
    assert sql("SELECT mail_action FROM public.job_email_events")[0]["mail_action"] == "keep"
    told = notes(sql, "email_interview")[0]
    assert told["urgent"] and "Convite para conversa" in told["text"] and "caixa de entrada" in told["text"]


def test_a_rejection_is_archived_and_told(db, sql, client, add_job, monkeypatch, awake):
    add_job(status="applied")
    fake_reader(monkeypatch, {"classification": "rejection", "confidence": 0.95, "summary": "Seguiram com outros", "evidence": "other", "feedback": []})
    r = client.post("/api/automation/email/ingest", json={"messages": [message()], "baseline": False}, headers=BOT).json()
    assert r["archive"] == ["<1@x>"] and "Li e arquivei" in notes(sql, "email_rejection")[0]["text"]


def test_an_unsure_reading_is_never_archived(db, client, add_job, monkeypatch):
    add_job(status="applied")
    fake_reader(monkeypatch, {"classification": "rejection", "confidence": 0.6, "summary": "Talvez", "evidence": "x"})
    assert client.post("/api/automation/email/ingest", json={"messages": [message()], "baseline": False}, headers=BOT).json()["archive"] == []


def test_the_imap_check_never_touches_the_mailbox(db, sql, add_job, monkeypatch):
    add_job(status="applied")
    fake_reader(monkeypatch, {"classification": "confirmation", "confidence": 0.99, "summary": "Recebida"})
    assert Monitor.process([message()])["archive"] == []
    assert sql("SELECT mail_action FROM public.job_email_events")[0]["mail_action"] is None


# ── The job status, told in the same message ─────────────────────────────
@pytest.fixture
def auto_status(db, monkeypatch):
    cfg = {**db, "email": {**db["email"], "auto_status": True}}
    monkeypatch.setattr(em, "config", lambda: cfg)
    monkeypatch.setattr(bot_service, "config", lambda: cfg)


def test_a_rejection_moves_the_job_and_says_so(db, sql, add_job, monkeypatch, awake, auto_status):
    job = add_job(status="applied")
    fake_reader(monkeypatch, {"classification": "rejection", "confidence": 0.95, "summary": "Seguiram com outros", "evidence": "x"})
    Monitor.process([message()], source="lolo")
    assert sql("SELECT status FROM public.job_listings WHERE id = %s", (job["id"],))[0]["status"] == "rejected"
    assert "candidatura enviada → *recusada*" in notes(sql, "email_rejection")[0]["text"]


def test_an_interview_moves_the_job_and_says_so(db, sql, add_job, monkeypatch, awake, auto_status):
    add_job(status="applied")
    fake_reader(monkeypatch, {"classification": "interview", "confidence": 0.9, "summary": "Convite", "evidence": "x"})
    Monitor.process([message()], source="lolo")
    assert "candidatura enviada → *em entrevista*" in notes(sql, "email_interview")[0]["text"]


def test_when_nothing_moves_it_says_why(db, sql, add_job, monkeypatch, awake, auto_status):
    add_job(status="applied")
    fake_reader(monkeypatch, {"classification": "rejection", "confidence": 0.6, "summary": "Talvez", "evidence": "x"})
    Monitor.process([message("<a>")], source="lolo")
    fake_reader(monkeypatch, {"classification": "rejection", "confidence": 0.99, "summary": "Não", "evidence": "x"})
    Monitor.process([message("<b>", sender="x@greenhouse.io", subject="Update")], source="lolo")
    unsure, unknown = [n["text"] for n in notes(sql, "email_rejection")]
    assert "Não tenho certeza" in unsure and "Não achei a vaga" in unknown
