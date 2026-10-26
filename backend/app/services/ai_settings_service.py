"""Writing style and model routing for everything the AI writes.

Style: one entry per kind of text (post, comment, invite, easy_apply, application, message). Each entry starts from
a preset and can override tone, formality, length, emojis, hashtags and add free instructions. `render(kind)` turns it
into the instruction block every prompt includes via the Jinja global `writing_style(kind)`.

Models: which model each task uses (posts / style adjust / writing / default). Only applied with AI_PROVIDER=agy,
whose shim exposes several models; other providers keep their own per-skill settings.
"""
import json
import re
import time
from copy import deepcopy
from typing import Any, Dict, Optional

from app.db.session import get_db_connection, get_db_cursor

KINDS = {
    "post": "Posts no LinkedIn",
    "comment": "Comentários em posts",
    "invite": "Notas de convite",
    "easy_apply": "Respostas do Easy Apply",
    "application": "CV e carta de apresentação",
    "message": "Mensagens diretas (DM/e-mail)",
}

PRESETS = {
    "direto": {"label": "Profissional direto", "tone": "professional and direct; short sentences; plain words, no marketing jargon",
               "formality": "neutral"},
    "tecnico": {"label": "Técnico especialista", "tone": "technical and specific; concrete numbers, trade-offs and real examples from projects",
                "formality": "neutral"},
    "conversacional": {"label": "Conversacional", "tone": "warm and human, like a conversation between colleagues; curious, not salesy",
                       "formality": "casual"},
    "executivo": {"label": "Executivo", "tone": "strategic and concise; business impact, decisions and outcomes first",
                  "formality": "formal"},
}

LENGTHS = {  # characters, per kind
    "post": {"short": (500, 800), "medium": (900, 1400), "long": (1500, 2200)},
    "comment": {"short": (120, 280), "medium": (280, 450), "long": (450, 650)},
    "invite": {"short": (120, 200), "medium": (200, 280), "long": (250, 300)},
    "easy_apply": {"short": (150, 350), "medium": (350, 650), "long": (650, 1000)},
    "application": {"short": (1200, 1800), "medium": (1800, 2600), "long": (2600, 3500)},
    "message": {"short": (250, 450), "medium": (450, 800), "long": (800, 1200)},
}

DEFAULT_STYLE = {
    "post": {"preset": "tecnico", "length": "medium", "emojis": "none", "hashtags": 3, "custom": ""},
    "comment": {"preset": "conversacional", "length": "short", "emojis": "none", "hashtags": 0, "custom": ""},
    "invite": {"preset": "direto", "length": "short", "emojis": "none", "hashtags": 0, "custom": ""},
    "easy_apply": {"preset": "direto", "length": "short", "emojis": "none", "hashtags": 0, "custom": ""},
    "application": {"preset": "executivo", "length": "medium", "emojis": "none", "hashtags": 0, "custom": ""},
    "message": {"preset": "direto", "length": "short", "emojis": "none", "hashtags": 0, "custom": ""},
}

TASKS = {
    "posts": "Gerar posts",
    "style": "Ajustar estilo com IA",
    "writing": "Textos (comentários, convites, CV, carta, Easy Apply)",
    "default": "Tarefas usuais (extração, pontuação, análise)",
}
DEFAULT_MODELS = {
    "posts": "gemini-4-argon-high",
    "style": "gemini-4-argon-medium",
    "writing": "gemini-3.8-flash-medium",
    "default": "gemini-3.8-flash-low",
}

# Words and moves that make text read as machine-written
AI_CLICHES = ("delve", "game-changer", "game changer", "in today's fast-paced", "unlock", "unleash", "elevate", "leverage synergies",
              "Great post", "Love this", "I couldn't agree more", "This resonates", "Thanks for sharing", "excited to share",
              "Ótimo post", "Excelente post", "Parabéns pelo post", "Concordo plenamente")

_cache: Dict[str, Any] = {}
_CACHE_TTL = 30


def _get(key: str) -> Optional[dict]:
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]
    conn = get_db_connection()
    try:
        with get_db_cursor(conn) as cur:
            cur.execute("SELECT value FROM public.app_ai_settings WHERE key = %s", (key,))
            row = cur.fetchone()
    finally:
        conn.close()
    value = row["value"] if row else None
    _cache[key] = (time.time(), value)
    return value


