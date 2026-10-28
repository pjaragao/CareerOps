"""LinkedIn Copilot: post drafts, engagement queue, prospects and weekly metrics.

Human-in-the-loop by design. The only action taken on LinkedIn by the system is publishing a post the user
explicitly approved, through the official API. Comments and follows are drafted here and done by the user on
LinkedIn; a connection request (no note) is sent by the extension only on the user's click, one at a time —
batch automation breaks LinkedIn's User Agreement and gets accounts restricted.
"""
import asyncio
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor
from app.services.ai_service import AIService
from app.services.ai_settings_service import detect_language
from app.services.linkedin_api_service import LinkedInApiError, LinkedInApiService
from app.services.skill_service import SkillService

log = logging.getLogger("linkedin_copilot")

MIN_SCORE = 40           # below this the AI recommends skipping
DAILY_ENGAGEMENT = 10    # size of the daily engagement queue
WEEKLY_PROSPECTS = 20    # weekly connection-request target
AUTO_DRAFTS = 2          # drafts kept ready from saved themes (see auto_draft)
# badges LinkedIn glues to names in the page text ("Ana Lima Verified Profile 3rd+")
_BADGES = re.compile(r"(\s*(•.*|verified profile|premium profile|perfil verificado|perfil premium|author|autor|you|você|1st|2nd|3rd\+?|[123]º\+?))+\s*$", re.I)


def _name_key(name: Optional[str]) -> str:
    """'José  da Silva, PhD 🚀' → 'jose da silva phd': for matching the same person across LinkedIn pages."""
    plain = unicodedata.normalize("NFKD", _BADGES.sub("", (name or "").strip())).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z ]+", " ", plain.lower()).split())


def _profile_slug(url: Optional[str]) -> str:
    m = re.search(r"/in/([^/?#]+)", url or "")
    return unquote(m.group(1)).lower() if m else ""


# how far a prospect got: a status is only ever moved forward
_STAGE = {"skipped": 0, "to_contact": 0, "invited": 1, "accepted": 2, "replied": 3}


def _clean_profile_url(url: Optional[str]) -> Optional[str]:
    """'…/in/ana/?miniProfile=…' and '…/in/ana' are the same person: stored without query and trailing slash."""
    return (url or "").split("#")[0].split("?")[0].rstrip("/") or None


def _one_per_person(rows: List[dict]) -> List[dict]:
    """Rows saved twice for one profile (older ones differ by a trailing slash): keeps the furthest along."""
    best: Dict[str, dict] = {}
    for r in rows:
        key = _profile_slug(r["profile_url"]) or f"id:{r['id']}"
        if key not in best or _STAGE.get(r["status"], 0) > _STAGE.get(best[key]["status"], 0):
            best[key] = r
    keep = {id(r) for r in best.values()}
    return [r for r in rows if id(r) in keep]


