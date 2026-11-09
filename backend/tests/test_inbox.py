"""Replies to your comments and the LinkedIn inbox (2026-11-08): the AI is replaced by fixed answers here."""
import asyncio

from app.services import linkedin_inbox_service as inbox
from app.services.linkedin_inbox_service import InboxService, language_policy, notices_given, with_notice


# ── Your rule for the language of the answers ─────────────────────────────
def test_portuguese_and_english_are_answered_in_their_own_language():
    assert language_policy("pt") == {"reply_lang": "pt", "notice": "", "flag": None}
    assert language_policy("en")["reply_lang"] == "en"
    assert language_policy("pt-BR")["reply_lang"] == "pt"


def test_spanish_gets_english_and_the_notice_only_once():
    first = language_policy("es")
    assert first["reply_lang"] == "en" and "understand Spanish" in first["notice"] and first["flag"] == "es"
    again = language_policy("es", es_notice_given=True)
    assert again["reply_lang"] == "en" and again["notice"] == "" and again["flag"] is None


def test_other_languages_get_english_and_the_translator_notice_once():
    first = language_policy("German")
    assert first["reply_lang"] == "en" and "translator" in first["notice"] and "German" in first["notice"]
    assert "real time" in first["notice"] and first["flag"] == "translator"
    assert language_policy("de", translator_notice_given=True)["notice"] == ""


def test_a_notice_already_in_your_messages_is_not_repeated():
    said = notices_given(["Hi! " + inbox.NOTICE_ES, "ok"])
    assert said == {"es": True, "translator": False}
    said = notices_given([inbox.NOTICE_TRANSLATOR.format(language="German")])
    assert said["translator"] is True


def test_the_notice_goes_in_after_the_greeting_and_never_twice():
    text = with_notice("Hi Hans,\nThanks for reaching out.", inbox.NOTICE_ES)
    assert text.startswith("Hi Hans,\n" + inbox.NOTICE_ES)
    assert with_notice(text, inbox.NOTICE_ES) == text
    assert with_notice("Thanks!", "") == "Thanks!"


# ── Fixed AI answers ──────────────────────────────────────────────────────
def fake_ai(monkeypatch, classify=None, answer=None, followup=None):
    seen = []

    async def run(path, context):
        seen.append((path, context))
        if path == "linkedin/reply_followup.md":
            return followup
        return classify if context.get("step") == "classify" else answer
    monkeypatch.setattr(inbox, "_skill", run)
    return seen


def actions(sql, kind):
    return sql("SELECT * FROM public.automation_actions WHERE kind = %s ORDER BY id", (kind,))


# ── Replies to your comments ──────────────────────────────────────────────
def test_a_reply_notice_is_read_once(db, sql):
    notice = {"url": "https://www.linkedin.com/feed/update/urn:li:activity:1/?commentUrn=x", "key": "commentUrn=x", "actor": "Bia Lima"}
    assert InboxService.add_reply_notices([notice, notice]) == 1
    assert InboxService.add_reply_notices([notice]) == 0
    read = actions(sql, "thread_read")
    assert len(read) == 1 and read[0]["status"] == "queued" and read[0]["lane"] == "linkedin_read"


def test_a_reply_with_nothing_to_add_is_only_liked_on_its_own(db, sql, monkeypatch):
    InboxService.add_reply_notices([{"url": "https://www.linkedin.com/feed/update/urn:li:activity:2/", "actor": "Bia"}])
    rid = sql("SELECT id FROM public.linkedin_comment_replies")[0]["id"]
    fake_ai(monkeypatch, followup={"decision": "like", "reason": "só agradeceu", "lang": "en", "reply": ""})
    row = asyncio.run(InboxService.read_reply(rid, "Post", "My comment", "Great point, thanks!", "Bia Lima"))
    assert row["decision"] == "like"
    like = actions(sql, "like")
    assert len(like) == 1 and like[0]["status"] == "queued" and like[0]["approved_at"] is None   # no OK needed, inside the limits
    assert like[0]["payload"]["reply_head"].startswith("Great point")
    assert sql("SELECT event FROM public.automation_events WHERE action_id = %s", (like[0]["id"],))[0]["event"] == "auto_approved"
    assert actions(sql, "reply") == []


def test_a_reply_that_asks_something_waits_for_your_ok(db, sql, monkeypatch):
    InboxService.add_reply_notices([{"url": "https://www.linkedin.com/feed/update/urn:li:activity:3/", "actor": "Bia"}])
    rid = sql("SELECT id FROM public.linkedin_comment_replies")[0]["id"]
    fake_ai(monkeypatch, followup={"decision": "reply", "reason": "fez uma pergunta", "lang": "en", "reply": "Yes, with tertiary treatment."})
    asyncio.run(InboxService.read_reply(rid, "Post", "My comment", "Would reuse work?", "Bia Lima"))
    reply = actions(sql, "reply")
    assert len(reply) == 1 and reply[0]["status"] == "proposed" and reply[0]["payload"]["text"] == "Yes, with tertiary treatment."
    assert reply[0]["payload"]["like"] is True
    assert actions(sql, "like") == []


