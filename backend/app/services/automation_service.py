"""Autopilot queue: what you approved, who executes it, and what stops it. The rules live here and nowhere else: the worker
(the browser on the server) and the Claude runner only ask for the next action and report what happened.

proposed → (you approve) approved → (documents) queued → (claimed) running_ext → verifying → done
A write is never repeated without looking first: when the outcome is unknown (crash, reply lost) the action goes to
unknown_outcome and the next claim only checks the page."""
import hashlib
import json
import logging
import random
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import yaml
from psycopg2.extras import Json

from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor
from app.services import content_guard

log = logging.getLogger("automation")

WRITE_KINDS = ("apply", "comment", "follow", "connect")
READ_KINDS = ("search", "check", "feed_scan", "follow_scan")
RUNNING = ("running_ext", "verifying", "awaiting_confirm", "running_claude")
OPEN = ("proposed", "approved", "review_docs", "queued", "unknown_outcome", "escalated", "needs_user") + RUNNING

# What happens to an action that could not finish, by the reason the executor gives
CLAUDE_CODES = {"selector_not_found", "step_stuck", "unexpected_layout", "external_form_unfinished"}
HALT_CODES = {"checkpoint", "restriction_notice", "session_expired", "rate_limited"}
DISCARD_CODES = {"job_closed", "already_applied", "post_deleted", "already_following", "already_connected", "already_pending"}
# Everything else (unknown question, captcha, login, an account to create…) is yours: Precisa de você

LINKEDIN_LANES = ["linkedin_read", "linkedin_write"]


def now() -> datetime:
    return datetime.now(timezone.utc)


def _local() -> datetime:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE))


@lru_cache(maxsize=1)
def config() -> dict:
    path = settings.CONFIG_DIR / "automation.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def question_key(text: str) -> str:
    """'Do you have 5+ years of SQL? *' and 'do you have 5 years of sql' are the same question."""
    plain = unicodedata.normalize("NFKD", (text or "").lower()).encode("ascii", "ignore").decode()
    plain = plain.split(" › ")[-1]
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", plain).split())[:300]


def ensure_schema() -> None:
    """Applies migrations_v15.sql (idempotent)."""
    sql = (Path(__file__).resolve().parent.parent / "db" / "migrations" / "migrations_v15.sql").read_text(encoding="utf-8")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def _rows(sql: str, params: tuple = ()) -> List[dict]:
    conn = get_db_connection()
    try:
        with get_db_cursor(conn) as cur:
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()] if cur.description else []
        conn.commit()
        return rows
    finally:
        conn.close()


def _one(sql: str, params: tuple = ()) -> Optional[dict]:
    rows = _rows(sql, params)
    return rows[0] if rows else None


def _event(cur, action_id: Optional[int], source: str, event: str, data: Optional[dict] = None, level: str = "info",
           screenshot: Optional[str] = None) -> None:
    cur.execute("INSERT INTO public.automation_events (action_id, source, level, event, data, screenshot_path) VALUES (%s, %s, %s, %s, %s, %s)",
                (action_id, source, level, event, Json(data or {}), screenshot))


def _period_start(period: str) -> datetime:
    today = _local().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=today.weekday()) if period == "week" else today