def _text_key(text: Optional[str]) -> str:
    """The post's opening, letters and digits only: the same post read on two LinkedIn pages gives the same key
    (line breaks, "… more", emoji and spacing differ)."""
    plain = unicodedata.normalize("NFKD", (text or "").lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", plain)[:60]


def _theme_market(theme: dict) -> str:
    return "br" if detect_language(theme.get("post_text") or "") == "Portuguese" else "intl"


def _local_midnight(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time(), tzinfo=ZoneInfo(settings.APP_TIMEZONE))


def _today() -> date:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _rows(sql: str, params: tuple = (), commit: bool = False) -> List[dict]:
    conn = get_db_connection()
    try:
        with get_db_cursor(conn) as cur:
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
        if commit:   # UPDATE … RETURNING of many rows
            conn.commit()
        return rows
    finally:
        conn.close()


def _one(sql: str, params: tuple = ()) -> Optional[dict]:
    conn = get_db_connection()
    try:
        with get_db_cursor(conn) as cur:
            cur.execute(sql, params)
            row = cur.fetchone() if cur.description else None
        conn.commit()
        return dict(row) if row else None
    finally:
        conn.close()


async def _skill(path: str, context: Dict[str, Any], model_key: str = "ai_model_writing") -> dict:
    prompt = await SkillService.render_prompt(path, context)
    provider = AIService.get_provider(model_key)
    result = await asyncio.to_thread(provider.generate_json, prompt)
    if not isinstance(result, dict) or result.get("error"):
        raise RuntimeError(f"AI skill {path} failed: {result}")
    return result


def _score(value: Any) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _voice():
    from app.services.linkedin_voice_service import VoiceService   # imports this module: loaded on first use
    return VoiceService


def _record_comment(item: Optional[dict]) -> None:
    """A comment you sent goes into the line of thought, with the AI's reading of it and your request."""
    if item and item.get("status") == "done" and item.get("comment_draft"):
        _voice().record("comment", item["comment_draft"], context=item.get("post_text"), topic=item.get("topic"),
                        stance=item.get("stance"), instruction=item.get("instruction"), post_url=item.get("post_url"),
                        ref=_voice().comment_ref(item.get("post_url"), item.get("post_text")))


def _record_post(post: Optional[dict]) -> None:
    if post and post.get("status") == "published":
        _voice().record("post", post["body"], topic=post.get("topic"), ref=f"post:{post['id']}")


class LinkedInCopilotService:
    # ── Posts ────────────────────────────────────────────────────────────
    @staticmethod
    def list_posts(status: Optional[str] = None) -> List[dict]:
        if status:
            return _rows("SELECT * FROM public.linkedin_posts WHERE status = %s ORDER BY COALESCE(scheduled_for, created_at) DESC", (status,))
        return _rows("SELECT * FROM public.linkedin_posts WHERE status <> 'discarded' ORDER BY COALESCE(scheduled_for, created_at) DESC")

    @staticmethod
    async def generate_posts(count: int = 2, pillar: Optional[str] = None, topic: Optional[str] = None,
                             source_notes: Optional[str] = None, market: str = "intl",
                             inspiration_id: Optional[int] = None) -> List[dict]:
        """market: "br" = Brazil (Portuguese, engineering/sanitation first) or "intl" = abroad (English, data/finance/modeling)."""
        recent = _rows("SELECT topic FROM public.linkedin_posts WHERE topic IS NOT NULL AND market = %s ORDER BY created_at DESC LIMIT 15", (market,))
        inspiration = None
        if inspiration_id:
            inspiration = _one("UPDATE public.linkedin_inspirations SET used_count = used_count + 1 WHERE id = %s RETURNING *", (inspiration_id,))
        result = await _skill("linkedin/post_drafts.md", {
            "market": market, "count": max(1, min(count, 5)), "pillar": pillar, "topic": topic, "source_notes": source_notes,
            "inspiration": inspiration,
            "recent_posts": [r["topic"] for r in recent],
        }, model_key="ai_model_posts")  # public text: the strongest model
        created = []
        for p in result.get("posts", []):
            body = (p.get("body") or "").strip()
            if not body:
                continue
            created.append(_one("""
                INSERT INTO public.linkedin_posts (market, pillar, topic, source_notes, body)
                VALUES (%s, %s, %s, %s, %s) RETURNING *
            """, (market, p.get("pillar") or pillar, p.get("topic") or topic, source_notes, body)))
        return created

    @staticmethod
    def update_post(post_id: int, body: Optional[str] = None, scheduled_for: Optional[datetime] = None) -> Optional[dict]:
        # Editing an approved post sends it back to draft: what gets published is always what was approved.
        return _one("""
            UPDATE public.linkedin_posts
               SET body = COALESCE(%s, body),
                   scheduled_for = COALESCE(%s, scheduled_for),
                   status = CASE WHEN %s IS NOT NULL AND status = 'approved' THEN 'draft' ELSE status END,
                   approved_at = CASE WHEN %s IS NOT NULL AND status = 'approved' THEN NULL ELSE approved_at END,
                   updated_at = NOW()
             WHERE id = %s AND status IN ('draft', 'approved', 'failed')
         RETURNING *
        """, (body, scheduled_for, body, body, post_id))

    @staticmethod
    def approve_post(post_id: int, scheduled_for: Optional[datetime] = None) -> Optional[dict]:
        when = scheduled_for or datetime.now(timezone.utc)
        return _one("""
            UPDATE public.linkedin_posts
               SET status = 'approved', approved_at = NOW(), scheduled_for = %s, error = NULL, updated_at = NOW()
             WHERE id = %s AND status IN ('draft', 'failed')
         RETURNING *
        """, (when, post_id))

    @staticmethod
    def unapprove_post(post_id: int) -> Optional[dict]:
        return _one("""
            UPDATE public.linkedin_posts SET status = 'draft', approved_at = NULL, updated_at = NOW()
             WHERE id = %s AND status = 'approved' RETURNING *
        """, (post_id,))

    @staticmethod
    def discard_post(post_id: int) -> Optional[dict]:
        return _one("""
            UPDATE public.linkedin_posts SET status = 'discarded', updated_at = NOW()
             WHERE id = %s AND status IN ('draft', 'approved', 'failed') RETURNING *
        """, (post_id,))

    @staticmethod
    def mark_published_manually(post_id: int) -> Optional[dict]:
        """For users without API access: they paste the text on LinkedIn themselves and record it here."""
        post = _one("""
            UPDATE public.linkedin_posts SET status = 'published', published_at = NOW(), updated_at = NOW()
             WHERE id = %s AND status IN ('draft', 'approved', 'failed') RETURNING *
        """, (post_id,))
        _record_post(post)
        return post

    @staticmethod
    def _published_today() -> int:
        row = _one("SELECT COUNT(*) AS n FROM public.linkedin_posts WHERE status = 'published' AND published_at > NOW() - INTERVAL '24 hours'")
        return row["n"] if row else 0

    @staticmethod
    def publish_post(post_id: int) -> dict:
        """Publishes one approved post via the API. Claims the row first so a post can never go out twice."""
        if LinkedInCopilotService._published_today() >= settings.LINKEDIN_MAX_POSTS_PER_DAY:
            raise LinkedInApiError(f"Daily limit reached ({settings.LINKEDIN_MAX_POSTS_PER_DAY} posts in 24 h)")
        claimed = _one("""
            UPDATE public.linkedin_posts SET status = 'published', published_at = NOW(), updated_at = NOW()
             WHERE id = %s AND status = 'approved' RETURNING *
        """, (post_id,))
        if not claimed:
            raise LinkedInApiError("Only approved posts can be published")
        try:
            urn = LinkedInApiService.publish_text(claimed["body"])
        except Exception as e:
            _one("UPDATE public.linkedin_posts SET status = 'failed', published_at = NULL, error = %s, updated_at = NOW() WHERE id = %s",
                 (str(e)[:500], post_id))
            raise
        post = _one("UPDATE public.linkedin_posts SET linkedin_urn = %s, error = NULL WHERE id = %s RETURNING *", (urn, post_id))
        _record_post(post)
        return post

    @staticmethod
    def publish_due() -> int:
        """Scheduler tick: publishes approved posts whose time has come (oldest first, within the daily limit)."""
        if not LinkedInApiService.status()["connected"]:
            return 0
        due = _rows("""
            SELECT id FROM public.linkedin_posts
             WHERE status = 'approved' AND scheduled_for <= NOW() ORDER BY scheduled_for LIMIT 1
        """)
        done = 0
        for row in due:
            try:
                LinkedInCopilotService.publish_post(row["id"])
                done += 1
            except Exception as e:
                log.warning("scheduled publish of post %s failed: %s", row["id"], e)
        return done

    # ── Inspirations (posts saved from the feed as topics of interest) ───
    @staticmethod
    def _save_inspiration(post_text: str, post_url: Optional[str] = None, author_name: Optional[str] = None,
                          author_headline: Optional[str] = None, note: Optional[str] = None) -> dict:
        existing = _one("SELECT * FROM public.linkedin_inspirations WHERE post_url = %s", (post_url,)) if post_url else None
        if not existing:
            # the same post saved before without its link (or now without one): one row, and the link fills in
            key = _text_key(post_text)
            existing = next((r for r in _rows("SELECT * FROM public.linkedin_inspirations WHERE post_url IS NULL OR %s::text IS NULL",
                                              (post_url,)) if len(key) >= 20 and _text_key(r["post_text"]) == key), None)
            if existing and post_url:
                LinkedInCopilotService.set_post_link(existing["id"], post_url)
        if existing:
            # saved again (e.g. by hand, then commented): fill what was missing — your comment, author, headline
            return _one("""
                UPDATE public.linkedin_inspirations SET note = COALESCE(note, %s), author_name = COALESCE(author_name, %s),
                       author_headline = COALESCE(author_headline, %s) WHERE id = %s RETURNING *
            """, (note, author_name, author_headline, existing["id"]))
        return _one("""
            INSERT INTO public.linkedin_inspirations (post_url, author_name, author_headline, post_text, note)
            VALUES (%s, %s, %s, %s, %s) RETURNING *
        """, (post_url, author_name, author_headline, post_text[:6000], note))

    @staticmethod
    def missing_links() -> List[dict]:
        """Saved posts without a link, for the extension to fill in when the post shows up on LinkedIn again."""
        return [{"id": r["id"], "key": _text_key(r["post_text"]), "author_name": r["author_name"]}
                for r in _rows("SELECT id, post_text, author_name FROM public.linkedin_inspirations WHERE post_url IS NULL ORDER BY id DESC LIMIT 50")
                if len(_text_key(r["post_text"])) >= 20]

    @staticmethod
    def set_post_link(item_id: int, post_url: str) -> Optional[dict]:
        """Fills a saved post's link, and the same post's comment-queue item and line-of-thought records."""
        item = _one("UPDATE public.linkedin_inspirations SET post_url = %s WHERE id = %s AND post_url IS NULL RETURNING *", (post_url, item_id))
        if not item:
            return None
        key = _text_key(item["post_text"])
        for table, text_col in (("linkedin_engagement", "post_text"), ("linkedin_voice", "context")):
            for r in _rows(f"SELECT id, {text_col} AS t FROM public.{table} WHERE post_url IS NULL AND {text_col} IS NOT NULL"):
                if _text_key(r["t"]) == key:
                    _one(f"UPDATE public.{table} SET post_url = %s WHERE id = %s AND post_url IS NULL RETURNING id", (post_url, r["id"]))
        return item

    @staticmethod
    def add_inspiration(post_text: str, post_url: Optional[str] = None, author_name: Optional[str] = None,
                        author_headline: Optional[str] = None, note: Optional[str] = None) -> dict:
        item = LinkedInCopilotService._save_inspiration(post_text, post_url, author_name, author_headline, note)
        if note:   # a comment you just posted closes the matching queue item
            LinkedInCopilotService.reconcile_engagement()
        if note and note.startswith("Você comentou: "):
            # also comments written without a draft; with a draft, the same key keeps its topic, stance and request
            # the link stored on the theme (it may have been found earlier than now), so the record key stays the same
            url = item.get("post_url") if item else post_url
            _voice().record("comment", note[len("Você comentou: "):], context=post_text, post_url=url,
                            ref=_voice().comment_ref(url, post_text))
        return item

    @staticmethod
    def list_inspirations() -> List[dict]:
        items = _rows("SELECT * FROM public.linkedin_inspirations ORDER BY used_count, created_at DESC LIMIT 50")
        for i in items:   # the market a post of yours on this theme should target, from the language it was written in
            i["market"] = _theme_market(i)
        return items

    @staticmethod
    async def auto_draft() -> Optional[dict]:
        """Scheduler tick: keeps AUTO_DRAFTS drafts ready, writing one from the newest unused saved theme when short.

        Bounded by the themes themselves: each theme is used once, and nothing is generated while enough drafts wait.
        """
        waiting = _one("SELECT COUNT(*) AS n FROM public.linkedin_posts WHERE status = 'draft'")["n"]
        if waiting >= AUTO_DRAFTS:
            return None
        theme = _one("SELECT * FROM public.linkedin_inspirations WHERE used_count = 0 ORDER BY created_at DESC LIMIT 1")
        if not theme:
            return None
        posts = await LinkedInCopilotService.generate_posts(count=1, market=_theme_market(theme), inspiration_id=theme["id"])
        return posts[0] if posts else None

    @staticmethod
    def delete_inspiration(item_id: int) -> Optional[dict]:
        return _one("DELETE FROM public.linkedin_inspirations WHERE id = %s RETURNING id", (item_id,))

    # ── Engagement queue ─────────────────────────────────────────────────
    @staticmethod
    async def add_engagement(post_text: str, post_url: Optional[str] = None, author_name: Optional[str] = None,
                             author_headline: Optional[str] = None, other_comments: Optional[str] = None,
                             instruction: Optional[str] = None, regenerate: bool = False) -> dict:
        """Drafts a comment. A post already in the queue returns its draft, unless the user asks for a new one
        (regenerate) or gives an instruction — then the same row gets the new draft."""
        existing = _one("SELECT * FROM public.linkedin_engagement WHERE post_url = %s", (post_url,)) if post_url else None
        if existing and not (regenerate or instruction):
            return existing
        own_recent = [r["comment_draft"][:220] for r in _rows("""
            SELECT comment_draft FROM public.linkedin_engagement
             WHERE comment_draft IS NOT NULL AND status IN ('done', 'pending') ORDER BY created_at DESC LIMIT 8
        """)]
        ai = await _skill("linkedin/engagement_comment.md", {
            "post_text": post_text[:6000], "post_url": post_url, "author_name": author_name, "author_headline": author_headline,
            "lang_name": detect_language(post_text), "other_comments": (other_comments or "")[:3000], "own_recent": own_recent,
            "instruction": (instruction or "")[:1000],
            "previous_draft": existing.get("comment_draft") if existing else None,
        })
        relevance = _score(ai.get("relevance"))
        comment = (ai.get("comment") or "").strip() or None
        topic, stance = ai.get("topic") or None, ai.get("stance") or None
        instruction = (instruction or "").strip()[:1000] or None
        if existing:
            # with an instruction the user wants a comment regardless of the relevance score
            status = "pending" if (instruction or relevance >= MIN_SCORE) and comment else "skipped"
            return _one("""
                UPDATE public.linkedin_engagement SET relevance = %s, reason = %s, comment_draft = %s, status = %s,
                       topic = %s, stance = %s, instruction = COALESCE(%s, instruction)
                 WHERE id = %s RETURNING *
            """, (relevance, ai.get("reason"), comment, status, topic, stance, instruction, existing["id"]))
        return _one("""
            INSERT INTO public.linkedin_engagement (post_url, author_name, author_headline, post_text, relevance, reason, comment_draft, status,
                                                    topic, stance, instruction)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
        """, (post_url, author_name, author_headline, post_text, relevance, ai.get("reason"),
              comment, "pending" if (instruction or relevance >= MIN_SCORE) and comment else "skipped", topic, stance, instruction))

    @staticmethod
    async def draft_reply(post_text: str, target_text: str, thread: Optional[str] = None, target_author: Optional[str] = None,
                          my_comment: Optional[str] = None, my_name: Optional[str] = None, author_name: Optional[str] = None,
                          instruction: Optional[str] = None, previous_draft: Optional[str] = None) -> dict:
        """Answer to a reply in a comment thread: "continue" the discussion, or "close" it with a short thank-you."""
        ai = await _skill("linkedin/engagement_reply.md", {
            "post_text": post_text[:4000], "target_text": target_text[:2000], "thread": (thread or "")[:4000],
            "target_author": target_author, "my_comment": (my_comment or "")[:2000], "my_name": my_name, "author_name": author_name,
            "lang_name": detect_language(target_text if len(target_text) >= 40 else f"{target_text} {my_comment or post_text}"),
            "instruction": (instruction or "")[:1000], "previous_draft": previous_draft,
        })
        reply = (ai.get("reply") or "").strip()
        if not reply:
            raise RuntimeError("A IA não devolveu uma resposta")
        return {"kind": "close" if ai.get("kind") == "close" else "continue", "reason": ai.get("reason"), "reply": reply,
                "topic": ai.get("topic") or None, "stance": ai.get("stance") or None}

    @staticmethod
    def reconcile_engagement() -> int:
        """Closes queue items you already commented on LinkedIn — also when you discarded the draft and wrote another.

        The extension saves every post you comment on as a theme with "Você comentou: <your text>"; a pending item for
        the same post (by link, or by its opening text when there is no link) is done, with what you really wrote.
        """
        closed = _rows("""
            UPDATE public.linkedin_engagement e
               SET status = 'done', comment_draft = regexp_replace(i.note, '^Você comentou: ', ''),
                   done_at = COALESCE(e.done_at, i.created_at)
              FROM public.linkedin_inspirations i
             WHERE e.status = 'pending' AND i.note LIKE 'Você comentou: %%'
               AND (e.post_url = i.post_url OR (e.post_url IS NULL AND left(e.post_text, 200) = left(i.post_text, 200)))
         RETURNING e.*
        """, commit=True)
        for item in closed:
            _record_comment(item)
        return len(closed)

    @staticmethod
    def engagement_queue() -> dict:
        LinkedInCopilotService.reconcile_engagement()
        pending = _rows("""
            SELECT * FROM public.linkedin_engagement WHERE status = 'pending'
             ORDER BY relevance DESC NULLS LAST, created_at LIMIT %s
        """, (DAILY_ENGAGEMENT,))
        today = _local_midnight(_today())
        done_today = _one("SELECT COUNT(*) AS n FROM public.linkedin_engagement WHERE status = 'done' AND done_at >= %s AND done_at < %s",
                          (today, today + timedelta(days=1)))
        return {"items": pending, "done_today": done_today["n"], "daily_target": DAILY_ENGAGEMENT}

    @staticmethod
    def update_engagement(item_id: int, status: Optional[str] = None, comment_draft: Optional[str] = None) -> Optional[dict]:
        item = _one("""
            UPDATE public.linkedin_engagement
               SET status = COALESCE(%s, status), comment_draft = COALESCE(%s, comment_draft),
                   done_at = CASE WHEN %s = 'done' THEN NOW() ELSE done_at END
             WHERE id = %s RETURNING *
        """, (status, comment_draft, status, item_id))
        if status == "done":
            _record_comment(item)
        return item

    # ── Prospects ────────────────────────────────────────────────────────
    @staticmethod
    async def add_prospect(profile_text: str, profile_url: Optional[str] = None, name: Optional[str] = None,
                           headline: Optional[str] = None, company: Optional[str] = None) -> dict:
        profile_url = _clean_profile_url(profile_url)
        if profile_url:
            existing = _one("SELECT * FROM public.linkedin_prospects WHERE RTRIM(profile_url, '/') = %s ORDER BY id LIMIT 1", (profile_url,))
            if existing:
                return existing
        ai = await _skill("linkedin/prospect_note.md", {
            "profile_text": profile_text[:6000], "profile_url": profile_url, "name": name, "headline": headline, "company": company,
        })
        fit = _score(ai.get("fit"))
        market = ai.get("market") if ai.get("market") in ("br", "intl") else None
        return _one("""
            INSERT INTO public.linkedin_prospects (profile_url, name, headline, company, profile_text, market, segment, fit, reason, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
        """, (profile_url, name or ai.get("name"), headline or ai.get("headline"), company or ai.get("company"), profile_text,
              market, ai.get("segment"), fit, ai.get("reason"), "to_contact" if fit >= MIN_SCORE else "skipped"))

    @staticmethod
    async def score_people(people: List[Dict[str, Any]], topic: Optional[str] = None) -> List[dict]:
        """Scores the people visible on a LinkedIn list page in one AI call and stores them as prospects.

        people: [{"profile_url", "name", "headline"}]. topic: the saved post they were found on (author/commenters).
        Already-known profiles are returned as they are (no new AI cost).
        """
        clean, seen = [], set()
        for person in people:
            url = _clean_profile_url(person.get("profile_url"))
            if not url or url in seen:
                continue
            seen.add(url)
            name = _BADGES.sub("", (person.get("name") or "").strip())[:120]
            headline = (person.get("headline") or "").strip()[:400]
            # nothing to judge by (no headline, or the name read twice): a score would be a guess, so leave them out
            if len(headline) < 4 or (name and headline.lower().startswith(name.lower())):
                continue
            clean.append({"profile_url": url, "name": name, "headline": headline})
        clean = clean[:25]
        if len(clean) * 2 < len(people):   # the extension is not reading headlines: LinkedIn's markup probably changed
            log.warning("score_people: only %d of %d people came with a usable headline", len(clean), len(people))
        known = {r["profile_url"].rstrip("/"): r for r in _one_per_person(_rows(
            "SELECT * FROM public.linkedin_prospects WHERE RTRIM(profile_url, '/') = ANY(%s)", ([c["profile_url"] for c in clean],)))}
        todo = [c for c in clean if c["profile_url"] not in known]
        results = {url: row for url, row in known.items()}
        if todo:
            ai = await _skill("linkedin/prospect_batch.md", {"people": todo, "topic": (topic or "").strip()[:600]})
            for item in ai.get("people", []):
                try:
                    person = todo[int(item.get("i"))]
                except (TypeError, ValueError, IndexError):
                    continue
                fit = _score(item.get("fit"))
                market = item.get("market") if item.get("market") in ("br", "intl") else None
                results[person["profile_url"]] = _one("""
                    INSERT INTO public.linkedin_prospects (profile_url, name, headline, profile_text, market, segment, fit, reason, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (profile_url) WHERE profile_url IS NOT NULL DO NOTHING
                    RETURNING *
                """, (person["profile_url"], person["name"] or None, person["headline"] or None, person["headline"], market,
                      item.get("segment"), fit, item.get("reason"), "to_contact" if fit >= MIN_SCORE else "skipped")) \
                    or _one("SELECT * FROM public.linkedin_prospects WHERE profile_url = %s", (person["profile_url"],))
        return [results[c["profile_url"]] for c in clean if c["profile_url"] in results]

    @staticmethod
    def list_prospects(status: Optional[str] = None) -> dict:
        items = _one_per_person(_rows("SELECT * FROM public.linkedin_prospects ORDER BY status, fit DESC NULLS LAST, created_at"))
        items = [r for r in items if r["status"] == status] if status else [r for r in items if r["status"] != "skipped"]
        week = _one("""
            SELECT COUNT(*) FILTER (WHERE status IN ('invited', 'accepted', 'replied') AND updated_at >= %s) AS invited_this_week
              FROM public.linkedin_prospects
        """, (_local_midnight(_week_start(_today())),))
        return {"items": items, "invited_this_week": week["invited_this_week"], "weekly_target": WEEKLY_PROSPECTS}

    @staticmethod
    def update_prospect(item_id: int, status: Optional[str] = None, note_draft: Optional[str] = None,
                        notes: Optional[str] = None) -> Optional[dict]:
        return _one("""
            UPDATE public.linkedin_prospects
               SET status = COALESCE(%s, status), note_draft = COALESCE(%s, note_draft), notes = COALESCE(%s, notes), updated_at = NOW()
             WHERE id = %s RETURNING *
        """, (status, note_draft[:300] if note_draft else None, notes, item_id))

    @staticmethod
    def check_prospects(connections: List[Dict[str, Any]], conversations: List[Dict[str, Any]],
                        sent: List[Dict[str, Any]]) -> dict:
        """Moves prospects forward from what the extension read on three LinkedIn lists.

        sent: [{"profile_url", "name"}] from Invitations → Sent (pending invites) → invited, which also catches invites
        sent from LinkedIn itself (search results, My Network) that the extension never saw.
        connections: same shape, from My Network → Connections (newest first) → accepted.
        conversations: [{"name", "profile_url"?, "replied"}] from Messaging, replied = the last message is theirs → replied.
        Matched by profile slug, else by the full name when it belongs to one profile only (search results link to
        /in/ACoAA… ids, the lists to the vanity slug). Every row of the same profile moves (older duplicates).
        """
        rows = _rows("SELECT * FROM public.linkedin_prospects")
        by_slug: Dict[str, List[dict]] = {}
        by_name: Dict[str, List[dict]] = {}
        for r in rows:
            if _profile_slug(r["profile_url"]):
                by_slug.setdefault(_profile_slug(r["profile_url"]), []).append(r)
            if _name_key(r["name"]):
                by_name.setdefault(_name_key(r["name"]), []).append(r)

        def match(person: Dict[str, Any]) -> List[dict]:
            same = by_slug.get(_profile_slug(person.get("profile_url")))
            if same:
                return same
            same = by_name.get(_name_key(person.get("name")), [])
            return same if len({_profile_slug(r["profile_url"]) or r["id"] for r in same}) == 1 else []

        target: Dict[int, str] = {}
        for status, people in (("invited", sent), ("accepted", connections),
                               ("replied", [c for c in conversations if c.get("replied")])):
            for person in people:
                for r in match(person):
                    current = target.get(r["id"], r["status"])
                    if _STAGE[status] > _STAGE.get(current, 0):
                        target[r["id"]] = status
        for item_id, status in target.items():
            LinkedInCopilotService.update_prospect(item_id, status)
        changed = _one_per_person([{**r, "status": target[r["id"]]} for r in rows if r["id"] in target])
        after = _one_per_person([{**r, "status": target.get(r["id"], r["status"])} for r in rows])
        pick = lambda status: [{"id": r["id"], "name": r["name"], "status": r["status"]} for r in changed if r["status"] == status]
        return {
            "invited": pick("invited"), "accepted": pick("accepted"), "replied": pick("replied"),
            "waiting": sum(1 for r in after if r["status"] == "invited"),
            "read": {"sent": len(sent), "connections": len(connections), "conversations": len(conversations)},
        }

    # ── Easy Apply assistant (fills the form; the user reviews and submits) ──
    # Demographic questions are never sent to the AI. Gender is answered only from config/easy_apply.yml (self_identification).
    DEMOGRAPHIC = re.compile(r"race|ra[cç]a|etnia|ethnic|veteran|disab|defici[eê]ncia|pcd|orienta[cç][aã]o sexual|sexual orientation|pronoun|pronome|religi", re.I)
    GENDER = re.compile(r"\bgender\b|g[eê]nero|\bsexo\b", re.I)
    MALE = re.compile(r"^(male|man|masculino|homem|m)$|\bmale\b|mascul", re.I)
    PT_HINTS = (" requisitos", " experiência", " sobre a vaga", " benefícios", " responsabilidades", " você ", " vaga ")

    @staticmethod
    def _gender_answer(field: Dict[str, Any], gender: str, lang: str) -> Optional[str]:
        if gender.lower() not in ("male", "masculino", "homem", "man"):
            return None
        if field.get("type") in ("select", "radio"):
            return next((o for o in field.get("options") or [] if LinkedInCopilotService.MALE.search(o.strip())
                         and not re.search(r"female|feminino|mulher", o, re.I)), None)
        return "Masculino" if lang == "Portuguese" else "Male"

    @staticmethod
    def _facts_text() -> str:
        path = settings.CONFIG_DIR / "easy_apply.yml"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    @staticmethod
    def _coerce(field: Dict[str, Any], value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        kind = field.get("type")
        if kind in ("select", "radio"):
            options = field.get("options") or []
            return next((o for o in options if o.strip().lower() == text.lower()), None)
        if kind == "checkbox":
            return "true" if text.lower() in ("true", "yes", "sim", "1") else "false"
        if kind == "number":
            digits = re.findall(r"\d+(?:[.,]\d+)?", text)
            return digits[0].replace(",", ".") if digits else None
        return text

    @staticmethod
    async def easy_apply_answers(job: Dict[str, Any], fields: List[Dict[str, Any]]) -> dict:
        """Answers for the fields of one Easy Apply step. Demographic questions are never answered."""
        import yaml
        from app.services.profile_service import ProfileService
        desc = (job.get("description") or "")[:5000]
        lang = "Portuguese" if sum(h in f" {desc.lower()} " for h in LinkedInCopilotService.PT_HINTS) >= 2 else "English"
        facts = yaml.safe_load(LinkedInCopilotService._facts_text() or "{}") or {}
        gender = str((facts.get("self_identification") or {}).get("gender") or "")
        answers: Dict[str, str] = {}
        usable, skipped = [], []
        for f in fields:
            if not f.get("key"):
                continue
            label = f.get("label") or ""
            if LinkedInCopilotService.GENDER.search(label):
                g = LinkedInCopilotService._gender_answer(f, gender, lang) if gender else None
                (answers.__setitem__(f["key"], g) if g else skipped.append(f["key"]))
            elif LinkedInCopilotService.DEMOGRAPHIC.search(label):
                skipped.append(f["key"])
            else:
                usable.append(f)
        if not usable:
            return {"answers": answers, "suggestions": {}, "needs_user": skipped, "notes": "", "language": lang}
        # the CV generated for this job (the one attached to the application): the fields copy from it
        saved = None
        if str(job.get("id") or "").isdigit():
            saved = _one("SELECT resume_markdown FROM public.job_listings WHERE id = %s", (int(job["id"]),))
        elif job.get("linkedin_job_id"):
            saved = _one("SELECT resume_markdown FROM public.job_listings WHERE linkedin_job_id = %s", (str(job["linkedin_job_id"]),))
        ai = await _skill("linkedin/easy_apply.md", {
            "job_title": job.get("title"), "company": job.get("company"), "location": job.get("location"),
            "job_description": desc, "lang_name": lang, "facts": LinkedInCopilotService._facts_text(),
            "resume_sent": (saved or {}).get("resume_markdown") or "",
            "resume_base": ProfileService.get_resume_base("pt" if lang == "Portuguese" else "en"),
            "fields": usable,
        }, model_key="ai_model_writing")
        raw = ai.get("answers") or {}
        raw_sugg = ai.get("salary_suggestions") or {}
        suggestions: Dict[str, dict] = {}
        for f in usable:
            v = LinkedInCopilotService._coerce(f, raw.get(f["key"]))
            if v is not None:
                answers[f["key"]] = v
                continue
            s = raw_sugg.get(f["key"])
            sv = LinkedInCopilotService._coerce(f, s.get("value") if isinstance(s, dict) else s)
            if sv is not None:
                suggestions[f["key"]] = {"value": sv, "basis": (s.get("basis") if isinstance(s, dict) else "") or ""}
        done = set(answers) | set(suggestions)
        needs = [k for k in (ai.get("needs_user") or []) if k not in done] + skipped
        needs += [f["key"] for f in usable if f["key"] not in done and f["key"] not in needs]
        return {"answers": answers, "suggestions": suggestions, "needs_user": needs, "notes": ai.get("notes") or "", "language": lang}

    # ── Capture (browser extension) ──────────────────────────────────────
    @staticmethod
    async def capture(url: str, text: str, title: Optional[str] = None) -> dict:
        """Routes a page the user chose to send: a profile becomes a prospect, anything else an engagement item."""
        clean = url.split("?")[0].split("#")[0]
        if "linkedin.com/in/" in clean:
            return {"kind": "prospect", "item": await LinkedInCopilotService.add_prospect(text, profile_url=clean, name=title)}
        # Only a post permalink identifies a post; the feed URL is shared by every post on it.
        is_permalink = "/posts/" in clean or "/feed/update/" in clean
        return {"kind": "engagement", "item": await LinkedInCopilotService.add_engagement(text, post_url=clean if is_permalink else None)}

    # ── Weekly metrics ───────────────────────────────────────────────────
    @staticmethod
    def weekly_summary(weeks: int = 8) -> List[dict]:
        start = _week_start(_today())
        out = []
        for i in range(weeks):
            ws = start - timedelta(weeks=i)
            lo, hi = _local_midnight(ws), _local_midnight(ws + timedelta(days=7))
            auto = _one("""
                SELECT
                  (SELECT COUNT(*) FROM public.linkedin_posts WHERE status = 'published' AND published_at >= %s AND published_at < %s) AS posts,
                  (SELECT COUNT(*) FROM public.linkedin_engagement WHERE status = 'done' AND done_at >= %s AND done_at < %s) AS comments,
                  (SELECT COUNT(*) FROM public.linkedin_prospects WHERE status IN ('invited','accepted','replied') AND updated_at >= %s AND updated_at < %s) AS invites,
                  (SELECT COUNT(*) FROM public.linkedin_prospects WHERE status IN ('accepted','replied') AND updated_at >= %s AND updated_at < %s) AS accepted
            """, (lo, hi) * 4)
            manual = _one("SELECT * FROM public.linkedin_metrics_weekly WHERE week_start = %s", (ws,)) or {}
            out.append({"week_start": ws.isoformat(), **auto, **{k: manual.get(k) for k in (
                "profile_views", "search_appearances", "post_impressions", "recruiter_messages", "interviews", "notes")}})
        return out

    @staticmethod
    def save_weekly_metrics(week_start: date, values: Dict[str, Any]) -> dict:
        cols = ["profile_views", "search_appearances", "post_impressions", "recruiter_messages", "interviews", "notes"]
        vals = [values.get(c) for c in cols]
        return _one(f"""
            INSERT INTO public.linkedin_metrics_weekly (week_start, {", ".join(cols)}, updated_at)
            VALUES (%s, {", ".join(["%s"] * len(cols))}, NOW())
            ON CONFLICT (week_start) DO UPDATE SET {", ".join(f"{c} = EXCLUDED.{c}" for c in cols)}, updated_at = NOW()
            RETURNING *
        """, (week_start, *vals))