# ── Inbox ─────────────────────────────────────────────────────────────────
OFFER = {"kind": "chat", "thread_url": "https://www.linkedin.com/messaging/thread/T1/", "name": "Hans Müller", "headline": "CEO, WebAgentur",
         "messages": [{"from": "them", "text": "Wir bieten Webentwicklung und Leadgenerierung an.", "key": "m1"}]}


def test_a_service_offer_is_declined_on_its_own_with_the_translator_notice(db, sql, monkeypatch):
    seen = fake_ai(monkeypatch, classify={"lang": "de", "translation_pt": "Oferecemos desenvolvimento web.", "category": "service_offer",
                                          "confidence": 0.95, "summary": "venda"},
                   answer={"reply": "Hi Hans,\nThank you, but this is not something I need right now. All the best!"})
    out = asyncio.run(InboxService.ingest([OFFER]))
    assert out["declined"] == 1
    msg = actions(sql, "message")[0]
    assert msg["status"] == "queued" and msg["approved_at"] is None
    assert "translator" in msg["payload"]["text"] and "German" in msg["payload"]["text"] and msg["payload"]["notice"] == "translator"
    answer_ctx = [c for p, c in seen if c.get("step") == "answer"][0]
    assert answer_ctx["reply_lang_name"] == "English"
    note = sql("SELECT * FROM public.bot_notifications WHERE kind = 'inbox'")[0]
    assert "recusada" in note["text"] and "Oferecemos desenvolvimento web" in note["text"]
    # the same message seen again by the next scan: nothing new
    assert asyncio.run(InboxService.ingest([OFFER]))["new"] == 0


def test_a_recruiter_gets_a_suggestion_to_approve_and_an_urgent_notice(db, sql, monkeypatch):
    fake_ai(monkeypatch, classify={"lang": "es", "translation_pt": "Temos uma vaga.", "category": "recruiter", "confidence": 0.9},
            answer={"reply": "Hi Ana,\nThanks — I'd be glad to talk. Would Thursday work?"})
    item = {**OFFER, "thread_url": "https://www.linkedin.com/messaging/thread/T2/", "name": "Ana García",
            "messages": [{"from": "them", "text": "Hola, tenemos una vacante para ti.", "key": "a1"}]}
    asyncio.run(InboxService.ingest([item]))
    msg = actions(sql, "message")[0]
    assert msg["status"] == "proposed" and "understand Spanish" in msg["payload"]["text"]
    note = sql("SELECT * FROM public.bot_notifications WHERE kind = 'inbox'")[0]
    assert note["urgent"] and note["data"]["ids"] == [msg["id"]]
    # sent: the Spanish notice is never said again in this conversation
    InboxService.message_sent(msg)
    conv = sql("SELECT * FROM public.linkedin_conversations")[0]
    assert conv["es_notice_given"] is True
    item["messages"].append({"from": "them", "text": "¿Cuándo puedes hablar?", "key": "a2"})
    asyncio.run(InboxService.ingest([item]))
    second = actions(sql, "message")[-1]
    assert "understand Spanish" not in second["payload"]["text"]


def test_an_invitation_is_told_with_translation_and_origin(db, sql, monkeypatch):
    sql("""INSERT INTO public.linkedin_engagement (post_url, author_name, post_text, status) VALUES
           ('https://www.linkedin.com/feed/update/urn:li:activity:9/', 'Hans Müller', 'Wasser', 'done')""")
    fake_ai(monkeypatch, classify={"lang": "de", "translation_pt": "Li seu comentário e gostaria de me conectar.", "category": "networking",
                                   "confidence": 0.8},
            answer={"reply": "Hi Hans, thanks for connecting!"})
    item = {"kind": "invite", "name": "Hans Müller", "headline": "Talent Partner", "profile_url": "https://www.linkedin.com/in/hans/",
            "messages": [{"from": "them", "text": "Hallo Paulo, ich habe Ihren Kommentar gelesen."}]}
    out = asyncio.run(InboxService.ingest([item]))
    assert out["invites"] == 1 and actions(sql, "message") == []   # you accept it yourself
    note = sql("SELECT * FROM public.bot_notifications WHERE kind = 'inbox'")[0]["text"]
    assert "Convite" in note and "Li seu comentário" in note and "comentou um post" in note and "translator" in note