def _put(key: str, value: dict) -> None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.app_ai_settings (key, value, updated_at) VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """, (key, json.dumps(value)))
        conn.commit()
    finally:
        conn.close()
    _cache.pop(key, None)


def detect_language(text: str) -> str:
    """Portuguese / Spanish / English, from common function words. Defaults to English."""
    words = re.findall(r"[a-zà-ú]+", (text or "").lower())
    pt = sum(w in {"não", "você", "para", "com", "uma", "que", "são", "mais", "isso", "nos", "das", "dos", "também", "quando", "como", "está", "pelo", "pela", "muito", "ao"} for w in words)
    es = sum(w in {"usted", "para", "con", "una", "que", "más", "esto", "los", "las", "también", "cuando", "como", "está", "muy", "pero", "del", "el"} for w in words)
    en = sum(w in {"the", "and", "with", "for", "this", "that", "you", "are", "was", "is", "of", "to", "in", "it", "on", "be", "have", "not", "what", "how"} for w in words)
    if pt > en and pt >= es:
        return "Portuguese"
    if es > en and es > pt:
        return "Spanish"
    return "English"


class AISettingsService:
    # ── style ──
    @staticmethod
    def get_style() -> Dict[str, dict]:
        saved = _get("style") or {}
        style = deepcopy(DEFAULT_STYLE)
        for kind, entry in saved.items():
            if kind in style and isinstance(entry, dict):
                style[kind].update({k: v for k, v in entry.items() if k in ("preset", "tone", "formality", "length", "emojis", "hashtags", "custom")})
        return style

    @staticmethod
    def save_style(style: Dict[str, dict]) -> Dict[str, dict]:
        clean = {k: v for k, v in style.items() if k in KINDS and isinstance(v, dict)}
        _put("style", clean)
        return AISettingsService.get_style()

    @staticmethod
    def render(kind: str) -> str:
        entry = AISettingsService.get_style().get(kind) or DEFAULT_STYLE["comment"]
        preset = PRESETS.get(entry.get("preset")) or PRESETS["direto"]
        tone = entry.get("tone") or preset["tone"]
        formality = entry.get("formality") or preset["formality"]
        lo, hi = LENGTHS.get(kind, LENGTHS["comment"]).get(entry.get("length") or "medium", (300, 600))
        emojis = {"none": "no emojis", "minimal": "at most one emoji, only if natural", "some": "a few emojis where natural"}.get(entry.get("emojis"), "no emojis")
        lines = [
            "WRITING STYLE (the candidate's settings — follow them):",
            f"- Tone: {tone}. Formality: {formality}.",
            f"- Length: about {lo}–{hi} characters.",
            f"- Emojis: {emojis}.",
        ]
        if kind == "post":
            n = int(entry.get("hashtags") or 0)
            lines.append(f"- Hashtags: {n} on the last line." if n else "- Hashtags: none.")
        if entry.get("custom"):
            lines.append(f"- Extra instructions from the candidate: {entry['custom']}")
        lines += [
            "- Sound like a real, specific person: first person, one concrete detail from real experience, varied sentence length.",
            "- Never use these clichés: " + "; ".join(AI_CLICHES) + ".",
            "- Don't open with praise or a summary of what the other person said; start with your own point.",
        ]
        return "\n".join(lines)

    # ── models ──
    @staticmethod
    def get_models() -> Dict[str, str]:
        models = dict(DEFAULT_MODELS)
        models.update({k: v for k, v in (_get("models") or {}).items() if k in TASKS and v})
        return models

    @staticmethod
    def save_models(models: Dict[str, str]) -> Dict[str, str]:
        _put("models", {k: v for k, v in models.items() if k in TASKS and v})
        return AISettingsService.get_models()

    @staticmethod
    def task_for_model_key(model_key: Optional[str]) -> str:
        return {"ai_model_posts": "posts", "ai_model_style": "style", "ai_model_writing": "writing",
                "ai_model_resume": "writing", "ai_model_cover": "writing", "ai_model_outreach": "writing"}.get(model_key or "", "default")
