"""General CVs: not tailored to one job, uploaded when signing up on job boards (We Work Remotely, Wellfound...).

Each one has a target title. The ATS review scores the CV the way resume checkers on those sites do (parsing, keywords
for the target title, impact, structure), "improve" rewrites it from that review, and the form suggestions say what to
answer in the sign-up forms (target job title, experience level, job status, salary range...)."""
import json
import logging
from pathlib import Path

from psycopg2.extras import Json

from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor
from app.services.skill_service import SkillService

log = logging.getLogger("general_resumes")

FIELDS = ("title", "lang", "target_title", "used_on", "content_md")
LANG_NAME = {"en": "English", "pt": "Portuguese"}


def ensure_schema() -> None:
    """Applies migrations_v14.sql (idempotent). When the table is new, it starts with the generic CV from config/."""
    sql = (Path(__file__).resolve().parent.parent / "db" / "migrations" / "migrations_v14.sql").read_text(encoding="utf-8")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.general_resumes') IS NOT NULL")
            existed = cur.fetchone()[0]
            cur.execute(sql)
            seed = settings.CONFIG_DIR / "resume_en_generic.md"
            if not existed and seed.exists():
                cur.execute(
                    "INSERT INTO public.general_resumes (title, lang, target_title, used_on, content_md) VALUES (%s, %s, %s, %s, %s)",
                    ("CV geral — vagas remotas (EN)", "en", "Data, Financial Modeling & AI Engineer", "We Work Remotely",
                     seed.read_text(encoding="utf-8")),
                )
        conn.commit()
    finally:
        conn.close()


def _row(r: dict) -> dict:
    out = dict(r)
    for k in ("created_at", "updated_at", "review_at", "form_suggestions_at"):
        if out.get(k):
            out[k] = out[k].isoformat()
    return out


def _ai_result(result) -> dict:
    """The AI answer as a dict, or an error people can read."""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            raise ValueError("a IA não devolveu JSON válido")
    if not isinstance(result, dict) or result.get("error"):
        raise ValueError(f"falha na IA: {(result or {}).get('error') if isinstance(result, dict) else 'resposta vazia'}")
    return result


def _candidate() -> dict:
    from app.services.job_pipeline_service import _candidate as candidate
    return candidate()


def _recent_job_titles(limit: int = 30) -> list:
    """Titles of the jobs saved in Vagas: they show which roles the candidate actually goes after."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT ON (lower(job_title)) job_title, created_at FROM public.job_listings "
                        "WHERE COALESCE(job_title, '') <> '' ORDER BY lower(job_title), created_at DESC")
            rows = sorted(cur.fetchall(), key=lambda r: r[1], reverse=True)
            return [r[0] for r in rows[:limit]]
    except Exception:
        return []
    finally:
        conn.close()


class GeneralResumeService:
    @staticmethod
    def list() -> list:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.general_resumes ORDER BY updated_at DESC")
                return [_row(r) for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get(resume_id: int) -> dict | None:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.general_resumes WHERE id = %s", (resume_id,))
                r = cur.fetchone()
                return _row(r) if r else None
        finally:
            conn.close()

    @staticmethod
    def create(data: dict) -> dict:
        values = {k: (data.get(k) or "") for k in FIELDS}
        values["title"] = values["title"].strip() or "Novo CV geral"
        values["lang"] = values["lang"] or "en"
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute(f"INSERT INTO public.general_resumes ({', '.join(FIELDS)}) VALUES ({', '.join(['%s'] * len(FIELDS))}) RETURNING *",
                            tuple(values[k] for k in FIELDS))
                r = cur.fetchone()
            conn.commit()
            return _row(r)
        finally:
            conn.close()

    @staticmethod
    def update(resume_id: int, data: dict) -> dict | None:
        changes = {k: data[k] for k in FIELDS if k in data and data[k] is not None}
        if not changes:
            return GeneralResumeService.get(resume_id)
        sets = ", ".join(f"{k} = %s" for k in changes)
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute(f"UPDATE public.general_resumes SET {sets}, updated_at = now() WHERE id = %s RETURNING *",
                            (*changes.values(), resume_id))
                r = cur.fetchone()
            conn.commit()
            return _row(r) if r else None
        finally:
            conn.close()

    @staticmethod
    def delete(resume_id: int) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.general_resumes WHERE id = %s", (resume_id,))
                gone = cur.rowcount > 0
            conn.commit()
            return gone
        finally:
            conn.close()

    @staticmethod
    def _store(resume_id: int, column: str, value: dict) -> dict:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute(f"UPDATE public.general_resumes SET {column} = %s, {column}_at = now() WHERE id = %s RETURNING *",
                            (Json(value), resume_id))
                r = cur.fetchone()
            conn.commit()
            return _row(r)
        finally:
            conn.close()

    @staticmethod
    def _context(resume: dict) -> dict:
        lang = resume.get("lang") or "en"
        return {
            "resume": resume.get("content_md") or "",
            "target_title": resume.get("target_title") or "",
            "used_on": resume.get("used_on") or "",
            "lang_name": LANG_NAME.get(lang, "English"),
        }

    @staticmethod
    async def review(resume_id: int) -> dict:
        """ATS-style review of the CV against its target title; stored on the CV."""
        resume = GeneralResumeService.get(resume_id)
        if not resume:
            raise LookupError("CV não encontrado")
        if not (resume.get("content_md") or "").strip():
            raise ValueError("o CV está vazio")
        result = _ai_result(await SkillService.run_skill("resumes/ats_review.md", GeneralResumeService._context(resume)))
        try:
            result["score"] = max(0, min(100, int(round(float(result.get("score", 0))))))
        except (TypeError, ValueError):
            result["score"] = 0
        return GeneralResumeService._store(resume_id, "review", result)

    @staticmethod
    async def improve(resume_id: int) -> dict:
        """A rewritten CV that fixes what the last review found (not saved: the page shows it to accept or discard)."""
        resume = GeneralResumeService.get(resume_id)
        if not resume:
            raise LookupError("CV não encontrado")
        context = GeneralResumeService._context(resume)
        context["review"] = json.dumps(resume.get("review") or {}, ensure_ascii=False, indent=1)
        result = _ai_result(await SkillService.run_skill("resumes/improve.md", context))
        if not (result.get("resume_markdown") or "").strip():
            raise ValueError("a IA não devolveu o CV")
        return {"resume_markdown": result["resume_markdown"], "changes": result.get("changes") or []}

    @staticmethod
    async def form_suggestions(resume_id: int) -> dict:
        """What to answer in job-board sign-up forms; stored on the CV."""
        resume = GeneralResumeService.get(resume_id)
        if not resume:
            raise LookupError("CV não encontrado")
        context = {**GeneralResumeService._context(resume), **_candidate(), "job_titles": _recent_job_titles()}
        result = _ai_result(await SkillService.run_skill("resumes/form_suggestions.md", context))
        return GeneralResumeService._store(resume_id, "form_suggestions", result)
