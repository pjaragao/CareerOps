"""What happens to a job right after it is added: the eligibility check (does the ad require living in a region or a
work visa the candidate does not have?) and, when it passes, the tailored CV and cover letter, so applying is quick.

Runs in a worker thread (AI calls are blocking) for every job waiting in 'scraped' / 'new': the ones just imported
(kick() from the import endpoints) and the ones already in the database (startup and every 10 minutes)."""
import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor
from app.services.job_service import JobService
from app.services.skill_service import SkillService

log = logging.getLogger("job_pipeline")

STATUSES = ("ok", "warning", "blocked")


def ensure_schema() -> None:
    """Applies migrations_v13.sql (idempotent)."""
    sql = (Path(__file__).resolve().parent.parent / "db" / "migrations" / "migrations_v13.sql").read_text(encoding="utf-8")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def _candidate() -> dict:
    """Where the candidate lives and may work (config/easy_apply.yml, the same answers Easy Apply gives)."""
    try:
        data = yaml.safe_load((settings.CONFIG_DIR / "easy_apply.yml").read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    auth = data.get("work_authorization") or {}
    return {
        "citizenship": auth.get("citizenship") or "Brazilian",
        "city": (data.get("contact") or {}).get("city") or "Brazil",
        "authorized": ", ".join(auth.get("authorized_to_work") or ["Brazil"]),
        "relocate": ", ".join(auth.get("willing_to_relocate") or []) or "nowhere",
    }


class JobPipelineService:
    _lock = threading.Lock()
    _again = False   # a job arrived while a run was going: run once more at the end

    @staticmethod
    def pending_ids() -> list:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("""
                    SELECT id FROM public.job_listings
                     WHERE status IN ('scraped', 'new') AND COALESCE(description, '') <> ''
                       AND (eligibility_checked_at IS NULL OR (eligibility_status <> 'blocked' AND auto_docs_at IS NULL))
                     ORDER BY created_at DESC
                """)
                return [r["id"] for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    async def check_eligibility(job_id: int) -> dict:
        """AI reading of the ad; stored on the job. Raises when the AI gives no usable answer (checked again later)."""
        job = JobService.get_job_by_id(job_id)
        if not job:
            raise ValueError("job not found")
        result = await SkillService.run_skill("jobs/eligibility.md", {
            **_candidate(),
            "job_title": job.get("job_title") or "",
            "company": job.get("company") or "",
            "location": job.get("location") or "",
            "job_description": (job.get("description") or "")[:12000],
        })
        status = (result or {}).get("status")
        if status not in STATUSES:
            raise ValueError(f"no eligibility answer: {result}")
        issues = [i for i in (result.get("issues") or []) if isinstance(i, dict) and i.get("quote")]
        if status != "ok" and not issues:
            status = "ok"   # a flag without a sentence from the ad behind it is not shown
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""UPDATE public.job_listings SET eligibility_status = %s, eligibility_issues = %s,
                                      eligibility_checked_at = %s WHERE id = %s""",
                            (status, json.dumps(issues, ensure_ascii=False), datetime.now(timezone.utc), job_id))
            conn.commit()
        finally:
            conn.close()
        return {"status": status, "issues": issues}

    @staticmethod
    async def generate_docs(job_id: int) -> list:
        """CV and cover letter for the job, only the ones still missing. Attempted once (auto_docs_at)."""
        from app.api.actions import ActionOptions, generate_resume, generate_cover_letter
        job = JobService.get_job_by_id(job_id)
        made = []
        try:
            if not job.get("resume_markdown"):
                if (await generate_resume(job_id, ActionOptions())).get("content"):
                    made.append("resume")
            if not job.get("cover_letter"):
                if (await generate_cover_letter(job_id, ActionOptions())).get("content"):
                    made.append("cover")
        finally:
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE public.job_listings SET auto_docs_at = %s WHERE id = %s", (datetime.now(timezone.utc), job_id))
                conn.commit()
            finally:
                conn.close()
        return made

    @staticmethod
    async def process(job_id: int) -> dict:
        job = JobService.get_job_by_id(job_id)
        if not job:
            return {}
        if job.get("eligibility_checked_at"):
            check = {"status": job.get("eligibility_status"), "issues": job.get("eligibility_issues") or []}
        else:
            check = await JobPipelineService.check_eligibility(job_id)
        made = []
        if check["status"] != "blocked" and not job.get("auto_docs_at"):
            made = await JobPipelineService.generate_docs(job_id)
        log.info("job %s: eligibility %s, generated %s", job_id, check["status"], made or "nothing")
        return {**check, "generated": made}

    @classmethod
    def run_pending(cls) -> int:
        """Every waiting job, one at a time (blocking: call it from a thread). One run at a time."""
        if not cls._lock.acquire(blocking=False):
            cls._again = True
            return 0
        done = 0
        try:
            while True:
                cls._again = False
                for job_id in cls.pending_ids():
                    try:
                        asyncio.run(cls.process(job_id))
                        done += 1
                    except Exception as e:
                        log.warning("job %s not processed: %s", job_id, e)
                if not cls._again:
                    break
        finally:
            cls._lock.release()
        return done

    @classmethod
    def kick(cls) -> None:
        """Process new jobs now, without holding up the request that added them."""
        threading.Thread(target=cls.run_pending, daemon=True, name="job-pipeline").start()
