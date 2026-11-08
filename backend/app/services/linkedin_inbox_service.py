"""Replies to your comments, and the LinkedIn inbox (invitations and conversations).

Replies: the reply_scan reads the notifications page; each new "X replied to your comment" becomes a thread_read that
opens the post and sends back the post, your comment and the reply. The AI decides: nothing more to say → a like (goes on
its own); something to answer → a reply that waits for your OK (and likes the comment too).

Inbox: the inbox_scan reads the received invitations and the unread conversations. Each new message gets its language,
a translation into Portuguese, where the person likely came from (what CareerOps did with them), a category and a
suggested answer. A service offer is turned down politely on its own; a recruiter's message becomes an answer to approve;
an invitation is told to you (you accept it yourself) with the message to send once you do.

Language of the answers (your rule, 2026-11-08): Portuguese → Portuguese, English → English. Spanish → English, saying
once in the conversation that you understand Spanish but write better in English. Any other language → English, saying
once that you read it with a translator and they may keep writing in their language (the translation is in real time).
"""
import logging
import re
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json

from app.services.automation_service import AutomationService, _one, _rows, config

log = logging.getLogger("linkedin_inbox")

LANG_NAMES = {"pt": "Portuguese", "en": "English", "es": "Spanish", "de": "German", "fr": "French", "it": "Italian", "nl": "Dutch",
              "pl": "Polish", "sv": "Swedish", "da": "Danish", "no": "Norwegian", "fi": "Finnish", "ru": "Russian", "tr": "Turkish",
              "ar": "Arabic", "hi": "Hindi", "ja": "Japanese", "zh": "Chinese", "ko": "Korean", "ro": "Romanian", "cs": "Czech"}
# redirect (2026-11-08, Zhenghang Yin / MeeBoss): an answer to your contact that points you somewhere else (the job link,
# a form, another person). A short thanks ("thanks for the heads-up, I'll follow your tip") and a task for you.
CATEGORIES = ("recruiter", "redirect", "service_offer", "networking", "job_seeker", "other")
# they answer something of yours: never turned down on its own, whatever the classifier says
ANSWERS_YOU = re.compile(r"thank(s| you) for (reaching out|your (message|interest|note|outreach)|getting in touch|connecting)|"
                         r"obrigad[oa] pelo (contato|interesse|seu contato)|gracias por (contactar|tu mensaje|tu inter[eé]s)|"
                         r"danke f[uü]r (ihre|deine) (nachricht|anfrage)|merci pour votre message", re.I)

NOTICE_ES = "Just a quick note: I understand Spanish perfectly well, but I write better in English, so I'll answer in English."
NOTICE_TRANSLATOR = ("I read your message with a translator, so I'm answering in English — please feel free to keep writing in {language}, "
                     "the translation is in real time.")
# your earlier messages already said it: never twice in the same conversation
SAID_ES = re.compile(r"understand spanish|entiendo (el )?espa[nñ]ol", re.I)
SAID_TRANSLATOR = re.compile(r"\btranslat(or|ion|ing)\b.{0,80}(real[- ]time|keep writing)|tradutor|traductor", re.I | re.S)


def _cfg() -> dict:
    return (config().get("inbox") or {})


def lang_code(value: Optional[str]) -> str:
    """'de', 'German', 'pt-BR' → ISO-639-1. Unknown → ''."""
    v = (value or "").strip().lower()
    if not v:
        return ""
    if len(v) >= 2 and v[:2] in LANG_NAMES and (len(v) == 2 or v[2] in "-_"):
        return v[:2]
    for code, name in LANG_NAMES.items():
        if v == name.lower() or v.startswith(name.lower()[:5]):
            return code
    return {"português": "pt", "portugues": "pt", "inglês": "en", "espanhol": "es", "español": "es", "deutsch": "de", "alemão": "de"}.get(v, "")


def language_policy(lang: str, es_notice_given: bool = False, translator_notice_given: bool = False) -> dict:
    """In which language to answer and what to say about it, once per conversation."""
    code = lang_code(lang) or "en"
    if code in ("pt", "en"):
        return {"reply_lang": code, "notice": "", "flag": None}
    if code == "es":
        return {"reply_lang": "en", "notice": "" if es_notice_given else NOTICE_ES, "flag": None if es_notice_given else "es"}
    name = LANG_NAMES.get(code, "your language")
    return {"reply_lang": "en", "notice": "" if translator_notice_given else NOTICE_TRANSLATOR.format(language=name),
            "flag": None if translator_notice_given else "translator"}


