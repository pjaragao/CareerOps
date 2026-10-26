"""LinkedIn Copilot: post drafts, engagement queue, prospects and weekly metrics.

Human-in-the-loop by design. The only action taken on LinkedIn by the system is publishing a post the user
explicitly approved, through the official API. Comments, follows and connection requests are drafted here and
done by the user on LinkedIn — automating them breaks LinkedIn's User Agreement and gets accounts restricted.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor
from app.services.ai_service import AIService
from app.services.linkedin_api_service import LinkedInApiError, LinkedInApiService
from app.services.skill_service import SkillService

log = logging.getLogger("linkedin_copilot")

MIN_SCORE = 40           # below this the AI recommends skipping
DAILY_ENGAGEMENT = 10    # size of the daily engagement queue
WEEKLY_PROSPECTS = 20    # weekly connection-request target


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


async def _skill(path: str, context: Dict[str, Any], model_key: str = "ai_model_outreach") -> dict:
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
                             source_notes: Optional[str] = None) -> List[dict]:
        recent = _rows("SELECT topic FROM public.linkedin_posts WHERE topic IS NOT NULL ORDER BY created_at DESC LIMIT 15")
        result = await _skill("linkedin/post_drafts.md", {
            "count": max(1, min(count, 5)), "pillar": pillar, "topic": topic, "source_notes": source_notes,
            "recent_posts": [r["topic"] for r in recent],
        }, model_key="ai_model_optimizer")  # public text: use the stronger model
        created = []
        for p in result.get("posts", []):
            body = (p.get("body") or "").strip()
            if not body:
                continue
            created.append(_one("""
                INSERT INTO public.linkedin_posts (pillar, topic, source_notes, body)
                VALUES (%s, %s, %s, %s) RETURNING *
            """, (p.get("pillar") or pillar, p.get("topic") or topic, source_notes, body)))
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

    # ── Engagement queue ─────────────────────────────────────────────────
    @staticmethod
    async def add_engagement(post_text: str, post_url: Optional[str] = None, author_name: Optional[str] = None,
                             author_headline: Optional[str] = None) -> dict:
        if post_url:
            existing = _one("SELECT * FROM public.linkedin_engagement WHERE post_url = %s", (post_url,))
            if existing:
                return existing
        ai = await _skill("linkedin/engagement_comment.md", {
            "post_text": post_text[:6000], "post_url": post_url, "author_name": author_name, "author_headline": author_headline,
        })
        relevance = _score(ai.get("relevance"))
        return _one("""
            INSERT INTO public.linkedin_engagement (post_url, author_name, author_headline, post_text, relevance, reason, comment_draft, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
        """, (post_url, author_name, author_headline, post_text, relevance, ai.get("reason"),
              (ai.get("comment") or "").strip() or None, "pending" if relevance >= MIN_SCORE else "skipped"))

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
        note = (ai.get("note") or "").strip()[:300] or None
        return _one("""
            INSERT INTO public.linkedin_prospects (profile_url, name, headline, company, profile_text, segment, fit, reason, note_draft, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
        """, (profile_url, name or ai.get("name"), headline or ai.get("headline"), company or ai.get("company"), profile_text,
              ai.get("segment"), fit, ai.get("reason"), note, "to_contact" if fit >= MIN_SCORE else "skipped"))

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
