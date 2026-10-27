"""Line of thought: what the professional already said in public, so every new text keeps one identity.

Two layers go into the prompts of comments, replies, posts and messages ({{ line_of_thought(text) }}):
- the voice profile: a short list of positions, consolidated by the AI from the records and edited by the user;
- the records closest to the new text (word overlap with topic, stance, the user's request and the text itself),
  plus the pinned ones, which always go in.

Records come from texts the user actually sent (comments, replies, messages, posts) and keep the request the user
gave when the AI drafted them — that request is the user's own opinion, the most valuable part.
"""
import hashlib
import logging
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db.session import get_db_connection
from app.services.ai_settings_service import _get, _put, detect_language
from app.services.linkedin_copilot_service import _one, _rows, _skill

log = logging.getLogger("linkedin_voice")

KINDS = ("comment", "reply", "message", "post", "position")
RELATED = 6          # closest records per prompt
PINNED = 6           # pinned records always included
_STOP = set("""
    para pelo pela pelos pelas como mais muito muita isso esse essa este esta isto aqui onde quando porque porem entao
    sobre entre ainda tambem cada todo toda todos todas outro outra outros outras mesmo mesma voce voces nosso nossa
    seus suas dele dela eles elas mas tem temos sao estao seria ser estar foram fazer feito pode podem deve devem
    that this with from have will your they their there what when which about would could should into than then them
    were been being more most some such only also just like very much many over after before because while where
    those these here other each every both does doing make made really thing things people post comment
    the and for are but not you all any can her was one our out has had how its who why yes get got may new now
    que com dos das uma nao por sem seu sua ele nos mas foi ter sim ate ano vez bem tem sao era tao ja
""".split())
_SHORT = {"ai", "ia", "bi", "ml", "pm", "ux", "hr", "rh", "ti", "it"}   # two-letter terms that carry the subject


def _plain(text: Optional[str]) -> str:
    return unicodedata.normalize("NFKD", (text or "").lower()).encode("ascii", "ignore").decode()


def _tokens(text: Optional[str]) -> set:
    # 3-letter words count: acronyms (IFC, BIM, ERP, DCF, PPP) are often the whole subject
    return {w for w in re.findall(r"[a-z0-9&]{2,}", _plain(text)) if (len(w) > 2 or w in _SHORT) and w not in _STOP}


def _score(query: set, entry: dict) -> float:
    """Weighted word overlap: the topic and the stance say more about the subject than the wording does."""
    if not query:
        return 0.0
    hits = (3 * len(query & _tokens(entry.get("topic")))
            + 2 * len(query & _tokens(f"{entry.get('stance') or ''} {entry.get('instruction') or ''}"))
            + len(query & _tokens(f"{entry.get('text') or ''} {(entry.get('context') or '')[:600]}")))
    return hits / (1 + math.log(1 + len(_tokens(entry.get("text")))))


def _ref(prefix: str, key: str) -> str:
    return f"{prefix}:{hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]}"


def ensure_schema() -> None:
    """Applies migrations_v12.sql (idempotent): migrations are run by hand and a deploy must not wait for it."""
    from pathlib import Path
    sql = (Path(__file__).resolve().parent.parent / "db" / "migrations" / "migrations_v12.sql").read_text(encoding="utf-8")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()
    VoiceService.backfill()