def notices_given(my_messages: List[str]) -> Dict[str, bool]:
    text = "\n".join(my_messages or [])
    return {"es": bool(SAID_ES.search(text)), "translator": bool(SAID_TRANSLATOR.search(text))}


def with_notice(text: str, notice: str) -> str:
    """The notice goes in once, after a greeting line when there is one. The AI is asked to include it; this makes sure."""
    text = (text or "").strip()
    if not notice:
        return text
    key = notice.split(",")[0][:30].lower()
    if key in text.lower():
        return text
    first, _, rest = text.partition("\n")
    if rest and len(first) < 60 and re.match(r"^(hi|hello|dear|hey|good (morning|afternoon|evening))\b", first, re.I):
        return f"{first}\n{notice}\n{rest.lstrip()}"
    return f"{notice}\n\n{text}" if text else notice


def _slug(url: Optional[str]) -> str:
    m = re.search(r"/in/([^/?#]+)", url or "")
    return m.group(1).lower() if m else ""


def _name_key(name: Optional[str]) -> str:
    import unicodedata
    plain = unicodedata.normalize("NFKD", (name or "").lower()).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z ]+", " ", plain).split()[:2])


def origin_of(name: Optional[str], profile_url: Optional[str]) -> str:
    """What CareerOps did with this person before, read from its own tables. Empty when nothing is known."""
    slug, key = _slug(profile_url), _name_key(name)
    found: List[str] = []
    if slug:
        p = _one("""SELECT status, created_at FROM public.linkedin_prospects WHERE lower(profile_url) LIKE %s ORDER BY id DESC LIMIT 1""",
                 (f"%/in/{slug}%",))
        if p:
            found.append(f"estava na sua lista de prospecção (status: {p['status']}, desde {p['created_at']:%d/%m})")
        a = _one("""SELECT kind, finished_at FROM public.automation_actions WHERE kind IN ('connect', 'follow') AND status = 'done'
                     AND lower(target_url) LIKE %s ORDER BY id DESC LIMIT 1""", (f"%/in/{slug}%",))
        if a:
            found.append(("a automação enviou convite a essa pessoa" if a["kind"] == "connect" else "a automação passou a seguir essa pessoa")
                         + (f" em {a['finished_at']:%d/%m}" if a.get("finished_at") else ""))
    if key and not any("prospecção" in f for f in found):   # by name: the link may be /in/ACoAA… (no slug to match)
        p = next((x for x in _rows("""SELECT name, status, message_sent_at, company, headline, created_at FROM public.linkedin_prospects
                                        WHERE name IS NOT NULL ORDER BY id DESC LIMIT 2000""") if _name_key(x["name"]) == key), None)
        if p:
            bits = [f"status: {p['status']}"] + ([f"mensagem sua em {p['message_sent_at']:%d/%m}"] if p.get("message_sent_at") else [])
            found.append(f"estava na sua lista de prospecção ({', '.join(bits)})")
    if key:   # by name, accents and case aside (Müller = Muller): compared here, over the recent rows
        e = next((x for x in _rows("""SELECT post_url, author_name, created_at FROM public.linkedin_engagement
                                        WHERE status = 'done' AND author_name IS NOT NULL ORDER BY id DESC LIMIT 1000""")
                  if _name_key(x["author_name"]) == key), None)
        if e:
            found.append(f"você comentou um post dessa pessoa ({e['created_at']:%d/%m}): {e['post_url']}")
        r = next((x for x in _rows("""SELECT post_url, reply_author, created_at FROM public.linkedin_comment_replies
                                        WHERE reply_author IS NOT NULL ORDER BY id DESC LIMIT 1000""")
                  if _name_key(x["reply_author"]) == key), None)
        if r:
            found.append(f"essa pessoa respondeu a um comentário seu ({r['created_at']:%d/%m}): {r['post_url']}")
    return "; ".join(found)


async def _skill(path: str, context: Dict[str, Any]) -> dict:
    from app.services.linkedin_copilot_service import _skill as run
    return await run(path, context)


