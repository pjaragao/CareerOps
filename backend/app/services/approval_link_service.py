"""The approval link (decided 2026-11-22): approving jobs from the phone, in any browser, without the app's token.

The link carries its own token, which only lists the jobs waiting for approval and approves or discards them: it cannot change
the mode, the account or the limits, nor approve a comment, an invitation or a message. Only its hash is kept; it lasts
link_days (7, the time a job waits for approval) and every link can be revoked at once in Configurações → Acesso.

The page is served by the backend under /aprovar, the only path published on the internet (Tailscale Funnel); every other path
answers 404 to a request that came through the Funnel (see public_guard).
"""
import hashlib
import secrets
from datetime import timedelta
from typing import List, Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.services.automation_service import AutomationService, _one, _rows, config, now

PUBLIC_PREFIX = "/aprovar"


def _hash(token: str) -> str:
    return hashlib.sha256((token or "").encode()).hexdigest()


def public_base() -> str:
    """CAREEROPS_PUBLIC_URL, or the app's address without its port (the Funnel answers on 443 of the same name)."""
    if settings.CAREEROPS_PUBLIC_URL:
        return settings.CAREEROPS_PUBLIC_URL.rstrip("/")
    p = urlparse(settings.CAREEROPS_APP_URL)
    return f"{p.scheme}://{p.hostname}" if p.hostname else settings.CAREEROPS_APP_URL.rstrip("/")


class ApprovalLinkService:
    @staticmethod
    def create_link(days: Optional[int] = None) -> str:
        days = int(days or ((config().get("jobs") or {}).get("link_days") or 7))
        token = secrets.token_urlsafe(32)
        _one("INSERT INTO public.approval_links (token_hash, expires_at) VALUES (%s, %s) RETURNING id", (_hash(token), now() + timedelta(days=days)))
        return f"{public_base()}{PUBLIC_PREFIX}?t={token}"

    @staticmethod
    def check(token: Optional[str]) -> Optional[dict]:
        """The link's row when the token is valid (and counts the use); None otherwise."""
        if not token or len(token) < 20 or len(token) > 200:
            return None
        return _one("""UPDATE public.approval_links SET uses = uses + 1, last_used_at = NOW()
                        WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > NOW() RETURNING id, expires_at""", (_hash(token),))

    @staticmethod
    def revoke_all() -> int:
        return len(_rows("UPDATE public.approval_links SET revoked_at = NOW() WHERE revoked_at IS NULL AND expires_at > NOW() RETURNING id"))

    @staticmethod
    def active() -> dict:
        row = _one("""SELECT COUNT(*) AS n, MAX(last_used_at) AS last_used_at FROM public.approval_links
                       WHERE revoked_at IS NULL AND expires_at > NOW()""")
        return {"active": row["n"], "last_used_at": row["last_used_at"], "base": public_base() + PUBLIC_PREFIX}

    @staticmethod
    def prune() -> None:
        _rows("DELETE FROM public.approval_links WHERE expires_at < NOW() - INTERVAL '30 days'")

    # ── What the page shows and does ─────────────────────────────────────
    @staticmethod
    def jobs() -> List[dict]:
        from app.services.discovery.sources import LABELS
        rows = _rows("""
            SELECT a.id, a.created_at, a.target_url, j.id AS job_id, j.job_title, j.company, j.location, j.url, j.apply_url, j.source,
                   j.triage_score, j.triage_reason, j.salary_flag, j.posted_at, j.eligibility_status, j.easy_apply,
                   left(j.description, 1500) AS excerpt
              FROM public.automation_actions a JOIN public.job_listings j ON a.target_type = 'job' AND j.id = a.target_id
             WHERE a.kind = 'apply' AND a.status = 'proposed'
             ORDER BY j.triage_score DESC NULLS LAST, j.posted_at DESC NULLS LAST, a.id DESC LIMIT 300""")
        for r in rows:
            r["source_label"] = LABELS.get(r.get("source") or "linkedin", r.get("source"))
        return rows

    @staticmethod
    def _is_job(action_id: int) -> bool:
        return bool(_one("SELECT 1 AS y FROM public.automation_actions WHERE id = %s AND kind = 'apply' AND status = 'proposed'", (action_id,)))

    @staticmethod
    def approve(action_id: int, link_id: int) -> Optional[dict]:
        if not ApprovalLinkService._is_job(action_id):
            return None
        done = AutomationService.approve(action_id)
        if done:
            AutomationService.add_event(action_id, "user", "approved_by_link", {"link": link_id})
        return done

    @staticmethod
    def reject(action_id: int, link_id: int) -> Optional[dict]:
        if not ApprovalLinkService._is_job(action_id):
            return None
        done = AutomationService.reject(action_id)
        if done:
            AutomationService.add_event(action_id, "user", "rejected_by_link", {"link": link_id})
        return done

    @staticmethod
    def approve_above(min_score: int, link_id: int) -> List[int]:
        ids = [r["id"] for r in _rows("""SELECT a.id FROM public.automation_actions a JOIN public.job_listings j ON j.id = a.target_id
                                          WHERE a.kind = 'apply' AND a.status = 'proposed' AND a.target_type = 'job' AND j.triage_score >= %s""",
                                      (min_score,))]
        return [i for i in ids if ApprovalLinkService.approve(i, link_id)]