class VoiceService:
    @staticmethod
    def backfill() -> int:
        """Records what was sent before the line of thought existed (idempotent: same refs as the live paths)."""
        n = 0
        for e in _rows("SELECT * FROM public.linkedin_engagement WHERE status = 'done' AND comment_draft IS NOT NULL"):
            n += bool(VoiceService.record("comment", e["comment_draft"], e["post_text"], e.get("topic"), e.get("stance"),
                                          e.get("instruction"), e["post_url"], VoiceService.comment_ref(e["post_url"], e["post_text"])))
        for i in _rows("SELECT * FROM public.linkedin_inspirations WHERE note LIKE 'Você comentou: %%'"):
            n += bool(VoiceService.record("comment", i["note"][len("Você comentou: "):], i["post_text"], post_url=i["post_url"],
                                          ref=VoiceService.comment_ref(i["post_url"], i["post_text"])))
        for p in _rows("SELECT * FROM public.linkedin_posts WHERE status = 'published'"):
            n += bool(VoiceService.record("post", p["body"], topic=p.get("topic"), ref=f"post:{p['id']}"))
        return n

    # ── Records ──────────────────────────────────────────────────────────
    @staticmethod
    def record(kind: str, text: str, context: Optional[str] = None, topic: Optional[str] = None,
               stance: Optional[str] = None, instruction: Optional[str] = None, post_url: Optional[str] = None,
               ref: Optional[str] = None) -> Optional[dict]:
        """Stores a text the user sent. The same ref again (the comment seen by two paths, an edited message) updates
        the row and keeps what the earlier path knew (topic, stance, request)."""
        text = (text or "").strip()
        if kind not in KINDS or len(text) < 3:
            return None
        ref = ref or _ref(kind, text)
        try:
            return _one("""
                INSERT INTO public.linkedin_voice (kind, lang, topic, stance, text, context, instruction, post_url, ref)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ref) WHERE ref IS NOT NULL DO UPDATE SET
                    text = EXCLUDED.text, lang = EXCLUDED.lang,
                    topic = COALESCE(EXCLUDED.topic, linkedin_voice.topic), stance = COALESCE(EXCLUDED.stance, linkedin_voice.stance),
                    context = COALESCE(EXCLUDED.context, linkedin_voice.context),
                    instruction = COALESCE(EXCLUDED.instruction, linkedin_voice.instruction),
                    post_url = COALESCE(EXCLUDED.post_url, linkedin_voice.post_url), updated_at = NOW()
                RETURNING *
            """, (kind, detect_language(text), (topic or "").strip()[:200] or None, (stance or "").strip()[:500] or None,
                  text[:3000], (context or "").strip()[:2000] or None, (instruction or "").strip()[:1000] or None,
                  post_url, ref))
        except Exception as e:   # the line of thought must never break sending a comment
            log.warning("voice record failed: %s", e)
            return None

    @staticmethod
    def comment_ref(post_url: Optional[str], post_text: Optional[str]) -> str:
        """One comment per post: the queue item and the 'Você comentou' theme of the same post share this key."""
        return _ref("comment", post_url or (post_text or "")[:200])

    @staticmethod
    def add_position(text: str, topic: Optional[str] = None, pinned: bool = True) -> dict:
        row = VoiceService.record("position", text, topic=topic, stance=text, ref=_ref("position", f"{topic}|{text}"))
        if row and pinned:
            row = _one("UPDATE public.linkedin_voice SET pinned = TRUE WHERE id = %s RETURNING *", (row["id"],))
        return row

    @staticmethod
    def list(kind: Optional[str] = None, q: Optional[str] = None, limit: int = 200) -> List[dict]:
        rows = _rows("SELECT * FROM public.linkedin_voice WHERE (%s::text IS NULL OR kind = %s) ORDER BY pinned DESC, created_at DESC LIMIT %s",
                     (kind, kind, limit))
        if q:
            query = _tokens(q)
            rows = sorted((r for r in rows if _score(query, r) > 0), key=lambda r: -_score(query, r))
        return rows

    @staticmethod
    def update(item_id: int, values: Dict[str, Any]) -> Optional[dict]:
        cols = [c for c in ("topic", "stance", "text", "pinned") if values.get(c) is not None]
        if not cols:
            return _one("SELECT * FROM public.linkedin_voice WHERE id = %s", (item_id,))
        return _one(f"UPDATE public.linkedin_voice SET {', '.join(f'{c} = %s' for c in cols)}, updated_at = NOW() WHERE id = %s RETURNING *",
                    (*[values[c] for c in cols], item_id))

    @staticmethod
    def delete(item_id: int) -> Optional[dict]:
        return _one("DELETE FROM public.linkedin_voice WHERE id = %s RETURNING id", (item_id,))

    # ── Retrieval (prompts) ──────────────────────────────────────────────
    @staticmethod
    def related(text: str, limit: int = RELATED) -> List[dict]:
        rows = _rows("SELECT * FROM public.linkedin_voice ORDER BY created_at DESC LIMIT 600")
        pinned = [r for r in rows if r["pinned"]][:PINNED]
        query = _tokens(text)
        scored = sorted(((_score(query, r), r) for r in rows if not r["pinned"]), key=lambda x: -x[0])
        close = [r for s, r in scored if s >= 1.0][:limit]
        if close:
            _one("UPDATE public.linkedin_voice SET used_count = used_count + 1 WHERE id = ANY(%s)", ([r["id"] for r in close],))
        return pinned + close

    @staticmethod
    def prompt_block(text: str) -> str:
        """The LINE OF THOUGHT section of a prompt (empty when there is nothing yet)."""
        try:
            profile = (VoiceService.get_profile().get("text") or "").strip()
            entries = VoiceService.related(text or "")
        except Exception as e:   # table missing, DB down: write without it rather than fail the draft
            log.warning("line of thought unavailable: %s", e)
            return ""
        if not profile and not entries:
            return ""
        lines = ["LINE OF THOUGHT — the professional's own positions. Everything they publish must read as the same person:",
                 "- Keep the same convictions and the same way of reasoning; reuse their real examples when they fit.",
                 "- Never contradict these. If this context calls for a different view, nuance it (\"it depends on…\") instead of flipping.",
                 "- Do not copy their sentences or openings: same thinking, new words."]
        if profile:
            lines += ["", "POSITIONS (consolidated and approved by the professional):", profile]
        if entries:
            lines += ["", "WHAT THEY ALREADY SAID ON RELATED TOPICS:"]
            for e in entries:
                tag = e["kind"] + (f" · {e['topic']}" if e.get("topic") else "") + (" · fixed" if e["pinned"] else "")
                line = f"- [{tag}]"
                if e.get("instruction"):
                    line += f" Their own request: \"{e['instruction'][:200]}\"."
                if e.get("stance") and e["kind"] != "position":
                    line += f" Stance: {e['stance'][:240]}."
                line += f" Text: \"{e['text'][:320]}\""
                lines.append(line)
        return "\n".join(lines)

    # ── Voice profile (consolidated positions) ───────────────────────────
    @staticmethod
    def get_profile() -> dict:
        value = _get("voice_profile") or {}
        return {"text": value.get("text") or "", "updated_at": value.get("updated_at"), "entries": value.get("entries", 0)}

    @staticmethod
    def save_profile(text: str, entries: Optional[int] = None) -> dict:
        if entries is None:
            entries = VoiceService.get_profile().get("entries", 0)
        _put("voice_profile", {"text": (text or "").strip()[:6000], "updated_at": datetime.now(timezone.utc).isoformat(), "entries": entries})
        return VoiceService.get_profile()

    @staticmethod
    def status() -> dict:
        total = _one("SELECT COUNT(*) AS n FROM public.linkedin_voice")["n"]
        profile = VoiceService.get_profile()
        return {**profile, "total": total, "new_since_profile": max(0, total - (profile.get("entries") or 0))}

    @staticmethod
    async def consolidate() -> dict:
        """Rewrites the voice profile from the records (newest first) and the current profile."""
        rows = _rows("SELECT * FROM public.linkedin_voice ORDER BY pinned DESC, created_at DESC LIMIT 120")
        if not rows:
            raise RuntimeError("Nada registrado ainda: comente, responda ou escreva uma posição primeiro")
        total = _one("SELECT COUNT(*) AS n FROM public.linkedin_voice")["n"]
        ai = await _skill("linkedin/voice_profile.md", {"entries": rows, "current": VoiceService.get_profile()["text"]},
                          model_key="ai_model_style")
        text = (ai.get("profile") or "").strip()
        if not text:
            raise RuntimeError("A IA não devolveu o perfil")
        return {**VoiceService.save_profile(text, total), "changes": ai.get("changes") or ""}