class InboxService:
    # ── Replies to your comments ─────────────────────────────────────────
    @staticmethod
    def add_reply_notices(notices: List[Dict[str, Any]]) -> int:
        """From the notifications page: one thread_read per notice not seen before."""
        made = 0
        for n in notices:
            url = (n.get("url") or "").strip()
            if "linkedin.com" not in url:
                continue
            key = (n.get("key") or url)[:500]
            row = _one("""INSERT INTO public.linkedin_comment_replies (notice_key, post_url, notice_text, reply_author)
                          VALUES (%s, %s, %s, %s) ON CONFLICT (notice_key) DO NOTHING RETURNING *""",
                       (key, url, (n.get("text") or "")[:1000], (n.get("actor") or "")[:200] or None))
            if row:
                made += bool(AutomationService.create_action(
                    "thread_read", f"thread_read:{row['id']}", f"Resposta de {row.get('reply_author') or 'alguém'}", url,
                    {"reply_id": row["id"], "actor": row.get("reply_author")}, status="queued", target_type="comment_reply",
                    target_id=row["id"], rank=44))
        return made

    @staticmethod
    async def read_reply(reply_id: int, post_text: str, my_comment: str, reply_text: str, reply_author: Optional[str] = None,
                         post_author: Optional[str] = None, thread: Optional[str] = None) -> Optional[dict]:
        """The thread was read: the AI decides between a like and an answer, and the action is made."""
        row = _one("SELECT * FROM public.linkedin_comment_replies WHERE id = %s", (reply_id,))
        if not row:
            return None
        if row["status"] not in ("new", "failed"):
            return row
        author = reply_author or row.get("reply_author")
        ai = await _skill("linkedin/reply_followup.md", {
            "post_text": (post_text or "")[:4000], "post_author": post_author, "my_comment": (my_comment or "")[:2000],
            "reply_text": (reply_text or "")[:2000], "reply_author": author, "thread": (thread or "")[:4000],
        })
        decision = ai.get("decision") if ai.get("decision") in ("like", "reply", "ignore") else "like"
        draft = (ai.get("reply") or "").strip()
        if decision == "reply" and not draft:
            decision = "like"
        status = "proposed" if decision in ("like", "reply") else "skipped"
        row = _one("""UPDATE public.linkedin_comment_replies
                         SET post_text = %s, post_author = %s, my_comment = %s, reply_text = %s, reply_author = %s, decision = %s,
                             reason = %s, draft = %s, lang = %s, status = %s, updated_at = NOW()
                       WHERE id = %s RETURNING *""",
                   (post_text, post_author, my_comment, reply_text, author, decision, ai.get("reason"), draft or None,
                    lang_code(ai.get("lang")) or None, status, reply_id))
        payload = {"reply_id": reply_id, "post_url": row["post_url"], "reply_author": author, "reply_head": (reply_text or "")[:300],
                   "my_comment": (my_comment or "")[:600], "post_head": (post_text or "")[:300], "reason": ai.get("reason")}
        if decision == "like":
            # nothing to add: a like is enough, and it goes on its own
            AutomationService.create_action("like", f"like:reply:{reply_id}", f"Curtir resposta de {author or 'alguém'}", row["post_url"],
                                            payload, status="queued", target_type="comment_reply", target_id=reply_id, rank=12,
                                            auto=True)
        elif decision == "reply":
            AutomationService.create_action("reply", f"reply:{reply_id}", author or "Resposta", row["post_url"],
                                            {**payload, "text": draft, "like": True}, target_type="comment_reply", target_id=reply_id, rank=9)
        return row

    # ── Inbox: invitations and conversations ─────────────────────────────
    @staticmethod
    async def analyze(kind: str, name: Optional[str], headline: Optional[str], messages: List[Dict[str, Any]],
                      profile_url: Optional[str] = None, es_given: Optional[bool] = None, tr_given: Optional[bool] = None,
                      instruction: Optional[str] = None) -> dict:
        """Language, translation, category, origin and the suggested answer, for an invitation or a conversation.
        messages: [{"from": "me"|"them", "text": "..."}], oldest first."""
        theirs = [m.get("text") or "" for m in messages if m.get("from") != "me"]
        mine = [m.get("text") or "" for m in messages if m.get("from") == "me"]
        said = notices_given(mine)
        es_given = said["es"] if es_given is None else (es_given or said["es"])
        tr_given = said["translator"] if tr_given is None else (tr_given or said["translator"])
        origin = origin_of(name, profile_url)
        history = "\n".join(f"{'ME' if m.get('from') == 'me' else (name or 'THEM')}: {m.get('text')}" for m in messages[-20:])
        # the language is decided first, then the answer is written in it (two steps: the rule is not left to the model)
        ai = await _skill("linkedin/inbox_assist.md", {
            "kind": kind, "name": name, "headline": headline, "history": history[:8000], "last": (theirs[-1] if theirs else "")[:3000],
            "origin": origin, "instruction": (instruction or "")[:1000], "step": "classify",
        })
        lang = lang_code(ai.get("lang")) or "en"
        policy = language_policy(lang, es_given, tr_given)
        category = ai.get("category") if ai.get("category") in CATEGORIES else "other"
        answer = await _skill("linkedin/inbox_assist.md", {
            "kind": kind, "name": name, "headline": headline, "history": history[:8000], "last": (theirs[-1] if theirs else "")[:3000],
            "origin": origin, "instruction": (instruction or "")[:1000], "step": "answer", "category": category,
            "reply_lang_name": LANG_NAMES[policy["reply_lang"]], "notice": policy["notice"],
        })
        suggestion = with_notice(answer.get("reply") or "", policy["notice"])
        return {"lang": lang, "lang_name": LANG_NAMES.get(lang, lang), "translation": (ai.get("translation_pt") or "").strip() if lang != "pt" else "",
                "category": category, "confidence": float(ai.get("confidence") or 0), "summary": ai.get("summary") or "",
                "origin": origin or "", "origin_guess": ai.get("origin_guess") or "", "suggestion": suggestion,
                "reply_lang": policy["reply_lang"], "notice": policy["flag"], "todo": (ai.get("todo") or "").strip(),
                # a no on its own only to someone with no link to you, who wrote first, and not answering anything of yours
                "decline": category == "service_offer" and not mine and not origin and not ANSWERS_YOU.search(" ".join(theirs))}

    @staticmethod
    async def ingest(items: List[Dict[str, Any]]) -> dict:
        """From the inbox_scan: what is new is analyzed, decided and told to you."""
        from app.services.bot_service import BotService
        out = {"new": 0, "declined": 0, "proposed": 0, "invites": 0}
        for it in items:
            kind = it.get("kind") if it.get("kind") in ("invite", "chat") else None
            messages = [m for m in (it.get("messages") or []) if (m.get("text") or "").strip()]
            if not kind or not messages:
                continue
            key = it.get("key") or (f"invite:{_slug(it.get('profile_url')) or _name_key(it.get('name'))}" if kind == "invite"
                                    else f"chat:{it.get('thread_url')}")
            if key in ("invite:", "chat:None"):
                continue
            last = next((m for m in reversed(messages) if m.get("from") != "me"), None)
            if not last:   # the last word is yours: nothing to answer
                continue
            last_key = (last.get("key") or last.get("text") or "")[:300]
            conv = _one("SELECT * FROM public.linkedin_conversations WHERE conv_key = %s", (key,))
            if conv and conv.get("last_key") == last_key:
                continue
            res = await InboxService.analyze(kind, it.get("name"), it.get("headline"), messages, it.get("profile_url"),
                                             (conv or {}).get("es_notice_given"), (conv or {}).get("translator_notice_given"))
            conv = _one("""
                INSERT INTO public.linkedin_conversations (conv_key, kind, thread_url, profile_url, name, headline, category, confidence, lang,
                                                          last_key, last_message, translation, origin, suggestion, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'new')
                ON CONFLICT (conv_key) DO UPDATE SET thread_url = COALESCE(EXCLUDED.thread_url, linkedin_conversations.thread_url),
                    profile_url = COALESCE(EXCLUDED.profile_url, linkedin_conversations.profile_url), headline = EXCLUDED.headline,
                    category = EXCLUDED.category, confidence = EXCLUDED.confidence, lang = EXCLUDED.lang, last_key = EXCLUDED.last_key,
                    last_message = EXCLUDED.last_message, translation = EXCLUDED.translation, origin = EXCLUDED.origin,
                    suggestion = EXCLUDED.suggestion, status = 'new', updated_at = NOW()
                RETURNING *""", (key, kind, it.get("thread_url"), it.get("profile_url"), it.get("name"), it.get("headline"), res["category"],
                                 res["confidence"], res["lang"], last_key, (last.get("text") or "")[:4000], res["translation"],
                                 res["origin"] or res["origin_guess"], res["suggestion"]))
            out["new"] += 1
            InboxService._decide(conv, res, BotService, out)
        return out

    @staticmethod
    def _decide(conv: dict, res: dict, BotService, out: dict) -> None:
        name = conv.get("name") or "alguém"
        flags = {"es": res["notice"] == "es", "translator": res["notice"] == "translator"}
        head = [f"*{name}*" + (f" — {conv['headline'][:90]}" if conv.get("headline") else "")]
        if res["translation"]:
            head.append(f"🌐 {res['lang_name']} → PT: “{res['translation'][:700]}”")
        else:
            head.append(f"💬 “{(conv.get('last_message') or '')[:700]}”")
        head.append(f"📍 Origem: {conv.get('origin') or 'nada no CareerOps (não veio de uma interação da automação)'}")
        if conv["kind"] == "invite":
            text = "\n".join(["🤝 *Convite com mensagem*", *head, "", "Aceite no LinkedIn se fizer sentido. Depois de aceitar, sugestão para o chat:",
                              f"“{res['suggestion']}”"])
            BotService.notify("inbox", text, {"conversation": conv["id"]}, key=f"inbox:{conv['conv_key']}:{conv['last_key'][:80]}")
            _rows("UPDATE public.linkedin_conversations SET status = 'notified' WHERE id = %s", (conv["id"],))
            out["invites"] += 1
            return
        if not conv.get("thread_url"):
            return
        threshold = float(_cfg().get("decline_confidence", 0.8))
        if res["decline"] and res["confidence"] >= threshold and _cfg().get("auto_decline", True):
            action = AutomationService.create_action(
                "message", f"message:{conv['id']}:{conv['last_key'][:80]}", f"Recusar oferta de {name}", conv["thread_url"],
                {"conversation": conv["id"], "name": name, "text": res["suggestion"], "why": "service_offer", "notice": res["notice"]},
                status="queued", target_type="conversation", target_id=conv["id"], rank=8, auto=True)
            InboxService._notices_sent(conv["id"], flags)
            _rows("UPDATE public.linkedin_conversations SET status = 'declined' WHERE id = %s", (conv["id"],))
            BotService.notify("inbox", "\n".join(["🚫 *Oferta de serviço recusada sozinha*", *head, f"Enviando: “{res['suggestion']}”"]),
                              {"conversation": conv["id"], "action": (action or {}).get("id")}, key=f"inbox:{conv['conv_key']}:{conv['last_key'][:80]}")
            out["declined"] += 1
            return
        # anything else (a recruiter above all): the answer waits for your OK
        action = AutomationService.create_action(
            "message", f"message:{conv['id']}:{conv['last_key'][:80]}", name, conv["thread_url"],
            {"conversation": conv["id"], "name": name, "text": res["suggestion"], "why": res["category"], "notice": res["notice"],
             "translation": res["translation"], "last": (conv.get("last_message") or "")[:600]},
            target_type="conversation", target_id=conv["id"], rank=7 if res["category"] in ("recruiter", "redirect") else 13)
        _rows("UPDATE public.linkedin_conversations SET status = 'proposed' WHERE id = %s", (conv["id"],))
        title = {"recruiter": "🎯 *Recrutador respondeu*", "redirect": "↪️ *Responderam ao seu contato: o caminho é outro*"}.get(
            res["category"], "💬 *Mensagem nova no LinkedIn*")
        todo = [f"📌 Para você: {res['todo']}"] if res.get("todo") else []
        BotService.notify("inbox", "\n".join([title, *head, *todo, "", f"Sugestão: “{res['suggestion']}”", "",
                                              "Responda “ok” para enviar, ou diga o que mudar."]),
                          {"conversation": conv["id"], "ids": [action["id"]] if action else []},
                          urgent=res["category"] in ("recruiter", "redirect"), key=f"inbox:{conv['conv_key']}:{conv['last_key'][:80]}")
        out["proposed"] += 1

    @staticmethod
    def _notices_sent(conv_id: int, flags: Dict[str, bool]) -> None:
        if flags.get("es"):
            _rows("UPDATE public.linkedin_conversations SET es_notice_given = TRUE WHERE id = %s", (conv_id,))
        if flags.get("translator"):
            _rows("UPDATE public.linkedin_conversations SET translator_notice_given = TRUE WHERE id = %s", (conv_id,))

    @staticmethod
    def message_sent(action: dict) -> None:
        """A message went out: the notice it carried is never said again in this conversation."""
        p = action.get("payload") or {}
        if action.get("target_id"):
            InboxService._notices_sent(action["target_id"], {"es": p.get("notice") == "es", "translator": p.get("notice") == "translator"})
            _rows("UPDATE public.linkedin_conversations SET status = 'done', updated_at = NOW() WHERE id = %s AND status <> 'declined'",
                  (action["target_id"],))

    @staticmethod
    def reply_done(action: dict) -> None:
        if action.get("target_id"):
            _rows("UPDATE public.linkedin_comment_replies SET status = 'done', updated_at = NOW() WHERE id = %s", (action["target_id"],))

    @staticmethod
    def reply_read_failed(reply_id: int) -> None:
        _rows("UPDATE public.linkedin_comment_replies SET status = 'failed', updated_at = NOW() WHERE id = %s", (reply_id,))

    # ── The extension, in your own browser: a suggestion for the conversation on screen ──
    @staticmethod
    async def suggest(name: Optional[str], headline: Optional[str], messages: List[Dict[str, Any]], profile_url: Optional[str] = None,
                      instruction: Optional[str] = None) -> dict:
        return await InboxService.analyze("chat", name, headline, messages, profile_url, instruction=instruction)