def test_an_automatic_no_that_cites_an_nda_subject_waits_for_you(db, sql, monkeypatch):
    fake_ai(monkeypatch, classify={"lang": "en", "category": "service_offer", "confidence": 0.99},
            answer={"reply": "Thanks, but I work with landfills already."})
    monkeypatch.setattr("app.services.skill_service.SkillService.generate_checked", lambda *a: None)
    asyncio.run(InboxService.ingest([{**OFFER, "messages": [{"from": "them", "text": "We sell web design."}]}]))
    assert actions(sql, "message")[0]["status"] == "proposed"


def test_the_bot_sends_inbox_notices_one_by_one(db, sql, monkeypatch):
    from app.services.bot_service import BotService
    monkeypatch.setattr(BotService, "quiet", staticmethod(lambda: False))
    BotService.notify("inbox", "🎯 Recrutador respondeu", {"ids": [1]}, urgent=True, key="k")
    assert [n["kind"] for n in BotService.pending()] == ["inbox"]


def test_a_scan_can_run_now_and_is_not_doubled(db, sql, client):
    from .conftest import APPROVER
    first = client.post("/api/automation/scans/inbox_scan/run", headers=APPROVER).json()
    again = client.post("/api/automation/scans/inbox_scan/run", headers=APPROVER).json()
    assert first["run_now"] and again["already"] and first["id"] == again["id"]
    assert client.post("/api/automation/scans/apply/run", headers=APPROVER).status_code == 422


# 2026-11-08: Zhenghang Yin (MeeBoss) answered the user's contact with a templated "apply through the job link"
MEEBOSS = {"kind": "chat", "thread_url": "https://www.linkedin.com/messaging/thread/T9/", "name": "Zhenghang Yin",
           "headline": "Software Engineer at MeeBoss", "profile_url": "https://www.linkedin.com/in/ACoAAGtQq8gBYWdJxhHWoa_61bJOY2-EQ-6NkTI",
           "messages": [{"from": "them", "key": "z1", "text": (
               "Hi Paulo, thank you for reaching out.\n\nThe fastest way to connect with the hiring manager for this role is through the link "
               "in the job post. Open the MeeBoss job link and choose \"Chat to Apply\" to contact the hiring manager directly.\n\n"
               "You may also find other roles that interest you here: https://www.meeboss.com/\n\nWishing you the best with the opportunity!")}]}


def test_an_answer_to_your_contact_is_never_declined_on_its_own(db, sql, monkeypatch):
    # even when the classifier gets it wrong (a link to a product, a templated text)
    fake_ai(monkeypatch, classify={"lang": "en", "category": "service_offer", "confidence": 0.95},
            answer={"reply": "Thanks, but not interested."})
    out = asyncio.run(InboxService.ingest([MEEBOSS]))
    assert out["declined"] == 0
    msg = actions(sql, "message")[0]
    assert msg["status"] == "proposed"   # waits for your OK


def test_a_redirect_gets_a_short_thanks_and_a_task_for_you(db, sql, monkeypatch):
    sql("""INSERT INTO public.linkedin_prospects (profile_url, name, status, message_sent_at)
           VALUES ('https://www.linkedin.com/in/zhenghang-yin/', 'Zhenghang Yin', 'replied', NOW())""")
    fake_ai(monkeypatch, classify={"lang": "en", "category": "redirect", "confidence": 0.9,
                                   "todo": "Candidate-se pelo link da vaga no MeeBoss, opção Chat to Apply."},
            answer={"reply": "Thanks for the heads-up! I'll follow your tip and reach out through the job link."})
    asyncio.run(InboxService.ingest([MEEBOSS]))
    msg = actions(sql, "message")[0]
    assert msg["status"] == "proposed" and "heads-up" in msg["payload"]["text"]
    assert "translator" not in msg["payload"]["text"] and "Spanish" not in msg["payload"]["text"]   # English: no notice
    note = sql("SELECT * FROM public.bot_notifications WHERE kind = 'inbox'")[0]
    assert note["urgent"] and "Chat to Apply" in note["text"] and "prospecção" in note["text"]   # found by name: the link is /in/ACoAA…


def test_the_scan_is_answered_at_once_and_the_analysis_goes_on(db, sql, client, monkeypatch):
    from .conftest import WORKER
    fake_ai(monkeypatch, classify={"lang": "en", "category": "networking", "confidence": 0.9}, answer={"reply": "Thanks!"})
    res = client.post("/api/automation/inbox-items", headers=WORKER, json={"items": [OFFER]})
    assert res.status_code == 200 and res.json() == {"accepted": 1}
    waited = client.post("/api/automation/inbox-items?wait=true", headers=WORKER, json={"items": [OFFER]})
    assert waited.status_code == 200 and "new" in waited.json()