class AutomationService:
    # ── State ────────────────────────────────────────────────────────────
    @staticmethod
    def state() -> dict:
        return _one("SELECT * FROM public.automation_state WHERE id = 1") or {}

    @staticmethod
    def update_state(mode: Optional[str] = None, account_kind: Optional[str] = None, allow_final_submit: Optional[bool] = None,
                     ramp_step: Optional[int] = None, ramp_auto: Optional[bool] = None) -> dict:
        """A step you pick counts from now: the automatic climb (when on) waits a full ramp_days from it."""
        return _one("""
            UPDATE public.automation_state
               SET mode = COALESCE(%s, mode), account_kind = COALESCE(%s, account_kind),
                   allow_final_submit = COALESCE(%s, allow_final_submit),
                   ramp_step = COALESCE(%s, ramp_step), ramp_step_at = CASE WHEN %s IS NULL THEN ramp_step_at ELSE NOW() END,
                   ramp_auto = COALESCE(%s, ramp_auto), updated_at = NOW()
             WHERE id = 1 RETURNING *""", (mode, account_kind, allow_final_submit, ramp_step, ramp_step, ramp_auto))

    @staticmethod
    def _allow_final(state: dict, kind: str, target_url: Optional[str]) -> bool:
        """Whether this run may do the final click. Otherwise it goes up to that click and reports a dry run."""
        if state["mode"] != "live":
            return False
        if kind == "apply":
            return state["account_kind"] == "main" and state["allow_final_submit"] and settings.AUTOMATION_ALLOW_FINAL_SUBMIT
        if state["account_kind"] == "test" and kind in ("comment", "connect"):
            return target_url in ((config().get("test_account") or {}).get("allowed_targets") or [])
        return True

    @staticmethod
    def halt(reason: str, lanes: Optional[List[str]] = None, source: str = "user", ramp_down: bool = False) -> dict:
        """Stops the lanes (all of them by default) until you turn them on again. A LinkedIn warning also lowers the ramp."""
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("""
                    UPDATE public.automation_state
                       SET halted_at = COALESCE(halted_at, NOW()), halted_reason = %s,
                           halted_lanes = (SELECT ARRAY(SELECT DISTINCT unnest(halted_lanes || %s::text[]))),
                           ramp_step = CASE WHEN %s THEN GREATEST(ramp_step - 1, 0) ELSE ramp_step END,
                           ramp_step_at = CASE WHEN %s THEN NOW() ELSE ramp_step_at END, updated_at = NOW()
                     WHERE id = 1 RETURNING *""", (reason, lanes or ["all"], ramp_down, ramp_down))
                state = dict(cur.fetchone())
                _event(cur, None, source, "halted", {"reason": reason, "lanes": lanes or ["all"]}, level="error")
            conn.commit()
        finally:
            conn.close()
        log.warning("automation halted: %s", reason)
        return state

    @staticmethod
    def resume() -> dict:
        """Only you turn it on again. Whatever stopped mid-way is looked at before anything is repeated."""
        return _one("""UPDATE public.automation_state
                          SET halted_at = NULL, halted_reason = NULL, halted_lanes = '{}', updated_at = NOW()
                        WHERE id = 1 RETURNING *""")

    # ── A new browser of yours (the phone) ───────────────────────────────
    @staticmethod
    def login_link(minutes: int = 15) -> str:
        """A one-time code that gives this browser the approver token: only its hash is kept, it works once and expires."""
        code = secrets.token_urlsafe(24)
        _one("INSERT INTO public.automation_login_links (code_hash, expires_at) VALUES (%s, NOW() + make_interval(mins => %s)) RETURNING id",
             (hashlib.sha256(code.encode()).hexdigest(), minutes))
        return f"{settings.CAREEROPS_APP_URL.rstrip('/')}/entrar?codigo={code}"

    @staticmethod
    def redeem_login(code: str) -> Optional[str]:
        used = _one("""UPDATE public.automation_login_links SET used_at = NOW()
                        WHERE code_hash = %s AND used_at IS NULL AND expires_at > NOW() RETURNING id""",
                    (hashlib.sha256((code or "").encode()).hexdigest(),))
        return settings.CAREEROPS_APPROVER_TOKEN if used and settings.CAREEROPS_APPROVER_TOKEN else None

    # ── Limits ───────────────────────────────────────────────────────────
    @staticmethod
    def limits(state: Optional[dict] = None) -> List[dict]:
        """Each kind: the limit at the current step of the ramp and how much of it is used."""
        state = state or AutomationService.state()
        step = min(max(state.get("ramp_step", 0), 0), 2)
        out = []
        for row in _rows("SELECT * FROM public.automation_limits ORDER BY kind"):
            start = _period_start(row["period"])
            if row["kind"] == "job_read":
                used = _one("SELECT COUNT(*) AS n FROM public.job_listings WHERE search_slug IS NOT NULL AND created_at >= %s", (start,))["n"]
            else:
                used = _one("""SELECT COUNT(*) AS n FROM public.automation_actions
                                WHERE kind = %s AND started_at >= %s AND status NOT IN ('discarded', 'cancelled')""", (row["kind"], start))["n"]
            out.append({**row, "limit": row[f"step{step}"], "used": used, "left": max(row[f"step{step}"] - used, 0)})
        return out

    @staticmethod
    def set_limit(kind: str, step0: int, step1: int, step2: int) -> Optional[dict]:
        return _one("UPDATE public.automation_limits SET step0 = %s, step1 = %s, step2 = %s WHERE kind = %s RETURNING *", (step0, step1, step2, kind))

    @staticmethod
    def job_read_budget() -> int:
        return next((l["left"] for l in AutomationService.limits() if l["kind"] == "job_read"), 0)

    # ── Creating and approving ───────────────────────────────────────────
    @staticmethod
    def create_action(kind: str, key: str, title: str, target_url: Optional[str], payload: Dict[str, Any], status: str = "proposed",
                      target_type: Optional[str] = None, target_id: Optional[int] = None, rank: int = 50,
                      sort_at: Optional[datetime] = None, lane: Optional[str] = None) -> Optional[dict]:
        """One action per idempotency key: proposing the same thing twice does nothing."""
        lane = lane or ("linkedin_read" if kind in READ_KINDS else "linkedin_write")
        return _one("""
            INSERT INTO public.automation_actions (kind, lane, status, target_type, target_id, target_url, title, rank, sort_at,
                                                   payload, payload_hash, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), %s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING RETURNING *""",
                    (kind, lane, status, target_type, target_id, target_url, title, rank, sort_at, Json(payload), payload_hash(payload), key))

    @staticmethod
    def fit_of(action: dict) -> Optional[int]:
        """How well it fits your profile, 0-100, whatever the kind: the job triage, the person's fit, the post's relevance."""
        p = action.get("payload") or {}
        value = action.get("triage_score") if action["kind"] == "apply" else p.get("fit") if p.get("fit") is not None else p.get("relevance")
        try:
            return None if value is None else int(round(float(value)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def inbox() -> dict:
        items = _rows("""
            SELECT a.*, j.triage_score, j.triage_reason, j.posted_at, j.employer_market, j.salary_flag, j.easy_apply,
                   j.eligibility_status, j.eligibility_issues, j.company, j.job_title, j.location
              FROM public.automation_actions a LEFT JOIN public.job_listings j ON a.target_type = 'job' AND j.id = a.target_id
             WHERE a.status = 'proposed' ORDER BY a.rank, a.sort_at DESC LIMIT 200""")
        grouped: Dict[str, list] = {k: [] for k in WRITE_KINDS}
        for item in items:
            item["fit"] = AutomationService.fit_of(item)
            grouped[item["kind"]].append(item)
        grouped["items"] = items   # one list, in the same order: the app shows it this way, with a filter by kind
        grouped["external_manual"] = _rows("""
            SELECT id, job_title, company, location, url, triage_score, triage_reason, posted_at, salary_flag FROM public.job_listings
             WHERE status = 'discovered' AND triage_outcome = 'external_manual' ORDER BY posted_at DESC NULLS LAST LIMIT 100""")
        grouped["discarded"] = _rows("""
            SELECT id, job_title, company, location, url, triage_score, triage_reason, posted_at, employer_market FROM public.job_listings
             WHERE status = 'discovered' AND triage_outcome = 'discarded' ORDER BY created_at DESC LIMIT 100""")
        return grouped

    @staticmethod
    def _approved_payload(cur, action: dict, text: Optional[str]) -> dict:
        """What will be executed, frozen now. Editing means approving a new text."""
        payload = dict(action["payload"] or {})
        if action["kind"] == "comment":
            if text is not None:
                payload["text"] = text.strip()
                cur.execute("UPDATE public.linkedin_engagement SET comment_draft = %s WHERE id = %s", (payload["text"], action["target_id"]))
            if not (payload.get("text") or "").strip():
                raise ValueError("Comentário vazio")
        content_guard.ensure_clean(payload, "O texto aprovado")
        return payload

    @staticmethod
    def approve(action_id: int, text: Optional[str] = None, run_now: bool = False) -> Optional[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.automation_actions WHERE id = %s AND status = 'proposed' FOR UPDATE", (action_id,))
                row = cur.fetchone()
                if not row:
                    return None
                action = dict(row)
                payload = AutomationService._approved_payload(cur, action, text)
                hours = ((config().get("automation") or {}).get("approval_hours") or {}).get(action["kind"], 168)
                # a job still needs its documents (tick); everything else can go
                status = "approved" if action["kind"] == "apply" else "queued"
                cur.execute("""
                    UPDATE public.automation_actions
                       SET status = %s, payload = %s, payload_hash = %s, approved_at = NOW(), expires_at = %s, run_now = %s, updated_at = NOW()
                     WHERE id = %s RETURNING *""", (status, Json(payload), payload_hash(payload), now() + timedelta(hours=hours), run_now, action_id))
                updated = dict(cur.fetchone())
                if action["kind"] == "apply":
                    cur.execute("UPDATE public.job_listings SET status = 'new', updated_at = NOW() WHERE id = %s AND status = 'discovered'", (action["target_id"],))
                _event(cur, action_id, "user", "approved", {"hash": updated["payload_hash"], "run_now": run_now})
            conn.commit()
            return updated
        finally:
            conn.close()

    @staticmethod
    async def revise(action_id: int, instruction: str, text: Optional[str] = None) -> Optional[dict]:
        """Your request for a comment still to approve: the AI rewrites it (from your edit, if any) and it waits for you again."""
        from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s AND status = 'proposed' AND kind = 'comment'", (action_id,))
        if not action:
            return None
        if text is not None and text.strip():
            _rows("UPDATE public.linkedin_engagement SET comment_draft = %s WHERE id = %s RETURNING id", (text.strip(), action["target_id"]))
        post = _one("SELECT * FROM public.linkedin_engagement WHERE id = %s", (action["target_id"],))
        if not post or not post.get("post_url"):
            raise ValueError("Post do comentário não encontrado")
        item = await Copilot.add_engagement(post.get("post_text") or "", post["post_url"], post.get("author_name"), post.get("author_headline"),
                                            instruction=instruction, regenerate=True)
        if not (item.get("comment_draft") or "").strip():
            raise ValueError("A IA não devolveu um comentário: tente outro pedido")
        payload = {**(action["payload"] or {}), "text": item["comment_draft"], "relevance": item.get("relevance"), "reason": item.get("reason")}
        updated = _one("""UPDATE public.automation_actions SET payload = %s, updated_at = NOW()
                           WHERE id = %s AND status = 'proposed' RETURNING *""", (Json(payload), action_id))
        if updated:
            _rows("INSERT INTO public.automation_events (action_id, source, event, data) VALUES (%s, 'user', 'revised', %s)",
                  (action_id, Json({"instruction": instruction[:500]})))
            updated["fit"] = AutomationService.fit_of(updated)
        return updated

    @staticmethod
    def reject(action_id: int) -> Optional[dict]:
        action = _one("""UPDATE public.automation_actions SET status = 'rejected', updated_at = NOW(), finished_at = NOW()
                          WHERE id = %s AND status = 'proposed' RETURNING *""", (action_id,))
        if action and action["kind"] == "apply":
            _rows("UPDATE public.job_listings SET status = 'archived', updated_at = NOW() WHERE id = %s AND status = 'discovered'", (action["target_id"],))
        if action and action["kind"] == "comment":
            _rows("UPDATE public.linkedin_engagement SET status = 'skipped' WHERE id = %s AND status = 'pending'", (action["target_id"],))
        if action and action["kind"] == "connect":
            _rows("UPDATE public.linkedin_prospects SET status = 'skipped' WHERE id = %s AND status = 'to_contact'", (action["target_id"],))
        return action

    @staticmethod
    def approve_docs(action_id: int) -> Optional[dict]:
        """You read the CV generated for the job: it may go."""
        action = _one("""UPDATE public.automation_actions SET status = 'queued', updated_at = NOW()
                          WHERE id = %s AND status = 'review_docs' RETURNING *""", (action_id,))
        if action:
            _rows("UPDATE public.automation_state SET review_cv_left = GREATEST(review_cv_left - 1, 0) WHERE id = 1")
        return action

    @staticmethod
    def confirm_submit(action_id: int) -> Optional[dict]:
        """One of the first applications, you watching: the click that sends it. If the wait ran out before your OK, the
        application goes back to the queue already confirmed: it is filled again and sent without waiting for you a second time."""
        action = _one("""UPDATE public.automation_actions SET result = result || '{"confirmed": true}'::jsonb, updated_at = NOW()
                          WHERE id = %s AND status = 'awaiting_confirm' RETURNING *""", (action_id,))
        if not action:
            action = _one("""UPDATE public.automation_actions
                                SET result = result || '{"confirmed": true}'::jsonb, status = 'queued', error_code = NULL, error_text = NULL,
                                    questions = '[]', updated_at = NOW()
                              WHERE id = %s AND status = 'needs_user' AND error_code = 'confirm_timeout' RETURNING *""", (action_id,))
        if action:
            _rows("UPDATE public.automation_state SET confirm_submit_left = GREATEST(confirm_submit_left - 1, 0) WHERE id = 1")
        return action

    @staticmethod
    def recover_job(job_id: int) -> Optional[dict]:
        """A job the triage discarded comes back for you to approve."""
        job = _one("""UPDATE public.job_listings SET triage_outcome = 'propose' WHERE id = %s AND status = 'discovered' RETURNING *""", (job_id,))
        return AutomationService.propose_job(job) if job else None

    @staticmethod
    def propose_job(job: dict) -> Optional[dict]:
        return AutomationService.create_action(
            "apply", f"apply:{job['id']}", f"{job.get('job_title') or 'Vaga'} · {job.get('company') or ''}", job.get("url"),
            {"job_id": job["id"], "linkedin_job_id": job.get("linkedin_job_id"), "title": job.get("job_title"), "company": job.get("company")},
            target_type="job", target_id=job["id"], rank=0, sort_at=job.get("posted_at") or job.get("created_at"))

    # ── Needs you ────────────────────────────────────────────────────────
    @staticmethod
    def needs_user() -> List[dict]:
        return _rows("""SELECT * FROM public.automation_actions WHERE status IN ('needs_user', 'review_docs', 'awaiting_confirm')
                         ORDER BY updated_at DESC LIMIT 200""")

    @staticmethod
    def answer(action_id: int, answers: List[dict]) -> Optional[dict]:
        """Your answers go to the answer bank and the action back to the queue."""
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                for a in answers:
                    if a.get("save", True) and str(a.get("answer") or "").strip():
                        cur.execute("""
                            INSERT INTO public.automation_answers (question_norm, question, field_type, answer)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (question_norm, field_type) DO UPDATE SET answer = EXCLUDED.answer, updated_at = NOW()""",
                                    (question_key(a["question"]), a["question"], a.get("field_type") or "text", str(a["answer"]).strip()))
                cur.execute("""
                    UPDATE public.automation_actions
                       SET status = 'queued', error_code = NULL, error_text = NULL, questions = '[]', updated_at = NOW()
                     WHERE id = %s AND status = 'needs_user' RETURNING *""", (action_id,))
                row = cur.fetchone()
                if row:
                    _event(cur, action_id, "user", "answered", {"count": len(answers)})
            conn.commit()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def known_answer(label: str, field_type: str) -> Optional[str]:
        """The answer you already gave to this question in another form."""
        row = _one("SELECT answer FROM public.automation_answers WHERE question_norm = %s AND field_type = %s",
                   (question_key(label), field_type))
        return row["answer"] if row else None

    @staticmethod
    def answers_list() -> List[dict]:
        return _rows("SELECT * FROM public.automation_answers ORDER BY updated_at DESC")

    @staticmethod
    def delete_answer(answer_id: int) -> Optional[dict]:
        return _one("DELETE FROM public.automation_answers WHERE id = %s RETURNING *", (answer_id,))

    @staticmethod
    def retry(action_id: int) -> Optional[dict]:
        """You solved it (captcha, login…) or want it tried again: first looks at the page if it may have gone out. A job whose
        CV or cover letter failed (not generated, or refused by the reviewer) gets both written again from scratch."""
        action = _one("""SELECT * FROM public.automation_actions WHERE id = %s
                          AND (status = 'needs_user' OR (status = 'review_docs' AND error_code = 'cv_review_failed'))""", (action_id,))
        if not action:
            return None
        if action["kind"] == "apply" and action["error_code"] in ("documents_failed", "cv_review_failed"):
            _rows("UPDATE public.job_listings SET resume_markdown = NULL, cover_letter = NULL WHERE id = %s", (action["target_id"],))
            status = "approved"
        else:
            status = "unknown_outcome" if (action["result"] or {}).get("executed") else "queued"
        return _one("""UPDATE public.automation_actions SET status = %s, error_code = NULL, error_text = NULL, questions = '[]', updated_at = NOW()
                        WHERE id = %s RETURNING *""", (status, action_id))

    @staticmethod
    def cancel(action_id: int) -> Optional[dict]:
        return _one("""UPDATE public.automation_actions SET status = 'cancelled', finished_at = NOW(), updated_at = NOW()
                        WHERE id = %s AND status = ANY(%s) RETURNING *""",
                    (action_id, ["approved", "review_docs", "queued", "needs_user", "escalated", "unknown_outcome"]))

    # ── Claim: the only way anything starts ──────────────────────────────
    @staticmethod
    def _refusal(state: dict, lane: str, cur) -> Optional[str]:
        cfg = config().get("automation") or {}
        if state["mode"] == "off":
            return "off"
        if state["halted_lanes"] and ("all" in state["halted_lanes"] or lane in state["halted_lanes"]):
            return "halted"
        if lane == "linkedin_write" and state["next_write_at"] and state["next_write_at"] > now():
            return "gap"
        cur.execute("SELECT lane, COUNT(*) AS n FROM public.automation_actions WHERE status = ANY(%s) GROUP BY lane", (list(RUNNING),))
        running = {r["lane"]: r["n"] for r in cur.fetchall()}
        if sum(running.values()) >= cfg.get("max_windows", 3):
            return "max_windows"
        if running.get(lane, 0) >= (cfg.get("lanes") or {}).get(lane, 1):
            return "lane_busy"
        return None

    @staticmethod
    def in_window() -> bool:
        window = (config().get("automation") or {}).get("window") or {}
        return window.get("start_hour", 8) <= _local().hour < window.get("end_hour", 20)

    @staticmethod
    def claim(lane: str, worker: str) -> dict:
        """The next action for this lane, or why there is none. The lock on the state row serializes every claim."""
        limits = None
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.automation_state WHERE id = 1 FOR UPDATE")
                state = dict(cur.fetchone())
                cur.execute("UPDATE public.automation_state SET worker_seen_at = NOW() WHERE id = 1")
                refusal = AutomationService._refusal(state, lane, cur)
                # outside the window only what you approved with "executar agora" goes
                only_now = not AutomationService.in_window()
                if not refusal and only_now:
                    cur.execute("SELECT 1 FROM public.automation_actions WHERE lane = %s AND run_now AND status IN ('queued', 'unknown_outcome') LIMIT 1", (lane,))
                    if not cur.fetchone():
                        refusal = "outside_window"
                if refusal:
                    conn.commit()
                    return {"action": None, "reason": refusal}
                limits = AutomationService.limits(state)
                exhausted = [l["kind"] for l in limits if l["left"] <= 0]
                if state["invites_paused_until"] and state["invites_paused_until"] > now():
                    exhausted.append("connect")
                # what may already have gone out is looked at first: it does not count as a new action
                cur.execute("""
                    SELECT * FROM public.automation_actions
                     WHERE lane = %s AND status = 'unknown_outcome' AND (scheduled_for IS NULL OR scheduled_for <= NOW()) AND (run_now OR NOT %s)
                     ORDER BY updated_at LIMIT 1 FOR UPDATE SKIP LOCKED""", (lane, only_now))
                row = cur.fetchone()
                verify_only = bool(row)
                if not row:
                    cur.execute("""
                        SELECT * FROM public.automation_actions
                         WHERE lane = %s AND status = 'queued' AND NOT (kind = ANY(%s))
                           AND (scheduled_for IS NULL OR scheduled_for <= NOW()) AND (expires_at IS NULL OR expires_at > NOW())
                           AND (run_now OR NOT %s)
                         ORDER BY run_now DESC, rank, sort_at DESC LIMIT 1 FOR UPDATE SKIP LOCKED""", (lane, exhausted, only_now))
                    row = cur.fetchone()
                if not row:
                    conn.commit()
                    return {"action": None, "reason": "empty"}
                action = dict(row)
                if action["payload_hash"] != payload_hash(action["payload"]):
                    cur.execute("""UPDATE public.automation_actions SET status = 'needs_user', error_code = 'payload_changed',
                                          error_text = 'O conteúdo mudou depois da aprovação: nada foi feito', updated_at = NOW() WHERE id = %s""", (action["id"],))
                    _event(cur, action["id"], "backend", "payload_changed", level="error")
                    conn.commit()
                    return {"action": None, "reason": "payload_changed"}
                if not verify_only:
                    try:
                        AutomationService._check_content(cur, action)
                    except content_guard.BlockedContent as e:
                        cur.execute("""UPDATE public.automation_actions SET status = 'needs_user', error_code = 'content_blocked',
                                              error_text = %s, updated_at = NOW() WHERE id = %s""", (str(e), action["id"]))
                        _event(cur, action["id"], "backend", "content_blocked", {"detail": str(e)}, level="error")
                        conn.commit()
                        return {"action": None, "reason": "content_blocked"}
                nonce = secrets.token_urlsafe(12)
                status = "verifying" if verify_only else "running_ext"
                cur.execute("""
                    UPDATE public.automation_actions
                       SET status = %s, lease_owner = %s, lease_until = NOW() + INTERVAL '10 minutes', nonce = %s,
                           attempts = attempts + %s, executor = COALESCE(executor, 'extension'),
                           started_at = COALESCE(started_at, NOW()), updated_at = NOW()
                     WHERE id = %s RETURNING *""", (status, worker, nonce, 0 if verify_only else 1, action["id"]))
                action = dict(cur.fetchone())
                if lane == "linkedin_write" and not verify_only:
                    low, high = (config().get("automation") or {}).get("write_gap_minutes") or [5, 20]
                    cur.execute("UPDATE public.automation_state SET next_write_at = %s WHERE id = 1",
                                (now() + timedelta(minutes=random.uniform(low, high)),))
                _event(cur, action["id"], "backend", "claimed", {"worker": worker, "verify_only": verify_only})
            conn.commit()
        finally:
            conn.close()
        return {"action": {**AutomationService._run_info(action, state), "verify_only": verify_only}, "reason": None}

    @staticmethod
    def _check_content(cur, action: dict) -> None:
        content_guard.ensure_clean(action["payload"], "O texto aprovado")
        if action["kind"] == "apply":
            cur.execute("SELECT resume_markdown, cover_letter FROM public.job_listings WHERE id = %s", (action["target_id"],))
            job = cur.fetchone()
            content_guard.ensure_clean(dict(job) if job else {}, "O CV ou a carta da vaga")

    @staticmethod
    def _run_info(action: dict, state: dict) -> dict:
        confirm = (action["kind"] == "apply" and state["account_kind"] == "main" and state["confirm_submit_left"] > 0
                   and not (action["result"] or {}).get("confirmed"))
        return {"id": action["id"], "kind": action["kind"], "lane": action["lane"], "status": action["status"], "nonce": action["nonce"],
                "target_url": action["target_url"], "target_id": action["target_id"], "payload": action["payload"],
                "allow_final": AutomationService._allow_final(state, action["kind"], action["target_url"]),
                "confirm_required": confirm, "confirmed": bool((action["result"] or {}).get("confirmed")),
                "halted": bool(state["halted_lanes"] and ("all" in state["halted_lanes"] or action["lane"] in state["halted_lanes"]))}

    @staticmethod
    def run_info(action_id: int, nonce: Optional[str] = None) -> Optional[dict]:
        """For the extension (with the nonce it was handed in the page address) and the worker."""
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s", (action_id,))
        if not action or (nonce is not None and action["nonce"] != nonce):
            return None
        return AutomationService._run_info(action, AutomationService.state())

    # ── Reports from the executors ───────────────────────────────────────
    @staticmethod
    def heartbeat(action_id: int) -> Optional[dict]:
        _rows("""UPDATE public.automation_actions SET lease_until = NOW() + INTERVAL '10 minutes'
                  WHERE id = %s AND status = ANY(%s)""", (action_id, list(RUNNING)))
        return AutomationService.run_info(action_id)

    @staticmethod
    def add_event(action_id: int, source: str, event: str, data: dict, level: str = "info", screenshot: Optional[str] = None) -> None:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                _event(cur, action_id, source, event, data, level, screenshot)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def ready_to_submit(action_id: int, fields: Optional[list] = None) -> Optional[dict]:
        """Final screen reached in a run that needs your click: waits for you."""
        return _one("""UPDATE public.automation_actions SET status = 'awaiting_confirm', result = result || %s, updated_at = NOW()
                        WHERE id = %s AND status = 'running_ext' RETURNING *""", (Json({"fields": fields or []}), action_id))

    @staticmethod
    def complete(action_id: int, outcome: str, data: Optional[dict] = None, source: str = "extension") -> Optional[dict]:
        """executed: the final click happened, the worker checks the page before it counts. dry_run: stopped before that click.
        read: a read task finished."""
        data = data or {}
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s AND status = ANY(%s)", (action_id, list(RUNNING)))
        if not action:
            return None
        if outcome == "dry_run":
            return AutomationService._finish(action, {**data, "dry_run": True}, source)
        if outcome == "read":
            return AutomationService._finish(action, data, source)
        allowed = AutomationService._allow_final(AutomationService.state(), action["kind"], action["target_url"])
        if not allowed:   # something clicked that had no permission to: nothing else runs until you look at it
            AutomationService.add_event(action_id, source, "unauthorized_final_action", data, level="error")
            AutomationService.halt(f"Ação #{action_id} ({action['kind']}) foi executada sem permissão", source="backend")
        return _one("""UPDATE public.automation_actions SET status = 'verifying', result = result || %s, updated_at = NOW()
                        WHERE id = %s RETURNING *""", (Json({**data, "executed": True, "executed_at": now().isoformat()}), action_id))

    @staticmethod
    def verify(action_id: int, proof: bool, evidence: Optional[dict] = None) -> Optional[dict]:
        """The page was looked at. Without proof a write that is known to have been clicked is never tried again."""
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s AND status = ANY(%s)", (action_id, list(RUNNING) + ["unknown_outcome"]))
        if not action:
            return None
        AutomationService.add_event(action_id, "worker", "verified", {"proof": proof, **(evidence or {})})
        if proof:
            return AutomationService._finish(action, {"proof": evidence or True}, "worker")
        result = action["result"] or {}
        if result.get("executed"):
            if not result.get("recheck"):   # LinkedIn may take a moment: one more look before asking you
                return _one("""UPDATE public.automation_actions
                                  SET status = 'unknown_outcome', scheduled_for = NOW() + INTERVAL '5 minutes',
                                      result = result || '{"recheck": true}'::jsonb, updated_at = NOW()
                                WHERE id = %s RETURNING *""", (action_id,))
            return AutomationService._to_user(action_id, "verify_failed", "Foi enviado, mas não consegui confirmar na página: confira no LinkedIn")
        if action["attempts"] < 2:   # the crash came before the click: the page shows it did not go out
            return _one("""UPDATE public.automation_actions SET status = 'queued', scheduled_for = NOW() + INTERVAL '10 minutes', updated_at = NOW()
                            WHERE id = %s RETURNING *""", (action_id,))
        return AutomationService._to_user(action_id, "verify_failed", "Não consegui confirmar se foi feito: confira no LinkedIn")

    @staticmethod
    def _to_user(action_id: int, code: str, text: str, questions: Optional[list] = None) -> Optional[dict]:
        return _one("""UPDATE public.automation_actions
                          SET status = 'needs_user', error_code = %s, error_text = %s, questions = %s, lease_owner = NULL, lease_until = NULL, updated_at = NOW()
                        WHERE id = %s RETURNING *""", (code, text, Json(questions or []), action_id))

    @staticmethod
    def escalate(action_id: int, code: str, text: str = "", questions: Optional[list] = None, source: str = "extension",
                 screenshot: Optional[str] = None) -> Optional[dict]:
        """Why it could not finish decides where it goes."""
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s AND status = ANY(%s)", (action_id, list(RUNNING)))
        if not action:
            return None
        AutomationService.add_event(action_id, source, f"escalate:{code}", {"text": text, "questions": questions or []},
                                    level="warning", screenshot=screenshot)
        if code in HALT_CODES:
            lanes = ["ats"] if action["lane"] == "ats" else LINKEDIN_LANES
            if code == "session_expired":
                AutomationService.set_session("logged_out")   # the worker opens the login page for you (noVNC)
            AutomationService.halt(f"{code}: {text}" if text else code, lanes, source=source, ramp_down=action["lane"] != "ats")
            status = "unknown_outcome" if (action["result"] or {}).get("executed") else "queued"
            return _one("""UPDATE public.automation_actions SET status = %s, error_code = %s, error_text = %s, lease_owner = NULL, updated_at = NOW()
                            WHERE id = %s RETURNING *""", (status, code, text, action_id))
        if code == "weekly_invite_limit":
            _rows("UPDATE public.automation_state SET invites_paused_until = NOW() + INTERVAL '7 days' WHERE id = 1")
            return _one("""UPDATE public.automation_actions SET status = 'queued', scheduled_for = NOW() + INTERVAL '7 days', error_code = %s, updated_at = NOW()
                            WHERE id = %s RETURNING *""", (code, action_id))
        if code in DISCARD_CODES:
            return AutomationService._discard(action, code, text)
        if (action["result"] or {}).get("executed"):   # it may have gone out: nobody clicks again, you look
            return AutomationService._to_user(action_id, code, f"Pode já ter sido enviado, confira antes de repetir. {text}".strip(), questions)
        lanes = (config().get("claude") or {}).get("lanes") or []
        if code in CLAUDE_CODES and action["claude_attempts"] < 1 and action["lane"] in lanes:
            return _one("""UPDATE public.automation_actions SET status = 'escalated', error_code = %s, error_text = %s, lease_owner = NULL, updated_at = NOW()
                            WHERE id = %s RETURNING *""", (code, text, action_id))
        return AutomationService._to_user(action_id, code, text, questions)

    @staticmethod
    def _discard(action: dict, code: str, text: str) -> Optional[dict]:
        if code == "already_applied" and action["kind"] == "apply":
            _rows("UPDATE public.job_listings SET status = 'applied', applied_at = COALESCE(applied_at, NOW()), updated_at = NOW() WHERE id = %s", (action["target_id"],))
        if code in ("already_connected", "already_pending") and action["kind"] == "connect":
            status = "accepted" if code == "already_connected" else "invited"
            _rows("UPDATE public.linkedin_prospects SET status = %s, updated_at = NOW() WHERE id = %s AND status = 'to_contact'", (status, action["target_id"]))
        return _one("""UPDATE public.automation_actions SET status = 'discarded', error_code = %s, error_text = %s, finished_at = NOW(), lease_owner = NULL, updated_at = NOW()
                        WHERE id = %s RETURNING *""", (code, text, action["id"]))

    @staticmethod
    def _finish(action: dict, data: dict, source: str) -> Optional[dict]:
        """Done, and what it means for the rest of the system. A dry run changes nothing else."""
        if not data.get("dry_run"):
            AutomationService._side_effects(action)
        done = _one("""UPDATE public.automation_actions SET status = 'done', result = result || %s, finished_at = NOW(), lease_owner = NULL, lease_until = NULL, updated_at = NOW()
                        WHERE id = %s RETURNING *""", (Json(data), action["id"]))
        AutomationService.add_event(action["id"], source, "done", {"dry_run": bool(data.get("dry_run"))})
        return done

    @staticmethod
    def _side_effects(action: dict) -> None:
        from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot
        kind, target = action["kind"], action["target_id"]
        if kind == "apply":
            _rows("""UPDATE public.job_listings SET status = 'applied', applied_via_bot = TRUE, applied_at = NOW(), updated_at = NOW()
                      WHERE id = %s AND status NOT IN ('interviewing', 'offer', 'rejected')""", (target,))
        elif kind == "comment":
            Copilot.update_engagement(target, "done", action["payload"].get("text"))
        elif kind == "connect":
            Copilot.update_prospect(target, "invited")

    @staticmethod
    def abort(action_id: int, reason: str = "stopped", retry_after: int = 0) -> Optional[dict]:
        """The worker closed the window (you stopped it, it is shutting down, no browser). Nothing is assumed about what happened."""
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s AND status = ANY(%s)", (action_id, list(RUNNING)))
        if not action:
            return None
        AutomationService.add_event(action_id, "worker", "aborted", {"reason": reason}, level="warning")
        status = "unknown_outcome" if action["kind"] in WRITE_KINDS else "queued"
        return _one("""UPDATE public.automation_actions SET status = %s, scheduled_for = NOW() + make_interval(secs => %s), lease_owner = NULL, lease_until = NULL, updated_at = NOW()
                        WHERE id = %s RETURNING *""", (status, retry_after, action_id))

    @staticmethod
    def handoff(action_id: int, url: str) -> Optional[dict]:
        """The job applies on the company site: goes to the browser without your LinkedIn session, if that is switched on."""
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s AND status = ANY(%s)", (action_id, list(RUNNING)))
        if not action:
            return None
        AutomationService.add_event(action_id, "worker", "handoff", {"url": url})
        if not (config().get("jobs") or {}).get("external_apply"):
            return AutomationService._to_user(action_id, "external_manual", f"Candidatura no site da empresa: {url}")
        return _one("""UPDATE public.automation_actions SET lane = 'ats', target_url = %s, status = 'queued', lease_owner = NULL, updated_at = NOW()
                        WHERE id = %s RETURNING *""", (url, action_id))

    # ── Claude fallback ──────────────────────────────────────────────────
    @staticmethod
    def claude_claim(runner: str) -> dict:
        """The next stuck action for the routine on the host, or why there is none. One attempt per action."""
        cfg = config().get("claude") or {}
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.automation_state WHERE id = 1 FOR UPDATE")
                state = dict(cur.fetchone())
                if state["mode"] == "off":
                    conn.commit()
                    return {"action": None, "reason": "off"}
                cur.execute("SELECT COUNT(*) AS n FROM public.automation_runs WHERE kind = 'claude' AND started_at >= %s", (_period_start("day"),))
                if cur.fetchone()["n"] >= cfg.get("per_day", 15):
                    conn.commit()
                    return {"action": None, "reason": "daily_cap"}
                only_now = not AutomationService.in_window()   # outside the window, only "executar agora"
                halted = state["halted_lanes"] or []
                lanes = [l for l in (cfg.get("lanes") or []) if "all" not in halted and l not in halted]
                cur.execute("""SELECT * FROM public.automation_actions WHERE status = 'escalated' AND lane = ANY(%s) AND (run_now OR NOT %s)
                                ORDER BY rank, sort_at DESC LIMIT 1 FOR UPDATE SKIP LOCKED""", (lanes, only_now))
                row = cur.fetchone()
                if not row:
                    conn.commit()
                    return {"action": None, "reason": "outside_window" if only_now else "empty"}
                action = dict(row)
                cur.execute("""UPDATE public.automation_actions
                                  SET status = 'running_claude', executor = 'claude', claude_attempts = claude_attempts + 1,
                                      lease_owner = %s, lease_until = NOW() + INTERVAL '12 minutes', updated_at = NOW()
                                WHERE id = %s RETURNING *""", (runner, action["id"]))
                action = dict(cur.fetchone())
                cur.execute("INSERT INTO public.automation_runs (kind, action_id) VALUES ('claude', %s) RETURNING id", (action["id"],))
                run_id = cur.fetchone()["id"]
            conn.commit()
        finally:
            conn.close()
        return {"action": {**AutomationService._run_info(action, state), "run_id": run_id, "dossier": AutomationService._dossier(action)}, "reason": None}

    @staticmethod
    def _dossier(action: dict) -> dict:
        """All the agent may use: what to do, on which address, with which values. No keys or tokens."""
        from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot
        dossier = {"kind": action["kind"], "target_url": action["target_url"], "payload": action["payload"], "why_stuck": action["error_text"]}
        if action["kind"] == "apply":
            from app.api.actions import _pdf_name
            job = _one("SELECT job_title, company, location, url, resume_markdown, cover_letter, language, description FROM public.job_listings WHERE id = %s", (action["target_id"],)) or {}
            # the worker saved these in /data/run/<id>, in the container where the browser tools run (handlers.prepare_documents).
            # They are named by /tmp/careerops-run/<id>, a link to that folder: the routine's own working folder has this same
            # path on the host, and the browser tool uploads only from its client's working folder (symlinks resolved).
            folder = f"/tmp/careerops-run/{action['id']}"
            dossier.update({"job": {k: job.get(k) for k in ("job_title", "company", "location", "url")}, "facts": Copilot._facts(),
                            "saved_answers": [{"question": a["question"], "answer": a["answer"]} for a in AutomationService.answers_list()],
                            "resume_markdown": job.get("resume_markdown") or "",
                            "files": {"resume": f"{folder}/{_pdf_name(job, 'resume')}", "cover_letter": f"{folder}/{_pdf_name(job, 'cover')}"}})
        return dossier

    @staticmethod
    def claude_result(action_id: int, run_id: int, status: str, summary: str = "", questions: Optional[list] = None,
                      audit_flags: Optional[list] = None, cost_usd: Optional[float] = None, transcript: Optional[dict] = None) -> Optional[dict]:
        _rows("UPDATE public.automation_runs SET finished_at = NOW(), ok = %s, cost_usd = %s, summary = %s WHERE id = %s",
              (status == "done" and not audit_flags, cost_usd, Json({"summary": summary, "audit_flags": audit_flags or [], **(transcript or {})}), run_id))
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s AND status = 'running_claude'", (action_id,))
        if not action:
            return None
        AutomationService.add_event(action_id, "claude", f"result:{status}", {"summary": summary, "audit_flags": audit_flags or []},
                                    level="error" if audit_flags else "info")
        if audit_flags:   # it touched something outside the target: you look before anything else happens
            AutomationService.halt(f"Claude fora do alvo na ação #{action_id}: {'; '.join(map(str, audit_flags))[:300]}", [action["lane"]], source="claude")
            return AutomationService._to_user(action_id, "claude_audit", f"Saiu do alvo: {'; '.join(map(str, audit_flags))[:500]}")
        if status == "done":   # the worker looks at the page: the model saying so is not enough
            return _one("""UPDATE public.automation_actions SET status = 'unknown_outcome', scheduled_for = NULL, lease_owner = NULL,
                                  result = result || %s, updated_at = NOW() WHERE id = %s RETURNING *""",
                        (Json({"executed": True, "claude_summary": summary, "executed_at": now().isoformat()}), action_id))
        return AutomationService._to_user(action_id, "claude_stopped", summary or "O Claude não conseguiu concluir", questions)

    @staticmethod
    def set_session(status: str) -> None:
        """What the worker sees of the LinkedIn session: logged_in / logged_out."""
        _rows("UPDATE public.automation_state SET session_status = %s, worker_seen_at = NOW() WHERE id = 1", (status,))

    # ── Screens ──────────────────────────────────────────────────────────
    @staticmethod
    def status() -> dict:
        state = AutomationService.state()
        counts = {r["status"]: r["n"] for r in _rows("SELECT status, COUNT(*) AS n FROM public.automation_actions WHERE status = ANY(%s) GROUP BY status", (list(OPEN),))}
        claude_today = _one("SELECT COUNT(*) AS n FROM public.automation_runs WHERE kind = 'claude' AND started_at >= %s", (_period_start("day"),))["n"]
        seen = state.get("worker_seen_at")
        return {"state": state, "counts": counts, "limits": AutomationService.limits(state), "claude_today": claude_today,
                "claude_per_day": (config().get("claude") or {}).get("per_day", 15), "worker_online": bool(seen and now() - seen < timedelta(minutes=3)),
                "final_submit_possible": AutomationService._allow_final(state, "apply", None),
                "novnc_url": settings.CAREEROPS_NOVNC_URL}

    @staticmethod
    def running() -> List[dict]:
        return _rows("SELECT * FROM public.automation_actions WHERE status = ANY(%s) ORDER BY updated_at DESC", (list(RUNNING) + ["queued", "approved", "escalated", "unknown_outcome"],))

    @staticmethod
    def history(limit: int = 100) -> List[dict]:
        return _rows("""SELECT * FROM public.automation_actions WHERE status IN ('done', 'discarded', 'failed', 'expired', 'cancelled')
                         ORDER BY finished_at DESC NULLS LAST, updated_at DESC LIMIT %s""", (limit,))

    @staticmethod
    def events(action_id: int) -> List[dict]:
        return _rows("SELECT * FROM public.automation_events WHERE action_id = %s ORDER BY at", (action_id,))

    # ── Every minute (main.py) ───────────────────────────────────────────
    @staticmethod
    def housekeeping() -> None:
        """Approvals that aged out; leases that ran out (a write is not assumed either way); the ramp going up."""
        _rows("""UPDATE public.automation_actions SET status = 'expired', finished_at = NOW(), updated_at = NOW()
                  WHERE status IN ('approved', 'review_docs', 'queued') AND expires_at < NOW()""")
        _rows("""UPDATE public.automation_actions SET status = CASE WHEN kind = ANY(%s) THEN 'unknown_outcome' ELSE 'queued' END,
                        lease_owner = NULL, lease_until = NULL, updated_at = NOW()
                  WHERE status = ANY(%s) AND lease_until < NOW()""", (list(WRITE_KINDS), list(RUNNING)))
        # a read that did not get its turn is not worth doing late: the next slot reads the page as it is then
        _rows("""UPDATE public.automation_actions SET status = 'expired', finished_at = NOW(), updated_at = NOW()
                  WHERE lane = 'linkedin_read' AND status = 'queued' AND created_at < NOW() - INTERVAL '18 hours'""")
        days = (config().get("automation") or {}).get("ramp_days", 7)
        _rows("""UPDATE public.automation_state SET ramp_step = ramp_step + 1, ramp_step_at = NOW()
                  WHERE id = 1 AND ramp_auto AND ramp_step < 2 AND mode = 'live' AND halted_at IS NULL AND ramp_step_at < NOW() - make_interval(days => %s)""", (days,))
        # what the screens and the queue no longer need: screenshots are removed by the worker, their rows here
        _rows("DELETE FROM public.automation_events WHERE at < NOW() - INTERVAL '90 days'")

    @staticmethod
    def prepare_documents() -> int:
        """Approved jobs: the CV and the cover letter are generated now, one at a time (blocking: call it from a thread), and
        read by the reviewer agent (cv_review: agent) or by you (cv_review: you, the first 20 on the main account)."""
        import asyncio
        from app.services.cv_review_service import CvReviewService, reasons
        from app.services.job_pipeline_service import JobPipelineService
        done = 0
        state = AutomationService.state()
        by_agent = (config().get("jobs") or {}).get("cv_review", "agent") == "agent"
        for action in _rows("SELECT * FROM public.automation_actions WHERE kind = 'apply' AND status = 'approved' ORDER BY rank, sort_at DESC LIMIT 2"):
            try:
                asyncio.run(JobPipelineService.generate_docs(action["target_id"]))
                job = _one("SELECT resume_markdown, cover_letter FROM public.job_listings WHERE id = %s", (action["target_id"],)) or {}
                if not job.get("resume_markdown"):
                    raise RuntimeError("o CV não foi gerado")
                if by_agent:
                    verdict = asyncio.run(CvReviewService.run(action["target_id"]))
                    AutomationService.add_event(action["id"], "reviewer", "cv_review", {k: verdict[k] for k in ("approved", "rounds", "history")},
                                                level="info" if verdict["approved"] else "warning")
                    if verdict["approved"]:
                        _rows("UPDATE public.automation_actions SET status = 'queued', updated_at = NOW() WHERE id = %s", (action["id"],))
                    else:   # still wrong after being redone: it waits for you, with the reasons
                        _rows("""UPDATE public.automation_actions SET status = 'review_docs', error_code = 'cv_review_failed', error_text = %s,
                                        updated_at = NOW() WHERE id = %s""",
                              (f"O revisor recusou depois de {verdict['rounds']} refação(ões): {reasons(verdict)}", action["id"]))
                else:
                    review = state["account_kind"] == "main" and state["review_cv_left"] > 0
                    _rows("UPDATE public.automation_actions SET status = %s, updated_at = NOW() WHERE id = %s",
                          ("review_docs" if review else "queued", action["id"]))
                done += 1
            except Exception as e:
                log.warning("documents for action %s not generated: %s", action["id"], e)
                AutomationService._to_user(action["id"], "documents_failed", f"Não consegui gerar os documentos: {e}")
        return done

    @staticmethod
    def sync_proposals() -> int:
        """What is ready becomes something for you to approve: prospects with a note, comments with a draft, jobs to apply to,
        companies of your jobs to follow. At most a screenful of each kind at a time."""
        made = 0
        open_count = {r["kind"]: r["n"] for r in _rows("SELECT kind, COUNT(*) AS n FROM public.automation_actions WHERE status = 'proposed' GROUP BY kind")}
        for p in _rows("""
            SELECT p.* FROM public.linkedin_prospects p
             WHERE p.status = 'to_contact' AND p.profile_url IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM public.automation_actions a WHERE a.idempotency_key = 'connect:' || p.id)
             ORDER BY CASE WHEN p.segment = 'hiring_team' THEN 0 ELSE 1 END, p.fit DESC NULLS LAST LIMIT %s""",
                       (max(30 - open_count.get("connect", 0), 0),)):
            made += bool(AutomationService.create_action(
                "connect", f"connect:{p['id']}", p.get("name") or p["profile_url"], p["profile_url"],
                {"profile_url": p["profile_url"], "name": p.get("name"), "headline": p.get("headline"), "fit": p.get("fit"), "reason": p.get("reason")},
                target_type="prospect", target_id=p["id"], rank=20 if p.get("market") != "br" else 21))
        for e in _rows("""
            SELECT e.* FROM public.linkedin_engagement e
             WHERE e.status = 'pending' AND e.post_url IS NOT NULL AND COALESCE(e.comment_draft, '') <> ''
               AND NOT EXISTS (SELECT 1 FROM public.automation_actions a WHERE a.idempotency_key = 'comment:' || e.id)
             ORDER BY e.relevance DESC NULLS LAST LIMIT %s""", (max(20 - open_count.get("comment", 0), 0),)):
            made += bool(AutomationService.create_action(
                "comment", f"comment:{e['id']}", e.get("author_name") or "Post", e["post_url"],
                {"post_url": e["post_url"], "post_head": (e.get("post_text") or "")[:500], "author": e.get("author_name"), "text": e["comment_draft"],
                 "relevance": e.get("relevance"), "reason": e.get("reason")},
                target_type="engagement", target_id=e["id"], rank=10 if e.get("market") != "br" else 11, sort_at=e.get("created_at")))
        # jobs you added by hand wait for approval too (what the searches find is proposed by the triage)
        for j in _rows("""
            SELECT j.* FROM public.job_listings j
             WHERE j.status IN ('new', 'scraped') AND COALESCE(j.eligibility_status, '') <> 'blocked' AND COALESCE(j.description, '') <> ''
               AND j.url LIKE '%%linkedin.com/jobs%%'
               AND NOT EXISTS (SELECT 1 FROM public.automation_actions a WHERE a.idempotency_key = 'apply:' || j.id)
             ORDER BY j.created_at DESC LIMIT %s""", (max(30 - open_count.get("apply", 0), 0),)):
            made += bool(AutomationService.propose_job(j))
        return made

    @staticmethod
    def follow_target(url: str, name: str, why: str = "", market: Optional[str] = None) -> Optional[dict]:
        clean = url.split("?")[0].split("#")[0].rstrip("/")
        rank = 30 if market != "br" else 31
        return AutomationService.create_action("follow", f"follow:{clean.lower()}", name or clean, clean,
                                               {"url": clean, "name": name, "why": why}, target_type="url", rank=rank)

    @staticmethod
    def schedule_reads() -> int:
        """The day's searches, checks and scans enter the queue at their hour. One per slot, however often this runs."""
        from app.services.job_search_service import JobSearchService
        cfg = config().get("automation") or {}
        local = _local()
        day = local.date().isoformat()
        made = 0
        for hour in cfg.get("search_hours") or []:
            if local.hour >= hour:
                for s in JobSearchService.round_for(local.date()):
                    made += bool(AutomationService.create_action(
                        "search", f"search:{s['slug']}:{day}:{hour}", s["name"], JobSearchService.linkedin_url(s),
                        {"search": s["slug"], "name": s["name"]}, status="queued", target_type="search", target_id=s["id"], rank=40))
        for hour in cfg.get("check_hours") or []:
            if local.hour >= hour:
                made += bool(AutomationService.create_action(
                    "check", f"check:{day}:{hour}", "Quem aceitou e respondeu", "https://www.linkedin.com/mynetwork/invite-connect/connections/",
                    {}, status="queued", rank=41))
        for hour in cfg.get("feed_scan_hours") or []:
            if local.hour >= hour:
                made += bool(AutomationService.create_action(
                    "feed_scan", f"feed_scan:{day}:{hour}", "Posts do feed", "https://www.linkedin.com/feed/", {"limit": 8}, status="queued", rank=42))
        for hour in cfg.get("follow_scan_hours") or []:
            if local.hour >= hour:
                target = JobSearchService.next_follow_scan()
                if target:
                    made += bool(AutomationService.create_action(
                        "follow_scan", f"follow_scan:{target['key']}", target["name"], target["url"], target, status="queued", rank=43))
        return made

    @staticmethod
    def expire_stale_proposals() -> None:
        _rows("""UPDATE public.automation_actions SET status = 'expired', finished_at = NOW(), updated_at = NOW()
                  WHERE status = 'proposed' AND kind = 'comment' AND created_at < NOW() - INTERVAL '7 days'""")
        # a job you already moved on (applied by hand, rejected, archived) leaves the approval list
        _rows("""UPDATE public.automation_actions a SET status = 'discarded', error_code = 'already_handled', finished_at = NOW(), updated_at = NOW(),
                        error_text = 'Saiu da lista: a vaga já está como ' || j.status
                   FROM public.job_listings j
                  WHERE a.status = 'proposed' AND a.kind = 'apply' AND a.target_type = 'job' AND j.id = a.target_id
                    AND j.status NOT IN ('new', 'scraped', 'discovered')""")

    @staticmethod
    def tick() -> None:
        """Blocking: main.py calls it from a thread. Off, it only keeps the books."""
        from app.services.job_search_service import JobSearchService
        from app.services.bot_service import BotService
        AutomationService.housekeeping()
        AutomationService.expire_stale_proposals()
        if AutomationService.state().get("mode") != "off":
            AutomationService.schedule_reads()
            JobSearchService.triage_pending()
            AutomationService.sync_proposals()
            JobSearchService.score_proposed()
            AutomationService.prepare_documents()
        try:   # what to tell you on WhatsApp; a failure here never holds the queue
            BotService.collect()
        except Exception as e:
            log.warning("bot notifications not collected: %s", e)
