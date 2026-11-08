"""Portfolio link per job, and who opened it.

Each job gets its own signed link to the portfolio (pjaragao-portfolio.vercel.app). The token is
pjr-<company slug>-<job id>-<sig>, sig = HMAC-SHA256(PORTFOLIO_TOKEN_SECRET, "<slug>:<job id>")[:16]; the
portfolio checks it with the same secret, so it needs no list of tokens and never calls the homelab.

The portfolio writes one small event per visit to a private Vercel Blob store. `pull` (every few minutes,
from main.py) reads them over GET /api/events, stores them in public.portfolio_events, updates the counters
on the job and acknowledges them, which deletes them on the portfolio side. Nothing on the homelab is exposed.

Settings come from the environment first, then from public.portfolio_settings:
PORTFOLIO_URL, PORTFOLIO_TOKEN_SECRET, PORTFOLIO_PULL_TOKEN.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from psycopg2.extras import Json

from app.db.session import get_db_connection, get_db_cursor

log = logging.getLogger("portfolio")

DEFAULT_URL = "https://pjaragao-portfolio.vercel.app"
LINK_RE = re.compile(r"\s*\|\s*\[(?:Portfolio|Portfólio)\]\([^)]*\)")


def ensure_schema() -> None:
    """Applies migrations_v16.sql (idempotent)."""
    sql = (Path(__file__).resolve().parent.parent / "db" / "migrations" / "migrations_v16.sql").read_text(encoding="utf-8")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def _q(sql: str, params: tuple = (), fetch: bool = True) -> List[dict]:
    conn = get_db_connection()
    try:
        with get_db_cursor(conn) as cur:
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()] if fetch and cur.description else []
        conn.commit()
        return rows
    finally:
        conn.close()


def _setting(key: str, default: str = "") -> str:
    value = os.getenv(key)
    if value:
        return value
    try:
        rows = _q("SELECT value FROM public.portfolio_settings WHERE key = %s", (key,))
        return rows[0]["value"] if rows else default
    except Exception:
        return default


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:40] or "empresa"


class PortfolioService:
    @staticmethod
    def configured() -> bool:
        return bool(_setting("PORTFOLIO_TOKEN_SECRET"))

    @staticmethod
    def base_url() -> str:
        return _setting("PORTFOLIO_URL", DEFAULT_URL).rstrip("/")

    @staticmethod
    def make_token(company: str, job_id: int) -> str:
        secret = _setting("PORTFOLIO_TOKEN_SECRET")
        if not secret:
            raise RuntimeError("PORTFOLIO_TOKEN_SECRET não configurado")
        slug = slugify(company)
        sig = hmac.new(secret.encode(), f"{slug}:{int(job_id)}".encode(), hashlib.sha256).hexdigest()[:16]
        return f"pjr-{slug}-{int(job_id)}-{sig}"

    @staticmethod
    def link_for(job: dict) -> Optional[str]:
        """The job's link (creates and saves its token the first time). None when the portfolio is not configured."""
        if not PortfolioService.configured() or not job or not job.get("id"):
            return None
        token = job.get("portfolio_token")
        if not token:
            token = PortfolioService.make_token(job.get("company") or "", job["id"])
            _q("UPDATE public.job_listings SET portfolio_token = %s WHERE id = %s AND portfolio_token IS NULL",
               (token, job["id"]), fetch=False)
            rows = _q("SELECT portfolio_token FROM public.job_listings WHERE id = %s", (job["id"],))
            token = rows[0]["portfolio_token"] if rows else token
        return f"{PortfolioService.base_url()}/?token={token}"

    @staticmethod
    def with_link(markdown: str, link: Optional[str], portuguese: bool = False) -> str:
        """Adds the portfolio link to the contact line of the CV (the line with the e-mail). Nothing else changes.
        Idempotent: an old portfolio link on that line is replaced, never duplicated."""
        if not markdown or not link:
            return markdown
        label = "Portfólio" if portuguese else "Portfolio"
        lines = markdown.split("\n")
        for i, line in enumerate(lines[:15]):
            if "@" in line and not line.lstrip().startswith("#"):
                clean = LINK_RE.sub("", line.rstrip())
                lines[i] = f"{clean} | [{label}]({link})"
                return "\n".join(lines)
        return markdown   # no contact line found: leave the CV as it is

    @staticmethod
    def attach(job_id: int, markdown: Optional[str] = None) -> Optional[str]:
        """The CV of the job with its portfolio link. Called whenever a CV is saved."""
        rows = _q("SELECT id, company, language, portfolio_token, resume_markdown FROM public.job_listings WHERE id = %s", (job_id,))
        if not rows:
            return markdown
        job = rows[0]
        content = markdown if markdown is not None else job.get("resume_markdown")
        try:
            link = PortfolioService.link_for(job)
        except Exception as e:
            log.warning("portfolio link for job %s failed: %s", job_id, e)
            return content
        return PortfolioService.with_link(content or "", link, (job.get("language") or "").lower().startswith("p"))

    @staticmethod
    def backfill(statuses: List[str]) -> List[dict]:
        """Adds the link to the CVs already generated for jobs in these statuses. Only the contact line changes."""
        done = []
        for job in _q("""SELECT id, company, language, status, portfolio_token, resume_markdown FROM public.job_listings
                         WHERE status = ANY(%s) AND resume_markdown IS NOT NULL AND resume_markdown <> '' ORDER BY id""", (statuses,)):
            new = PortfolioService.with_link(job["resume_markdown"], PortfolioService.link_for(job),
                                             (job.get("language") or "").lower().startswith("p"))
            if new != job["resume_markdown"]:
                _q("UPDATE public.job_listings SET resume_markdown = %s, updated_at = NOW() WHERE id = %s", (new, job["id"]), fetch=False)
                done.append({"id": job["id"], "status": job["status"], "company": job["company"]})
        return done

    # ── Job CV on the portfolio ────────────────────────────────────────────
    @staticmethod
    def _put_pdf(job_id: int, name: str, pdf: bytes) -> dict:
        from urllib.parse import quote
        req = urllib.request.Request(
            f"{PortfolioService.base_url()}/api/cv?jobId={int(job_id)}&name={quote(name)}", data=pdf, method="PUT",
            headers={"Authorization": f"Bearer {_setting('PORTFOLIO_PULL_TOKEN')}", "Content-Type": "application/pdf", "User-Agent": "careerops"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    @staticmethod
    def sync_cvs(limit: int = 20) -> int:
        """Uploads the PDF of each job CV that carries a portfolio link and changed since the last upload.
        Whoever opens that job's link can download exactly that CV; other links never see it."""
        if not _setting("PORTFOLIO_PULL_TOKEN"):
            return 0
        from app.api.actions import _pdf_name
        from app.services import content_guard
        from app.services.pdf_service import PDFService
        sent = 0
        rows = _q("""SELECT id, company, language, job_title, resume_markdown, portfolio_cv_hash FROM public.job_listings
                      WHERE portfolio_token IS NOT NULL AND resume_markdown LIKE '%%[Portf%%' ORDER BY updated_at DESC NULLS LAST""")
        for job in rows:
            digest = hashlib.sha256(job["resume_markdown"].encode()).hexdigest()
            if digest == job.get("portfolio_cv_hash"):
                continue
            try:
                content_guard.ensure_clean(job["resume_markdown"], "O CV")
                name = _pdf_name(job, "resume")
                pdf = PDFService.generate_pdf(job["resume_markdown"], name)
                if PortfolioService._put_pdf(job["id"], name, pdf).get("ok"):
                    _q("UPDATE public.job_listings SET portfolio_cv_hash = %s WHERE id = %s", (digest, job["id"]), fetch=False)
                    sent += 1
            except Exception as e:
                log.warning("portfolio CV upload for job %s failed: %s", job["id"], e)
            if sent >= limit:
                break
        return sent

    # ── Views ──────────────────────────────────────────────────────────────
    @staticmethod
    def _call(path: str, body: Optional[dict] = None) -> dict:
        token = _setting("PORTFOLIO_PULL_TOKEN")
        req = urllib.request.Request(
            PortfolioService.base_url() + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "careerops"},
            method="POST" if body is not None else "GET")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    @staticmethod
    def pull(max_pages: int = 10) -> int:
        """Brings the new portfolio events home. Returns how many were stored."""
        if not _setting("PORTFOLIO_PULL_TOKEN"):
            return 0
        stored = 0
        for _ in range(max_pages):
            page = PortfolioService._call("/api/events")
            events = page.get("events") or []
            if not events:
                break
            for e in events:
                stored += PortfolioService._store(e)
            PortfolioService._call("/api/events/ack", {"pathnames": [e["pathname"] for e in events if e.get("pathname")]})
            if len(events) < 200:
                break
        return stored

    @staticmethod
    def _store(e: dict) -> int:
        job_id = e.get("jobId") or None
        if job_id and not _q("SELECT 1 AS y FROM public.job_listings WHERE id = %s", (job_id,)):
            job_id = None
        rows = _q("""INSERT INTO public.portfolio_events (event_id, token, job_id, company, event, details, location, device, occurred_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (event_id) DO NOTHING RETURNING id""",
                  (e.get("id") or e.get("pathname"), e.get("token") or "", job_id, e.get("company"), e.get("event") or "?",
                   Json(e.get("data") or {}), e.get("location"), e.get("device"), e.get("at") or datetime.now(timezone.utc).isoformat()))
        if not rows:
            return 0
        if job_id:
            if e.get("event") == "pageview":
                _q("""UPDATE public.job_listings SET portfolio_views = portfolio_views + 1,
                          portfolio_last_view_at = GREATEST(COALESCE(portfolio_last_view_at, %s), %s) WHERE id = %s""",
                   (e.get("at"), e.get("at"), job_id), fetch=False)
            elif e.get("event") == "duration":
                sec = int((e.get("data") or {}).get("seconds") or 0)
                if 0 < sec < 6 * 3600:
                    _q("UPDATE public.job_listings SET portfolio_seconds = portfolio_seconds + %s WHERE id = %s", (sec, job_id), fetch=False)
        return 1

    @staticmethod
    def news() -> List[dict]:
        """Views not told to you yet, grouped by job (for the Lolo summary)."""
        return _q("""SELECT e.job_id, COALESCE(j.company, e.company) AS company, j.job_title, COUNT(*) AS views,
                            MAX(e.occurred_at) AS last_at, (ARRAY_AGG(e.location ORDER BY e.occurred_at DESC))[1] AS location
                       FROM public.portfolio_events e LEFT JOIN public.job_listings j ON j.id = e.job_id
                      WHERE e.notified_at IS NULL AND e.event = 'pageview'
                      GROUP BY e.job_id, COALESCE(j.company, e.company), j.job_title ORDER BY MAX(e.occurred_at) DESC""")

    @staticmethod
    def mark_told() -> None:
        _q("UPDATE public.portfolio_events SET notified_at = NOW() WHERE notified_at IS NULL", fetch=False)

    @staticmethod
    def news_text(items: Optional[List[dict]] = None) -> str:
        items = PortfolioService.news() if items is None else items
        if not items:
            return ""
        total = sum(int(i["views"]) for i in items)
        parts = []
        for i in items[:5]:
            who = i.get("company") or "?"
            what = f" — {i['job_title']}" if i.get("job_title") else ""
            where = f" ({i['location']})" if i.get("location") and i["location"] != "desconhecido" else ""
            parts.append(f"• {who}{what}: {i['views']}x{where}")
        more = f"\n• +{len(items) - 5} outra(s)" if len(items) > 5 else ""
        return f"👀 *Portfólio*: {total} visualização(ões) nova(s)\n" + "\n".join(parts) + more
