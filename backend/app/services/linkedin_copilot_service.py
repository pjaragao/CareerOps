"""LinkedIn Copilot: post drafts, engagement queue, prospects and weekly metrics.

Human-in-the-loop by design. The only action taken on LinkedIn by the system is publishing a post the user
explicitly approved, through the official API. Comments and follows are drafted here and done by the user on
LinkedIn; a connection request (no note) is sent by the extension only on the user's click, one at a time —
batch automation breaks LinkedIn's User Agreement and gets accounts restricted.
"""
import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
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


def _theme_market(theme: dict) -> str:
    return "br" if detect_language(theme.get("post_text") or "") == "Portuguese" else "intl"


def _local_midnight(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time(), tzinfo=ZoneInfo(settings.APP_TIMEZONE))


def _today() -> date:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _rows(sql: str, params: tuple = ()) -> List[dict]:
    conn = get_db_connection()
    try:
        with get_db_cursor(conn) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
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
        return _one("""
            UPDATE public.linkedin_posts SET status = 'published', published_at = NOW(), updated_at = NOW()
             WHERE id = %s AND status IN ('draft', 'approved', 'failed') RETURNING *
        """, (post_id,))

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
        return _one("UPDATE public.linkedin_posts SET linkedin_urn = %s, error = NULL WHERE id = %s RETURNING *", (urn, post_id))

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
    def add_inspiration(post_text: str, post_url: Optional[str] = None, author_name: Optional[str] = None,
                        author_headline: Optional[str] = None, note: Optional[str] = None) -> dict:
        if post_url:
            existing = _one("SELECT * FROM public.linkedin_inspirations WHERE post_url = %s", (post_url,))
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
        if existing:
            # with an instruction the user wants a comment regardless of the relevance score
            status = "pending" if (instruction or relevance >= MIN_SCORE) and comment else "skipped"
            return _one("""
                UPDATE public.linkedin_engagement SET relevance = %s, reason = %s, comment_draft = %s, status = %s
                 WHERE id = %s RETURNING *
            """, (relevance, ai.get("reason"), comment, status, existing["id"]))
        return _one("""
            INSERT INTO public.linkedin_engagement (post_url, author_name, author_headline, post_text, relevance, reason, comment_draft, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
        """, (post_url, author_name, author_headline, post_text, relevance, ai.get("reason"),
              comment, "pending" if (instruction or relevance >= MIN_SCORE) and comment else "skipped"))

    @staticmethod
    def engagement_queue() -> dict:
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
        return _one("""
            UPDATE public.linkedin_engagement
               SET status = COALESCE(%s, status), comment_draft = COALESCE(%s, comment_draft),
                   done_at = CASE WHEN %s = 'done' THEN NOW() ELSE done_at END
             WHERE id = %s RETURNING *
        """, (status, comment_draft, status, item_id))

    # ── Prospects ────────────────────────────────────────────────────────
    @staticmethod
    async def add_prospect(profile_text: str, profile_url: Optional[str] = None, name: Optional[str] = None,
                           headline: Optional[str] = None, company: Optional[str] = None) -> dict:
        if profile_url:
            existing = _one("SELECT * FROM public.linkedin_prospects WHERE profile_url = %s", (profile_url,))
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
            url = (person.get("profile_url") or "").split("?")[0].rstrip("/")
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
        known = {r["profile_url"]: r for r in _rows(
            "SELECT * FROM public.linkedin_prospects WHERE profile_url = ANY(%s)", ([c["profile_url"] for c in clean],))}
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
        if status:
            items = _rows("SELECT * FROM public.linkedin_prospects WHERE status = %s ORDER BY fit DESC NULLS LAST, created_at", (status,))
        else:
            items = _rows("SELECT * FROM public.linkedin_prospects WHERE status <> 'skipped' ORDER BY status, fit DESC NULLS LAST, created_at")
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
        ai = await _skill("linkedin/easy_apply.md", {
            "job_title": job.get("title"), "company": job.get("company"), "location": job.get("location"),
            "job_description": desc, "lang_name": lang, "facts": LinkedInCopilotService._facts_text(),
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
