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
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import yaml
from psycopg2.extras import Json

from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor
from app.services import answer_match, content_guard

log = logging.getLogger("automation")

WRITE_KINDS = ("apply", "comment", "follow", "connect", "reply", "like", "message")
SCAN_KINDS = ("check", "feed_scan", "follow_scan", "saved_import", "reply_scan", "inbox_scan")   # no target: a newer one replaces an older one
READ_KINDS = ("search", "check", "feed_scan", "follow_scan", "saved_import", "reply_scan", "thread_read", "inbox_scan")
# What the system does on its own, without your OK (2026-11-08): liking a reply that needs no answer, turning down a
# service offer politely. Each one goes straight to the queue ("auto_approved" event), inside the window and the limits.
AUTO_KINDS = ("like", "message")
# Reads that keep their own hours (Configurações) instead of the time window of the rest
ANYTIME_KINDS = ("saved_import",)
RUNNING = ("running_ext", "verifying", "awaiting_confirm", "running_claude")
OPEN = ("proposed", "approved", "review_docs", "queued", "unknown_outcome", "escalated", "needs_user") + RUNNING

# What happens to an action that could not finish, by the reason the executor gives
CLAUDE_CODES = {"selector_not_found", "step_stuck", "unexpected_layout", "external_form_unfinished"}
HALT_CODES = {"checkpoint", "restriction_notice", "session_expired", "rate_limited"}
DISCARD_CODES = {"job_closed", "already_applied", "post_deleted", "already_following", "already_connected", "already_pending", "already_liked"}

CAPTCHA_RE = re.compile(
    r"captcha|recaptcha|hcaptcha|cloudflare|turnstile|anti[- ]?bot|n[aã]o sou um rob[oô]|"
    r"no es un robot|human verification|verify you are human|puzzle|security check",
    re.I,
)
CLOSED_JOB_RE = re.compile(
    r"no longer available|n['’]?est plus disponible|has expired|not accepting applications|"
    r"no apply or easy apply|no longer accepting applications|vaga.*encerrada|position.*closed|job.*closed",
    re.I,
)
QUOTA_RE = re.compile(r"502:?\s*bad gateway|cota .* esgotada|quota reached|weekly limit|hydrogen upstream failed", re.I)
TRANSIENT_RE = re.compile(
    r"502:?\s*bad gateway|cota .* esgotada|quota reached|weekly limit|hydrogen upstream failed|"
    r"hydrogen execution error|remote end closed connection|connection refused|"
    r"timed out|timeouterror|timeout\s+\d+ms|127\.0\.0\.1:922[23]|connect_timeout|econnrefused|503 service unavailable|"
    r"request not processed|connectionreseterror|without a valid status payload|err_aborted|frame was detached|"
    r"tentei usar uma ferramenta|tool_call|careerops-apply-copilot|step limit|65 steps",
    re.I,
)
RESET_IN_RE = re.compile(r"resets?\s+in\s+(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?", re.I)
ATS_AUTH_RETRY_RE = re.compile(
    r"sign in|log in|\blogin\b|create an account|criar conta|account required|"
    r"email verification|verification code|c[oó]digo de verifica[cç][aã]o|verify.*email",
    re.I,
)
IDENTITY_CHECK_RE = re.compile(
    r"biometr|selfie|identity verification|verify (your )?identity|verifica[cç][aã]o de identidade|verificar (sua )?identidade|"
    r"documento (oficial )?com foto|photo id|government[- ]issued id|id document|liveness|\b(onfido|jumio|veriff)\b|persona (widget|identity)|via persona",
    re.I,
)
URL_EXTRACT_RE = re.compile(r"https?://[^\s<>\"')\]}]+", re.I)


def _deterministic_answer(question: str) -> Optional[str]:
    """Fast deterministic fallback for recurring ATS/Easy Apply screening questions."""
    raw = (question or "").strip()
    if not raw:
        return None
    tail = raw.split(" › ")[-1].lower()
    low = raw.lower()
    text = f"{low}\n{tail}"
    if re.search(r"notice\s*period|aviso\s*pr[eé]vio|per[ií]odo de aviso|incorporaci[oó]n|how\s+soon\s+can\s+you\s+start|earliest\s+start", text):
        return "21" if re.search(r"\b(in\s+days|dias)\b", text) else "3 weeks"
    if re.search(r"driver'?s?\s+licen[cs]e|driving\s+licen[cs]e|carnet\s+de\s+conducir|\bcnh\b", text):
        return "Yes"
    if re.search(r"provide.*references|professional\s+references|\b\d*\s*references\b", text):
        return "Yes"
    if re.search(
        r"relatives?|family\s+member|conflict\s+of\s+interest|significant\s+interest|0\.1%|"
        r"previously\s+employed|worked\s+for\s+|former\s+employee|government\s+official|"
        r"bound\s+by\s+any\s+agreement|non[- ]?compete|restrictive\s+covenant",
        text,
    ):
        return "No"
    if re.search(
        r"privacy|consent|certif(y|ied)|acknowledge|i\s+agree|accept.*terms|background\s+check|"
        r"data\s+processing|retention|accurate\s+and\s+true|confirm\s+that|\blgpd\b|\bgdpr\b",
        text,
    ):
        return "Yes"
    if re.search(r"end\s+date\s+month|graduation\s+month|month.*graduat|m[eê]s.*conclus[aã]o", text):
        return "December"
    if re.search(r"highest\s+level\s+of\s+education|\bdegree\b|escolaridade|forma[cç][aã]o", text):
        return "Bachelor's Degree"
    if re.search(r"strictly\s+(looking\s+for\s+)?remote|only\s+remote", text):
        return "No"
    if re.search(r"willing\s+to\s+travel|comfortable\s+working\s+remotely|time\s*zone|overlap\s+with|remote\s+work|trabalho\s+remoto", text):
        return "Yes"
    if re.search(
        r"(legally\s+)?authorized\s+to\s+work\s+in\s+(the\s+)?(united\s+states|\bus\b|\busa\b|"
        r"united\s+kingdom|\buk\b|spain|european\s+union|\beu\b|canada)|\beu\s+citizen",
        text,
    ):
        return "No"
    if re.search(r"(legally\s+)?authorized\s+to\s+work\s+in\s+brazil|autorizado.*trabalhar.*brasil", text):
        return "Yes"
    if re.search(r"(require|need).*?(visa\s+)?sponsorship|visa\s+sponsorship|visto\s+de\s+trabalho", text):
        return "Yes"
    if re.search(r"salary\s+expectation|desired\s+(annual\s+)?(base\s+)?(salary|compensation|pay)|pretens[aã]o\s+salarial|hourly\s+rate|remunera[cç][aã]o", text):
        if "eur" in text or "€" in text:
            return "74400"
        if "brl" in text or "r$" in text:
            return "420000" if re.search(r"year|annual|anual|ano", text) else "35000"
        if "month" in text or "mensal" in text:
            return "7000"
        if "hour" in text or "hora" in text:
            return "45"
        return "84000"
    if re.search(r"\b(gender|sex)\b|identidade\s+de\s+g[eê]nero", text):
        return "Male"
    if re.search(r"hispanic\s+or\s+latino|\b(ethnicity|race)\b|ra[cç]a|etnia", text):
        return "Hispanic or Latino"
    if re.search(r"\b(disability|disabled|veteran|pcd)\b", text):
        return "No"
    if re.search(r"how\s+did\s+you\s+hear|where\s+did\s+you\s+hear|referral\s+source|como\s+soube", text):
        return "LinkedIn"
    return None
# Everything else (unknown question, captcha, login, an account to create…) is yours: Precisa de você

LINKEDIN_LANES = ["linkedin_read", "linkedin_write"]

# The old address of your saved jobs: LinkedIn sends it to the page of the day (/jobs-tracker/ since late 2026)
SAVED_JOBS_URL = "https://www.linkedin.com/my-items/saved-jobs/"
NOTIFICATIONS_URL = "https://www.linkedin.com/notifications/?filter=all"
RECEIVED_INVITES_URL = "https://www.linkedin.com/mynetwork/invitation-manager/received/"
SAVED_IMPORT_DEFAULT = {"enabled": True, "day_start": 8, "day_end": 24, "day_every": 1, "night_every": 2}


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
    """Applies migrations_v15.sql through migrations_v25.sql (idempotent)."""
    folder = Path(__file__).resolve().parent.parent / "db" / "migrations"
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for name in ("migrations_v15.sql", "migrations_v17.sql", "migrations_v18.sql", "migrations_v19.sql",
                         "migrations_v20.sql", "migrations_v21.sql", "migrations_v22.sql", "migrations_v23.sql",
                         "migrations_v24.sql", "migrations_v25.sql"):
                cur.execute((folder / name).read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


VERIFY_TRIES = 3   # checks of an "unknown" write with no verdict before it goes to you

# One job posted in many places (2026-11-19: "AI ML Engineer - Remote - Latin America" 10 times, one per Brazilian city):
# the same company and the same title are one job, whatever the place
JOB_KEY_SQL = "lower(regexp_replace(coalesce(company, ''), '\\W', '', 'g')) || '|' || lower(regexp_replace(coalesce(job_title, ''), '\\W', '', 'g'))"
PLACE_REASON = "Local fora do foco"   # a copy discarded for its place says nothing about a copy in a good place
# an application in one of these is the job's application: a twin of it is never sent
TWIN_APPLY_STATUSES = ("done", "running_ext", "running_claude", "verifying", "unknown_outcome", "escalated", "needs_user", "awaiting_confirm")


def job_key(company: Optional[str], title: Optional[str]) -> str:
    """Python side of JOB_KEY_SQL (same result for the same strings)."""
    norm = lambda x: re.sub(r"\W", "", x or "").lower()
    return f"{norm(company)}|{norm(title)}"


def _twin_apply(cur, action: dict, statuses=TWIN_APPLY_STATUSES) -> Optional[dict]:
    """Another application to the same job (same company and title, another place), in one of `statuses`."""
    if action.get("kind") != "apply" or not action.get("target_id"):
        return None
    cur.execute(f"""SELECT a.id, a.status, j.location FROM public.automation_actions a JOIN public.job_listings j ON j.id = a.target_id
                      WHERE a.kind = 'apply' AND a.id <> %s AND a.target_id <> %s AND a.status = ANY(%s)
                        AND {JOB_KEY_SQL.replace('company', 'j.company').replace('job_title', 'j.job_title')} =
                            (SELECT {JOB_KEY_SQL} FROM public.job_listings WHERE id = %s)
                      ORDER BY a.updated_at DESC LIMIT 1""", (action["id"] or 0, action["target_id"], list(statuses), action["target_id"]))
    row = cur.fetchone()
    return dict(row) if row else None


def _same_site_link(link: str, action: dict) -> bool:
    """An e-mail link the agent may open: the form's own site (same registrable domain as the job's page), never another
    one (the runner's audit would stop the lane on it anyway)."""
    from urllib.parse import urlparse
    root = lambda h: ".".join((h or "").lower().rstrip(".").split(".")[-2:])
    host = urlparse(link).hostname or ""
    targets = [urlparse(action.get("target_url") or "").hostname or ""]
    return bool(host) and any(t and root(t) == root(host) for t in targets)


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
        if state["account_kind"] == "test" and kind in ("comment", "connect", "reply", "message"):
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
        """Each kind: the limit at the current step of the ramp and how much of it is used. Only the automations count:
        what you approved, retried or sent with "executar agora" neither uses the limit nor waits for it."""
        state = state or AutomationService.state()
        step = min(max(state.get("ramp_step", 0), 0), 2)
        out = []
        for row in _rows("SELECT * FROM public.automation_limits ORDER BY kind"):
            start = _period_start(row["period"])
            if row["kind"] == "job_read":   # LinkedIn ads only: the other sources have their own limit (source_read)
                used = _one("""SELECT COUNT(*) AS n FROM public.job_listings WHERE search_slug IS NOT NULL AND source = 'linkedin'
                                 AND created_at >= %s""", (start,))["n"]
            elif row["kind"] == "source_read":   # new jobs from the other sources, each one read by the AI
                used = _one("SELECT COUNT(*) AS n FROM public.job_listings WHERE source <> 'linkedin' AND created_at >= %s", (start,))["n"]
            elif row["kind"] == "job_propose":   # jobs the search put on your approval list today (not the ones you added)
                used = _one("""SELECT COUNT(*) AS n FROM public.automation_actions a JOIN public.job_listings j ON j.id = a.target_id
                                WHERE a.kind = 'apply' AND a.target_type = 'job' AND j.search_slug IS NOT NULL AND a.created_at >= %s""",
                            (start,))["n"]
            elif row["kind"] in WRITE_KINDS:
                # what went out or may have (done, clicked, running now): a try that stopped before the final click sent
                # nothing to LinkedIn and is not counted (2026-11-04: invites that never left had filled the week's 20)
                used = _one("""SELECT COUNT(*) AS n FROM public.automation_actions
                                WHERE kind = %s AND started_at >= %s AND NOT (run_now OR approved_at IS NOT NULL)
                                  AND (status = 'done' OR status = ANY(%s) OR result ? 'executed')""", (row["kind"], start, list(RUNNING)))["n"]
            else:
                used = _one("""SELECT COUNT(*) AS n FROM public.automation_actions
                                WHERE kind = %s AND started_at >= %s AND status NOT IN ('discarded', 'cancelled')
                                  AND NOT (run_now OR approved_at IS NOT NULL)""", (row["kind"], start))["n"]
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
                      sort_at: Optional[datetime] = None, lane: Optional[str] = None, auto: bool = False) -> Optional[dict]:
        """One action per idempotency key: proposing the same thing twice does nothing. auto (only AUTO_KINDS): it goes
        without your OK — unless its text fails the NDA guard, then it waits for you like any other."""
        lane = lane or ("linkedin_read" if kind in READ_KINDS else "linkedin_write")
        if auto and kind in AUTO_KINDS:
            try:
                content_guard.ensure_clean(payload, "O texto automático")
            except content_guard.BlockedContent:
                auto, status = False, "proposed"
        else:
            auto = False
        action = _one("""
            INSERT INTO public.automation_actions (kind, lane, status, target_type, target_id, target_url, title, rank, sort_at,
                                                   payload, payload_hash, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), %s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING RETURNING *""",
                    (kind, lane, status, target_type, target_id, target_url, title, rank, sort_at, Json(payload), payload_hash(payload), key))
        if action and auto:
            hours = ((config().get("automation") or {}).get("approval_hours") or {}).get(kind, 48)
            # not approved_at: like the reads, it keeps to the time window and to the day's limit of its kind
            action = _one("""UPDATE public.automation_actions SET status = 'queued', expires_at = %s, updated_at = NOW()
                              WHERE id = %s RETURNING *""", (now() + timedelta(hours=hours), action["id"]))
            _rows("INSERT INTO public.automation_events (action_id, source, event, data) VALUES (%s, 'backend', 'auto_approved', '{}'::jsonb)",
                  (action["id"],))
        return action

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
                   j.eligibility_status, j.eligibility_issues, j.company, j.job_title, j.location, j.source AS job_source
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
            SELECT id, job_title, company, location, url, triage_score, triage_reason, posted_at, employer_market, source FROM public.job_listings
             WHERE status = 'discovered' AND triage_outcome = 'discarded' ORDER BY updated_at DESC LIMIT 100""")
        return grouped

    @staticmethod
    def _approved_payload(cur, action: dict, text: Optional[str]) -> dict:
        """What will be executed, frozen now. Editing means approving a new text."""
        payload = dict(action["payload"] or {})
        if action["kind"] in ("reply", "message"):
            if text is not None:
                payload["text"] = text.strip()
            if not (payload.get("text") or "").strip():
                raise ValueError("Texto vazio")
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
    async def revise(action_id: int, instruction: str, text: Optional[str] = None, angle: Optional[str] = None) -> Optional[dict]:
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
                                            instruction=instruction or (None if (post.get("comment_variants") or {}).get(angle)
                                                                        else "Write the comment in the chosen angle."),
                                            regenerate=bool(instruction), angle=angle)
        if not (item.get("comment_draft") or "").strip():
            raise ValueError("A IA não devolveu um comentário: tente outro pedido")
        payload = {**(action["payload"] or {}), "text": item["comment_draft"], "relevance": item.get("relevance"), "reason": item.get("reason"),
                   "variants": item.get("comment_variants") or {}}
        updated = _one("""UPDATE public.automation_actions SET payload = %s, updated_at = NOW()
                           WHERE id = %s AND status = 'proposed' RETURNING *""", (Json(payload), action_id))
        if updated:
            _rows("INSERT INTO public.automation_events (action_id, source, event, data) VALUES (%s, 'user', 'revised', %s)",
                  (action_id, Json({"instruction": instruction[:500], "angle": angle})))
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
        if action and action["kind"] == "reply":
            _rows("UPDATE public.linkedin_comment_replies SET status = 'skipped', updated_at = NOW() WHERE id = %s", (action["target_id"],))
        if action and action["kind"] == "message":
            _rows("UPDATE public.linkedin_conversations SET status = 'ignored', updated_at = NOW() WHERE id = %s", (action["target_id"],))
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
        """A job the triage discarded, or whose proposal expired, comes back for you to approve."""
        job = _one("""UPDATE public.job_listings SET triage_outcome = 'propose' WHERE id = %s AND status = 'discovered' RETURNING *""", (job_id,))
        if not job:
            return None
        revived = _one("""UPDATE public.automation_actions SET status = 'proposed', error_code = NULL, error_text = NULL, finished_at = NULL,
                                 notified_status = NULL, created_at = NOW(), updated_at = NOW()
                           WHERE idempotency_key = %s AND status = 'expired' RETURNING *""", (f"apply:{job_id}",))
        return revived or AutomationService.propose_job(job)

    @staticmethod
    def propose_job(job: dict) -> Optional[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:   # the same job in another place already has its application (or its proposal)
                twin = _twin_apply(cur, {"id": 0, "kind": "apply", "target_id": job["id"]}, TWIN_APPLY_STATUSES + ("proposed", "approved", "review_docs", "queued"))
        finally:
            conn.close()
        if twin:
            log.info("job %s not proposed: same job as apply #%s (%s)", job["id"], twin["id"], twin.get("location"))
            return None
        # a job read straight from a company site (Greenhouse, Lever...) goes to that form: no LinkedIn page in between
        direct = (job.get("source") or "linkedin") != "linkedin" and job.get("apply_url")
        return AutomationService.create_action(
            "apply", f"apply:{job['id']}", f"{job.get('job_title') or 'Vaga'} · {job.get('company') or ''}",
            job["apply_url"] if direct else job.get("url"),
            {"job_id": job["id"], "linkedin_job_id": job.get("linkedin_job_id"), "title": job.get("job_title"), "company": job.get("company"),
             "source": job.get("source") or "linkedin"},
            target_type="job", target_id=job["id"], rank=0, sort_at=job.get("posted_at") or job.get("created_at"),
            lane="ats" if direct else None)

    # ── Needs you ────────────────────────────────────────────────────────
    @staticmethod
    def needs_user() -> List[dict]:
        return _rows("""SELECT * FROM public.automation_actions WHERE status IN ('needs_user', 'review_docs', 'awaiting_confirm')
                         ORDER BY updated_at DESC LIMIT 200""")

    @staticmethod
    def _upsert_answer(cur, question: str, answer: str, field_type: str = "text") -> None:
        key = question_key(question)
        val = str(answer or "").strip()
        if not key or not val or answer_match.not_an_answer(val):   # "cancele", "arquivar vaga": about one form, not an answer
            return
        cur.execute("""
            INSERT INTO public.automation_answers (question_norm, question, field_type, answer)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (question_norm, field_type) DO UPDATE SET answer = EXCLUDED.answer, updated_at = NOW()""",
                    (key, question[:1000], field_type or "text", val[:2000]))

    @staticmethod
    def save_answer(question: str, answer: str, field_type: str = "text") -> None:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                AutomationService._upsert_answer(cur, question, answer, field_type)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def answer(action_id: int, answers: List[dict]) -> Optional[dict]:
        """Your answers go to the answer bank and the action back to the queue."""
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                for a in answers:
                    if a.get("save", True) and str(a.get("answer") or "").strip():
                        AutomationService._upsert_answer(cur, a["question"], a["answer"], a.get("field_type") or "text")
                cur.execute("""
                    UPDATE public.automation_actions
                       SET status = 'queued', error_code = NULL, error_text = NULL, questions = '[]', claude_attempts = 0,
                           expires_at = NULL, updated_at = NOW()
                     WHERE id = %s AND status = 'needs_user' RETURNING *""", (action_id,))
                # expires_at NULL: 2026-11-22, 6 jobs approved before 12/11 expired a minute after your answers sent them back
                row = cur.fetchone()
                if row:
                    _event(cur, action_id, "user", "answered", {"count": len(answers)})
            conn.commit()
            return dict(row) if row else None
        finally:
            conn.close()

    # ── The operations panel (2026-11-17): what runs now, the last 24 h, the queue, how the agents do ──
    @staticmethod
    def ops() -> dict:
        running = _rows("""
            SELECT a.id, a.kind, a.lane, a.status, a.title, a.target_url, a.executor, a.updated_at,
                   r.started_at AS run_started_at, r.model AS run_model,
                   EXTRACT(EPOCH FROM (NOW() - COALESCE(r.started_at, a.updated_at)))::int AS elapsed_s
              FROM public.automation_actions a
              LEFT JOIN LATERAL (SELECT started_at, model FROM public.automation_runs
                                  WHERE action_id = a.id AND kind = 'claude' AND finished_at IS NULL
                                  ORDER BY id DESC LIMIT 1) r ON a.status = 'running_claude'
             WHERE a.status IN ('running_ext', 'running_claude', 'verifying', 'approved')
             ORDER BY COALESCE(r.started_at, a.updated_at)""")
        hourly = _rows("""
            SELECT to_char(date_trunc('hour', finished_at) AT TIME ZONE 'America/Sao_Paulo', 'HH24') AS hour,
                   COUNT(*) FILTER (WHERE lane = 'ats') AS ats, COUNT(*) FILTER (WHERE lane <> 'ats') AS linkedin
              FROM public.automation_actions
             WHERE kind = 'apply' AND status = 'done' AND finished_at > NOW() - interval '24 hours'
             GROUP BY date_trunc('hour', finished_at) ORDER BY date_trunc('hour', finished_at)""")
        done = _one("""
            SELECT COUNT(*) FILTER (WHERE finished_at > NOW() - interval '24 hours') AS d24,
                   COUNT(*) FILTER (WHERE finished_at > NOW() - interval '1 hour') AS h1,
                   COUNT(*) FILTER (WHERE finished_at >= date_trunc('day', NOW() AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'America/Sao_Paulo') AS today,
                   COUNT(*) FILTER (WHERE finished_at > NOW() - interval '7 days') AS d7
              FROM public.automation_actions WHERE kind = 'apply' AND status = 'done'""") or {}
        queue = {r["status"]: r["n"] for r in _rows("""
            SELECT status, COUNT(*) AS n FROM public.automation_actions
             WHERE kind = 'apply' AND status IN ('proposed', 'approved', 'review_docs', 'queued', 'running_ext', 'escalated',
                                                 'running_claude', 'verifying', 'unknown_outcome', 'awaiting_confirm', 'needs_user')
             GROUP BY status""")}
        outcomes = _rows("""
            SELECT CASE WHEN model LIKE 'hermes%%' THEN 'hermes' WHEN model LIKE 'claude%%' THEN 'claude' ELSE COALESCE(model, '—') END AS agent,
                   COALESCE(result_class, 'em andamento') AS result, COUNT(*) AS n,
                   ROUND(AVG(EXTRACT(EPOCH FROM (finished_at - started_at)))::numeric) AS avg_s
              FROM public.automation_runs
             WHERE kind = 'claude' AND started_at > NOW() - interval '24 hours' AND COALESCE(result_class, '') <> 'deferred'
             GROUP BY 1, 2 ORDER BY 1, 3 DESC""")
        tokens = _rows("""
            SELECT CASE WHEN model LIKE 'hermes%%' THEN 'hermes' WHEN model LIKE 'claude%%' THEN 'claude' ELSE COALESCE(model, '—') END AS agent,
                   SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0) + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0)
                       + COALESCE((summary->'hermes_usage'->>'input_tokens')::bigint, 0) + COALESCE((summary->'hermes_usage'->>'output_tokens')::bigint, 0)) AS tokens
              FROM public.automation_runs WHERE kind = 'claude' AND started_at > NOW() - interval '24 hours' GROUP BY 1""")
        stuck = _rows("""
            SELECT COALESCE(error_code, '—') AS code, COUNT(*) AS n FROM public.automation_actions
             WHERE kind = 'apply' AND status = 'needs_user' GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")
        others = _rows("""
            SELECT kind, COUNT(*) FILTER (WHERE status = 'done' AND finished_at > NOW() - interval '24 hours') AS done_24h,
                   COUNT(*) FILTER (WHERE status IN ('queued', 'escalated', 'running_ext', 'running_claude')) AS waiting
              FROM public.automation_actions WHERE kind IN ('comment', 'reply', 'like', 'follow', 'connect', 'message')
             GROUP BY kind ORDER BY kind""")
        state = AutomationService.state()
        return {"now": now().isoformat(), "running": running, "applies": {**done, "hourly": hourly}, "queue": queue,
                "agent_outcomes": outcomes, "tokens_24h": tokens, "needs_you": stuck, "other_actions": others,
                "engine": AutomationService.ai_engine(),
                "state": {"mode": state.get("mode"), "halted_lanes": state.get("halted_lanes") or [],
                          "claude_paused_until": state.get("claude_paused_until"), "captcha_session_until": state.get("captcha_session_until")}}

    # ── Which engine does each kind of AI work (2026-11-17): Lolo's Hermes (free Nous model), Claude or AGY ──
    AI_ENGINE_DEFAULT = {"agent": "hermes", "documents": "claude", "forms": "claude", "texts": "hermes"}
    AI_ENGINE_CHOICES = {"agent": ("hermes", "auto", "claude"), "documents": ("claude", "hermes"),
                         "forms": ("claude", "hermes"), "texts": ("hermes", "agy")}
    _engine_cache: Dict[str, Any] = {"at": 0.0, "value": None}

    @staticmethod
    def ai_engine(fresh: bool = False) -> Dict[str, str]:
        import time as _t
        cache = AutomationService._engine_cache
        if fresh or cache["value"] is None or _t.time() - cache["at"] > 30:
            try:
                row = _one("SELECT ai_engine FROM public.automation_state WHERE id = 1") or {}
                saved = row.get("ai_engine") or {}
            except Exception:
                saved = {}
            value = {k: (saved.get(k) if saved.get(k) in AutomationService.AI_ENGINE_CHOICES[k] else v)
                     for k, v in AutomationService.AI_ENGINE_DEFAULT.items()}
            cache.update(at=_t.time(), value=value)
        return dict(cache["value"])

    @staticmethod
    def set_ai_engine(changes: Dict[str, str]) -> Dict[str, str]:
        clean = {k: v for k, v in (changes or {}).items() if v in AutomationService.AI_ENGINE_CHOICES.get(k, ())}
        if clean:
            _rows("UPDATE public.automation_state SET ai_engine = ai_engine || %s WHERE id = 1", (Json(clean),))
            AutomationService.add_event_global("ai_engine", clean)
        return AutomationService.ai_engine(fresh=True)

    @staticmethod
    def add_event_global(event: str, data: dict) -> None:
        log.info("automation %s: %s", event, data)

    # ── Live questions (2026-11-16): the apply agent asks, Lolo asks you on WhatsApp, the agent waits with the form open ──
    @staticmethod
    def ask_live(action_id: int, question: str, options: Optional[list] = None, field_type: str = "text") -> dict:
        """{answer} at once when the answer bank has it; else the question goes to you on WhatsApp and {question_id} comes
        back for the agent to wait on. Never at night (quiet hours) and never for an action that is not running."""
        question = (question or "").strip()[:1000]
        if not question:
            return {"answer": None, "unavailable": "empty question"}
        known = AutomationService.known_answer(question, field_type or "text")
        if known:
            return {"answer": known, "source": "saved"}
        # not in other words either: the AI looks for a saved answer to the same question, in any wording or language
        tr = answer_match.translation(question, options)
        try:
            hit = answer_match.ai_match(question, field_type or "text", options, AutomationService.answers_list(),
                                        also=[tr["pt"], tr["en"]] if tr else None)
        except Exception as e:
            log.warning("answer match for #%s failed: %s", action_id, e)
            hit = None
        if hit:
            AutomationService.add_event(action_id, "claude", "answer_reused", {"question": question[:300], **hit})
            return {"answer": hit["answer"], "source": "saved_similar", "saved_question": hit["saved_question"]}
        from app.services.bot_service import BotService
        if BotService.quiet():
            return {"answer": None, "unavailable": "quiet hours: the candidate is not asked at night"}
        action = _one("SELECT id, title, status FROM public.automation_actions WHERE id = %s", (action_id,))
        if not action or action["status"] != "running_claude":
            return {"answer": None, "unavailable": "the action is not running"}
        q = _one("""SELECT * FROM public.automation_live_questions WHERE action_id = %s AND answer IS NULL AND question = %s
                     ORDER BY id DESC LIMIT 1""", (action_id, question))
        if not q:
            opts = [str(o)[:200] for o in (options or [])][:30]
            q = _one("""INSERT INTO public.automation_live_questions (action_id, question, options, field_type)
                        VALUES (%s, %s, %s, %s) RETURNING *""", (action_id, question, Json(opts), (field_type or "text")[:20]))
            listed = ("\nOpções: " + " / ".join(opts)) if opts else ""
            shown = question
            if tr:   # not Portuguese or English: you read it in Portuguese, with the original below
                pairs = [f"{o} ({p})" if p and p != o else o for o, p in zip(opts, tr["options_pt"] + [""] * len(opts))]
                listed = ("\nOpções: " + " / ".join(pairs)) if opts else ""
                shown = f"🌐 {tr['pt']}\n_(original em {tr['lang_name']}: {question})_"
            BotService.notify("question", f"❓ Pergunta da vaga {action.get('title') or f'#{action_id}'} (#{action_id}):\n{shown}{listed}\n"
                              "Responda citando esta mensagem: o formulário está aberto esperando, e a resposta fica salva para as próximas.",
                              {"reply": "live_question", "action_id": action_id, "question_id": q["id"]}, urgent=True, key=f"liveq:{q['id']}")
            AutomationService.add_event(action_id, "claude", "live_question", {"question": question[:300], "question_id": q["id"]})
        AutomationService._hold_lease(action_id)
        return {"answer": None, "question_id": q["id"]}

    @staticmethod
    def _hold_lease(action_id: int) -> None:
        _rows("""UPDATE public.automation_actions SET lease_until = GREATEST(lease_until, NOW() + interval '20 minutes')
                  WHERE id = %s AND status = 'running_claude'""", (action_id,))

    @staticmethod
    def live_answer(question_id: int) -> Optional[dict]:
        q = _one("SELECT id, action_id, answer FROM public.automation_live_questions WHERE id = %s", (question_id,))
        if q and q["answer"] is None:
            AutomationService._hold_lease(q["action_id"])
        return q

    @staticmethod
    def answer_live(question_id: int, answer: str) -> Optional[dict]:
        """Your answer: to the waiting agent, and to the answer bank for good. If the agent gave up waiting meanwhile, the
        action is waiting for you: the answer also sends it back to the queue."""
        answer = (answer or "").strip()[:3000]
        q = _one("""UPDATE public.automation_live_questions SET answer = %s, answered_at = NOW()
                     WHERE id = %s AND answer IS NULL RETURNING *""", (answer, question_id)) if answer else None
        if not q:
            return None
        AutomationService.save_answer(q["question"], answer, q.get("field_type") or "text")
        AutomationService.add_event(q["action_id"], "user", "live_answer", {"question_id": question_id})
        if (_one("SELECT status FROM public.automation_actions WHERE id = %s", (q["action_id"],)) or {}).get("status") == "needs_user":
            AutomationService.answer(q["action_id"], [{"question": q["question"], "answer": answer, "save": False}])
        return q

    @staticmethod
    def open_live_questions() -> List[dict]:
        return _rows("""SELECT q.id, q.action_id, q.question, q.options, a.title FROM public.automation_live_questions q
                          JOIN public.automation_actions a ON a.id = q.action_id
                         WHERE q.answer IS NULL AND q.asked_at > NOW() - interval '1 day' ORDER BY q.id""")

    @staticmethod
    def known_answer(label: str, field_type: str) -> Optional[str]:
        """The answer you already gave to this question in another form (exact type first, then any compatible type)."""
        key = question_key(label)
        if not key:
            return None
        row = _one("SELECT answer FROM public.automation_answers WHERE question_norm = %s AND field_type = %s",
                   (key, field_type))
        if row:
            return row["answer"]
        row = _one("SELECT answer FROM public.automation_answers WHERE question_norm = %s ORDER BY updated_at DESC LIMIT 1",
                   (key,))
        if row:
            return row["answer"]
        return AutomationService.topic_answer(label) or AutomationService._loose_answer(label, field_type)

    @staticmethod
    def topic_answer(label: str) -> Optional[str]:
        """The newest saved answer about the same personal fact (date of birth, race, German level), in any wording or
        language: answer_match.topic."""
        hit = AutomationService._topic_hit(label)
        return hit["answer"] if hit else None

    @staticmethod
    def _topic_hit(label: str) -> Optional[dict]:
        name = answer_match.topic(label)
        if not name:
            return None
        for a in AutomationService.answers_list():   # newest first
            if not answer_match.not_an_answer(a.get("answer") or "") and answer_match.topic(a["question"]) == name:
                return a
        return None

    @staticmethod
    def _loose_answer(label: str, field_type: str) -> Optional[str]:
        """Same question in other words (2026-11-19): without the agent's context around it, a field label it quoted, or the
        same content words in any order. Same field type first. Never an instruction saved as an answer."""
        mine = answer_match.keys_of(label)
        hits = []
        for a in AutomationService.answers_list():
            if answer_match.not_an_answer(a.get("answer") or ""):
                continue
            theirs = answer_match.keys_of(a["question"])
            if set(mine) & set(theirs) or any(answer_match.same_words(m, t) for m in mine for t in theirs):
                hits.append(a)
        if not hits:
            return None
        same_type = [a for a in hits if a.get("field_type") == field_type]
        return (same_type or hits)[0]["answer"]

    STOPWORDS = {"the", "a", "an", "do", "you", "your", "are", "is", "of", "in", "to", "for", "and", "or", "have", "what", "how",
                 "this", "with", "be", "will", "can", "o", "a", "de", "da", "do", "voce", "e", "em", "para", "qual", "que"}

    @staticmethod
    def lookup_answers(question: str, limit: int = 3) -> dict:
        """For the Claude routine (token plan, phase 1): the saved answers closest to one question, instead of the whole
        answer bank in every prompt, plus what the deterministic mapper would answer."""
        words = {w for w in question_key(question).split() if w not in AutomationService.STOPWORDS and len(w) > 1}
        scored = []
        for a in AutomationService.answers_list():
            other = {w for w in (a.get("question_norm") or question_key(a["question"])).split()
                     if w not in AutomationService.STOPWORDS and len(w) > 1}
            if not words or not other:
                continue
            score = len(words & other) / len(words | other)
            if score >= 0.34:
                scored.append((score, a))
        scored.sort(key=lambda x: -x[0])
        hit = AutomationService._topic_hit(question)   # same personal fact in other words or another language
        if hit:
            scored = [(1.0, hit)] + [(sc, a) for sc, a in scored if a.get("id") != hit.get("id")]
        mapped = None
        try:
            from app.services.form_mapper import FormMapper
            from app.services.linkedin_copilot_service import LinkedInCopilotService
            mapped = FormMapper(LinkedInCopilotService._facts()).answer({"key": "q", "label": question, "type": "text"})
        except Exception as e:
            log.warning("lookup mapper failed: %s", e)
        return {"mapped": mapped, "saved": [{"question": a["question"], "answer": a["answer"], "score": round(sc, 2)}
                                            for sc, a in scored[:limit]]}

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
        elif action["error_code"] == "verify_failed":
            # the page was looked at twice and showed nothing, and you were told to check before repeating: "de novo" sends it
            # again for real; re-checking once more would only bring the same message back (2026-11-05: invites marked as
            # sent by the old flow that never left looped this way)
            status = "queued"
            _rows("""UPDATE public.automation_actions SET result = jsonb_build_object('previous', result) WHERE id = %s""", (action_id,))
        else:
            status = "unknown_outcome" if (action["result"] or {}).get("executed") else "queued"
        # you asked for it again: it does not wait for the time window, which only holds back the automations. The event
        # also tells the Claude gate that something changed (a new run is allowed)
        AutomationService.add_event(action_id, "user", "retry", {})
        # and a CAPTCHA you sent back gets its site tried again: the site block from earlier failures would otherwise send it
        # straight back to you without a run (2026-11-20: Cravath, Bowman and adesso, retried for the new solver)
        from app.services.site_service import SiteService
        if action["error_code"] == "captcha" or SiteService.block_kind(action.get("error_text") or ""):
            SiteService.clear_block(action.get("target_url") or "")
        # asking again also gives the Claude routine a new attempt: escalate() hands a form to it only while claude_attempts < 1,
        # so without this a retried form came straight back to you (2026-11-16: 18 items in a row)
        # and it no longer expires: the approval window was for your first OK, not for a retry you asked for now (2026-11-19:
        # 42 of 91 retried CAPTCHA items, approved over a week ago, expired a minute after going back to the queue)
        return _one("""UPDATE public.automation_actions SET status = %s, error_code = NULL, error_text = NULL, questions = '[]', run_now = TRUE,
                        claude_attempts = 0, expires_at = NULL, updated_at = NOW() WHERE id = %s RETURNING *""", (status, action_id))

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
        return window.get("start_hour", 8) <= _local().hour < window.get("end_hour", 23)

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
                # outside the window only what you asked for goes: approved, retried or "executar agora"; the automations wait
                only_now = not AutomationService.in_window()
                if not refusal and only_now:
                    cur.execute("""SELECT 1 FROM public.automation_actions WHERE lane = %s AND (run_now OR approved_at IS NOT NULL OR kind = ANY(%s))
                                     AND status IN ('queued', 'unknown_outcome') LIMIT 1""", (lane, list(ANYTIME_KINDS)))
                    if not cur.fetchone():
                        refusal = "outside_window"
                live = AutomationService.captcha_session_active(state)
                if not refusal and live:
                    # the live CAPTCHA session: only those actions, one at a time, in the company-site browser you watch
                    if lane != "ats":
                        refusal = "captcha_session"
                    else:
                        cur.execute("""SELECT 1 FROM public.automation_actions WHERE status IN ('running_ext', 'running_claude', 'verifying')
                                         AND (result->>'live_captcha')::boolean IS TRUE LIMIT 1""")
                        if cur.fetchone():
                            refusal = "captcha_session_busy"
                if refusal:
                    conn.commit()
                    return {"action": None, "reason": refusal}
                limits = AutomationService.limits(state)
                exhausted = [l["kind"] for l in limits if l["left"] <= 0]   # holds back only the automations
                paused = ["connect"] if state["invites_paused_until"] and state["invites_paused_until"] > now() else []   # holds back all
                # a check that never gives a verdict (the worker hung or lost the browser) would hold the lane forever: after
                # VERIFY_TRIES checks with no answer it is yours, "confira antes de repetir" (2026-11-19: one action was
                # re-checked ~35 times in 8 h while 28 applications waited behind it)
                cur.execute("""
                    UPDATE public.automation_actions a
                       SET status = 'needs_user', error_code = 'verify_failed', lease_owner = NULL, lease_until = NULL, updated_at = NOW(),
                           error_text = 'Tentei conferir várias vezes se foi enviado e a verificação não respondeu: confira na página antes de repetir'
                     WHERE a.lane = %s AND a.status = 'unknown_outcome'
                       AND (SELECT COUNT(*) FROM public.automation_events e
                             WHERE e.action_id = a.id AND e.event = 'claimed' AND (e.data->>'verify_only')::boolean IS TRUE
                               AND e.at > COALESCE((SELECT MAX(v.at) FROM public.automation_events v
                                                     WHERE v.action_id = a.id AND v.event IN ('verified', 'retry')), '-infinity')) >= %s""",
                            (lane, VERIFY_TRIES))
                # what may already have gone out is looked at first: it does not count as a new action
                cur.execute("""
                    SELECT * FROM public.automation_actions
                     WHERE lane = %s AND status = 'unknown_outcome' AND (scheduled_for IS NULL OR scheduled_for <= NOW()) AND (run_now OR approved_at IS NOT NULL OR NOT %s)
                     ORDER BY updated_at LIMIT 1 FOR UPDATE SKIP LOCKED""", (lane, only_now))
                row = cur.fetchone()
                verify_only = bool(row)
                if not row:
                    cur.execute("""
                        SELECT * FROM public.automation_actions
                         WHERE lane = %s AND status = 'queued' AND NOT (kind = ANY(%s))
                           AND (run_now OR approved_at IS NOT NULL OR NOT (kind = ANY(%s)))
                           AND (scheduled_for IS NULL OR scheduled_for <= NOW()) AND (expires_at IS NULL OR expires_at > NOW())
                           AND (run_now OR approved_at IS NOT NULL OR kind = ANY(%s) OR NOT %s)
                           AND (NOT %s OR (result->>'live_captcha')::boolean IS TRUE)
                         ORDER BY run_now DESC, rank, sort_at DESC LIMIT 1 FOR UPDATE SKIP LOCKED""", (lane, paused, exhausted, list(ANYTIME_KINDS), only_now, live))
                    row = cur.fetchone()
                if not row:
                    conn.commit()
                    return {"action": None, "reason": "empty"}
                action = dict(row)
                twin = _twin_apply(cur, action) if not verify_only else None
                if twin:
                    cur.execute("""UPDATE public.automation_actions SET status = 'discarded', error_code = 'duplicate', finished_at = NOW(),
                                          error_text = %s, lease_owner = NULL, updated_at = NOW() WHERE id = %s""",
                                (f"Mesma vaga em outro local: a candidatura #{twin['id']} ({twin['status']}) já cuida dela", action["id"]))
                    _event(cur, action["id"], "backend", "duplicate_job", {"twin": twin["id"]})
                    conn.commit()
                    return {"action": None, "reason": "duplicate"}
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
                    auto_cfg = config().get("automation") or {}
                    # applications have their own, shorter gap (2026-11-19, you asked for ~20 an hour); comments, invites and
                    # messages keep the long one
                    low, high = (auto_cfg.get("apply_gap_minutes") if action["kind"] == "apply" else None) \
                        or auto_cfg.get("write_gap_minutes") or [5, 20]
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
                "live_captcha": bool((action["result"] or {}).get("live_captcha")),
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
        if event == "captcha_waiting":   # live session: tell you on WhatsApp which job is on the noVNC screen now
            try:
                from app.services.bot_service import BotService
                a = _one("SELECT title FROM public.automation_actions WHERE id = %s", (action_id,)) or {}
                BotService.notify("captcha", f"🧩 CAPTCHA esperando você no noVNC: {a.get('title') or f'ação #{action_id}'}\n"
                                  f"{settings.CAREEROPS_NOVNC_URL or ''}\nResolva o desafio; o resto o sistema faz.",
                                  {"action_id": action_id}, urgent=True, key=f"captcha:{action_id}:{now().strftime('%Y%m%d%H')}")
            except Exception as e:
                log.warning("captcha notice failed: %s", e)

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
    def confirm_by_email(job_id: int, event_id: Optional[int], subject: str = "", domain: str = "") -> Optional[dict]:
        """The company's "we received your application" e-mail proves an apply the page could not: the action is done and
        the job applied. Only an action whose final click happened (never a send that did not go out)."""
        action = _one("""SELECT * FROM public.automation_actions WHERE kind = 'apply' AND target_id = %s
                           AND (status IN ('unknown_outcome', 'verifying') OR (status = 'needs_user' AND error_code = 'verify_failed'))
                         ORDER BY updated_at DESC LIMIT 1""", (job_id,))
        if not action:
            return None
        AutomationService.add_event(action["id"], "email", "verified", {"proof": True, "by": "email", "event_id": event_id,
                                                                        "subject": (subject or "")[:200], "domain": domain})
        if action["lane"] == "ats":
            from app.services.site_service import SiteService
            SiteService.count_success(action.get("target_url") or "")
        return AutomationService._finish(action, {"proof": "email", "email_event_id": event_id}, "email")

    @staticmethod
    def reopen_by_email(job_id: int, event_id: Optional[int], summary: str = "", link: str = "") -> dict:
        """The company writes that the application was started and not sent ("Continue to apply…", "finish your draft"):
        the apply goes back to the apply agent, which continues the form (from the e-mail's link when it is on the same
        site). Twice at most per action: a third reminder means the agent cannot finish it, and it stays with you.
        Returns {"outcome": "reopened"|"running"|"to_user"|"no_action", "action_id", "link"}."""
        action = _one("""SELECT * FROM public.automation_actions WHERE kind = 'apply' AND target_id = %s
                          ORDER BY updated_at DESC LIMIT 1""", (job_id,))
        if not action:
            return {"outcome": "no_action"}
        aid = action["id"]
        if action["status"] in ("queued", "escalated", "running_ext", "running_claude", "verifying", "approved", "review_docs"):
            AutomationService.add_event(aid, "email", "incomplete_email", {"event_id": event_id, "while": action["status"]})
            return {"outcome": "running", "action_id": aid}
        if action["status"] not in ("done", "unknown_outcome", "needs_user", "discarded"):
            return {"outcome": "no_action", "action_id": aid}
        tries = (_one("""SELECT COUNT(*) AS n FROM public.automation_events WHERE action_id = %s AND event = 'incomplete_email'
                           AND data->>'reopened' = 'true'""", (aid,)) or {}).get("n") or 0
        if link and not _same_site_link(link, action):
            link = ""
        text = (f"E-mail da empresa: a candidatura NÃO foi concluída ({(summary or '')[:200]}). Continue o formulário até o envio final"
                + (f"; abra primeiro o link do e-mail: {link}" if link else "; abra a página da vaga e entre na conta do portal se pedir") + ".")
        if tries >= 2:
            AutomationService.add_event(aid, "email", "incomplete_email", {"event_id": event_id, "reopened": False})
            AutomationService._to_user(aid, "incomplete_by_email", "A empresa avisou de novo que a candidatura não foi concluída, "
                                       "e o agente já tentou 2 vezes: termine pelo link do e-mail." + (f" {link}" if link else ""))
            return {"outcome": "to_user", "action_id": aid, "link": link}
        AutomationService.add_event(aid, "email", "incomplete_email", {"event_id": event_id, "reopened": True, "link": link,
                                                                       "was": action["status"]})
        _rows("""UPDATE public.automation_actions
                    SET status = 'escalated', error_code = 'incomplete_by_email', error_text = %s, questions = '[]', run_now = TRUE,
                        claude_attempts = 0, last_run_fingerprint = NULL, scheduled_for = NULL, lease_owner = NULL, lease_until = NULL,
                        finished_at = NULL, result = COALESCE(result, '{}'::jsonb) || jsonb_build_object('incomplete_email', %s::int),
                        updated_at = NOW()
                  WHERE id = %s""", (text, event_id or 0, aid))
        if action["status"] == "done":   # it was counted as sent: it is not, until the agent finishes it
            _rows("""UPDATE public.job_listings SET status = 'new', applied_at = NULL, updated_at = NOW()
                      WHERE id = %s AND status = 'applied'""", (job_id,))
        return {"outcome": "reopened", "action_id": aid, "link": link}

    @staticmethod
    def verify(action_id: int, proof: bool, evidence: Optional[dict] = None) -> Optional[dict]:
        """The page was looked at. Without proof a write that is known to have been clicked is never tried again."""
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s AND status = ANY(%s)", (action_id, list(RUNNING) + ["unknown_outcome"]))
        if not action:
            return None
        AutomationService.add_event(action_id, "worker", "verified", {"proof": proof, **(evidence or {})})
        if proof and action["kind"] == "apply" and action["lane"] == "ats":   # the site is passable: recipes and site memory learn it
            from app.services.site_service import SiteService
            SiteService.count_success((evidence or {}).get("url") or action.get("target_url") or "")
        if proof:
            return AutomationService._finish(action, {"proof": evidence or True}, "worker")
        result = action["result"] or {}
        if action["kind"] == "connect" and (evidence or {}).get("not_sent"):
            # the worker reloaded the profile, read the sent list, and Connect is still offered: nothing went out (2026-11-05:
            # Gavin Nicholls, Gottfried Schmidtke). Not a "check before repeating" for you: the Claude routine sends it
            _rows("UPDATE public.automation_actions SET result = jsonb_build_object('previous', result) WHERE id = %s", (action_id,))
            return AutomationService.escalate(action_id, "unexpected_layout", "O convite não saiu (o perfil ainda oferece Conectar)", source="worker",
                                              screenshot=(evidence or {}).get("screenshot"))
        if result.get("executed"):
            if not result.get("recheck"):   # LinkedIn may take a moment: one more look before asking you
                return _one("""UPDATE public.automation_actions
                                  SET status = 'unknown_outcome', scheduled_for = NOW() + INTERVAL '5 minutes',
                                      result = result || '{"recheck": true}'::jsonb, updated_at = NOW()
                                WHERE id = %s RETURNING *""", (action_id,))
            return AutomationService._to_user(action_id, "verify_failed", "Cliquei para enviar, mas a página não mostra que foi feito: confira no LinkedIn antes de repetir")
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
        if not CAPTCHA_RE.search(f"{code} {text}") and CLOSED_JOB_RE.search(text or ""):
            return AutomationService._discard(action, "job_closed", text)
        lanes = (config().get("claude") or {}).get("lanes") or []
        ats_auth_code = action["lane"] == "ats" and code in ("account_required", "email_verification")
        if (code in CLAUDE_CODES or ats_auth_code) and action["claude_attempts"] < 1 and action["lane"] in lanes:
            return _one("""UPDATE public.automation_actions SET status = 'escalated', error_code = %s, error_text = %s, lease_owner = NULL, updated_at = NOW()
                            WHERE id = %s RETURNING *""", (code, text, action_id))
        resolved = AutomationService._resolve_before_user(action, code, text, questions, source=source)
        if resolved is not None:
            return resolved
        return AutomationService._to_user(action_id, code, text, questions)

    @staticmethod
    def _extract_questions(questions: Optional[list], text: str) -> List[str]:
        out: List[str] = []
        for item in questions or []:
            label = (item.get("label") or item.get("question") or "") if isinstance(item, dict) else str(item or "")
            label = label.strip()
            if label and label not in out:
                out.append(label[:500])
        if not out and text and len(text.strip()) >= 15:
            low = text.lower()
            if any(tok in low for tok in ("question", "pergunta", "required field", "campo obrigat", "missing field", "precisa preencher")):
                out.append(text.strip()[:800])
        return out

    @staticmethod
    def _ai_answer_questions(action: dict, questions: List[str], error_text: str) -> tuple[bool, Dict[str, str]]:
        # an identity check (ID document, selfie, biometric consent) is yours alone: 2026-11-22, Aligned Labs' Persona step got
        # "Yes" from the consent rule and went back to the agent twice
        if IDENTITY_CHECK_RE.search(" ".join([error_text or ""] + [json.dumps(q, ensure_ascii=False, default=str) for q in (questions or [])])):
            return False, {}
        qs = AutomationService._extract_questions(questions, error_text)
        # no real question list: the fallback is the agent's whole summary, not a form question. Answering it by keyword and saving
        # the pair filled the answer bank with junk ("Yes" to a paragraph) on 2026-11-15
        if not qs or any(len(q) > 300 for q in qs):
            return False, {}
        resolved: Dict[str, str] = {}
        pending: List[str] = []
        for q in qs:
            ans = _deterministic_answer(q) or AutomationService.known_answer(q, "text")
            if ans:
                resolved[q] = ans
            else:
                pending.append(q)
        if pending:
            try:
                from app.services.ai_service import AIService
                from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot
                job = _one("SELECT job_title, company, location, resume_markdown FROM public.job_listings WHERE id = %s",
                           (action.get("target_id"),)) or {}
                facts = Copilot._facts()
                saved = [{"question": a["question"], "answer": a["answer"]} for a in AutomationService.answers_list()[:40]]
                prompt = (
                    "You help submit a job application using ONLY real facts about the candidate.\n"
                    f"Job: {job.get('job_title')} at {job.get('company')} ({job.get('location')})\n"
                    f"Candidate Facts JSON: {json.dumps(facts, ensure_ascii=False, default=str)[:3000]}\n"
                    f"Saved Answers JSON: {json.dumps(saved, ensure_ascii=False, default=str)[:2500]}\n"
                    f"Resume Excerpt: {(job.get('resume_markdown') or '')[:3000]}\n"
                    f"Questions to answer JSON: {json.dumps(pending, ensure_ascii=False)}\n"
                    "Rules: Answer ONLY what can be truthfully derived from the facts, resume, or standard job-application conventions "
                    "for this candidate (lives in Florianopolis, Brazil; graduated Bachelor in Mechanical Engineering at UFSC in 12/2011; "
                    "not US/EU/UK citizen; requires visa sponsorship outside Brazil; fluent Portuguese & English; CNH / driver's license Yes; "
                    "notice period 3 weeks / 21 days; open to hybrid & remote). NEVER invent skills, licenses, or years the candidate does not have. "
                    "If ANY question requires personal judgment, asks for an NDA/non-compete agreement, or has an impossible country/residency requirement, "
                    'set "can_answer": false.\n'
                    'Return JSON: {"can_answer": true|false, "answers": [{"question": "...", "answer": "..."}]}'
                )
                ai_res = AIService.get_provider("default").generate_json(prompt, temperature=0.1)
                if isinstance(ai_res, dict) and ai_res.get("can_answer"):
                    for item in ai_res.get("answers") or []:
                        if isinstance(item, dict) and str(item.get("question") or "").strip() and str(item.get("answer") or "").strip():
                            resolved[str(item["question"]).strip()] = str(item["answer"]).strip()
            except Exception as e:
                log.warning("AI question triage failed for action #%s: %s", action.get("id"), e)
        if any(q not in resolved for q in qs):
            return False, resolved
        for q, ans in resolved.items():
            AutomationService.save_answer(q, ans, "text")
        return True, resolved

    @staticmethod
    def _reschedule_retry(action_id: int, status: str, delay_secs: int, error_code: str, error_text: str) -> Optional[dict]:
        return _one("""
            UPDATE public.automation_actions
               SET status = %s,
                   scheduled_for = NOW() + make_interval(secs => %s),
                   lease_owner = NULL,
                   lease_until = NULL,
                   error_code = %s,
                   error_text = %s,
                   updated_at = NOW()
             WHERE id = %s RETURNING *""", (status, delay_secs, error_code, (error_text or "")[:500], action_id))

    @staticmethod
    def _resolve_before_user(action: dict, code: str, text: str, questions: Optional[list] = None,
                             source: str = "worker") -> Optional[dict]:
        """Deterministic + AI triage before escalating to needs_user."""
        combined = f"{code or ''} {text or ''}"
        if code == "captcha" or CAPTCHA_RE.search(combined) or re.search(r"\b2fa\b|\bsms\b.*code|phone verification", combined, re.I):
            return None
        if CLOSED_JOB_RE.search(text or ""):
            return AutomationService._discard(action, "job_closed", text)
        claude_lanes = set((config().get("claude") or {}).get("lanes") or [])
        retry_status = "escalated" if action.get("lane") in claude_lanes else "queued"
        if action.get("kind") in READ_KINDS or action.get("lane") == "linkedin_read":
            if action.get("attempts", 0) < 2:
                AutomationService.add_event(action["id"], "triage", "auto_retry_read", {"source": source})
                return AutomationService._reschedule_retry(action["id"], "queued", 600, "auto_retry", text)
            return AutomationService._discard(action, "superseded", text)

        if (
            action.get("kind") == "apply"
            and action.get("lane") == "linkedin_write"
            and (config().get("jobs") or {}).get("external_apply")
            and (code == "external_manual" or "candidatura no site" in (text or "").lower())
        ):
            urls = URL_EXTRACT_RE.findall(text or "")
            ext_url = next((u for u in urls if "linkedin.com" not in u.lower()), "") or str(action.get("target_url") or "")
            if ext_url:
                AutomationService.add_event(action["id"], "triage", "auto_handoff", {"url": ext_url})
                return _one("""UPDATE public.automation_actions
                                  SET lane = 'ats', target_url = %s, status = 'queued', error_code = NULL, error_text = NULL,
                                      scheduled_for = NOW(), lease_owner = NULL, lease_until = NULL, updated_at = NOW()
                                WHERE id = %s RETURNING *""", (ext_url, action["id"]))

        if QUOTA_RE.search(text or "") and action.get("claude_attempts", 0) < 5:
            m = RESET_IN_RE.search(text or "")
            delay_secs = max(120, (int(m.group(1) or 0) * 3600) + (int(m.group(2) or 0) * 60) + 60) if m and (m.group(1) or m.group(2)) else 1800
            from app.services.bot_service import BotService
            BotService.notify(
                "summary",
                "⏳ *CareerOps*: Cota temporária do modelo de IA atingida (502). O fallback multi-modelo foi acionado e "
                "as vagas represadas foram reagendadas automaticamente para retomar quando a cota renovar.",
                urgent=False,
                key=f"quota_retry:{_local().strftime('%Y-%m-%d-%H')}",
            )
            AutomationService.add_event(action["id"], "triage", "auto_retry_quota", {"delay_secs": delay_secs})
            return AutomationService._reschedule_retry(action["id"], retry_status, delay_secs, "auto_retry", text)

        if TRANSIENT_RE.search(text or "") and action.get("claude_attempts", 0) < 4 and action.get("attempts", 0) < 6:
            AutomationService.add_event(action["id"], "triage", "auto_retry_transient", {"source": source})
            return AutomationService._reschedule_retry(action["id"], retry_status, 300, "auto_retry", text)

        if action.get("lane") == "ats" and ATS_AUTH_RETRY_RE.search(text or "") and action.get("claude_attempts", 0) < 3:
            AutomationService.add_event(action["id"], "triage", "ats_auth_retry", {})
            return AutomationService._reschedule_retry(action["id"], "escalated", 60, "ats_auth_retry", text)

        if (
            action.get("kind") == "apply"
            and (code in ("unknown_required_question", "step_stuck", "claude_stopped") or bool(questions))
            and action.get("attempts", 0) < 6
            and action.get("claude_attempts", 0) < 4
        ):
            ok, resolved = AutomationService._ai_answer_questions(action, questions or [], text or "")
            if ok:
                target_status = "escalated" if (action.get("lane") in claude_lanes and (source == "claude" or code == "claude_stopped" or action.get("lane") == "ats")) else "queued"
                AutomationService.add_event(action["id"], "triage", "auto_answered", {"count": len(resolved)})
                return _one("""UPDATE public.automation_actions
                                  SET status = %s, scheduled_for = NOW() + INTERVAL '15 seconds', lease_owner = NULL, lease_until = NULL,
                                      error_code = 'auto_answered', error_text = NULL, questions = '[]', updated_at = NOW()
                                WHERE id = %s RETURNING *""", (target_status, action["id"]))
        return None

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
        if action["kind"] in SCAN_KINDS and not data.get("dry_run"):
            # a later scan of the same kind read the page: the older ones stuck on you have nothing left to do
            _rows("""UPDATE public.automation_actions SET status = 'discarded', error_code = 'superseded',
                         error_text = 'Uma leitura mais nova do mesmo tipo terminou bem', finished_at = NOW(), lease_owner = NULL, updated_at = NOW()
                     WHERE kind = %s AND status = 'needs_user' AND id <> %s AND created_at < %s""", (action["kind"], action["id"], action["created_at"]))
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
        elif kind in ("reply", "like"):
            from app.services.linkedin_inbox_service import InboxService
            InboxService.reply_done(action)
        elif kind == "message":
            from app.services.linkedin_inbox_service import InboxService
            InboxService.message_sent(action)

    @staticmethod
    def abort(action_id: int, reason: str = "stopped", retry_after: int = 0) -> Optional[dict]:
        """The worker closed the window (you stopped it, it is shutting down, no browser). Nothing is assumed about what happened."""
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s AND status = ANY(%s)", (action_id, list(RUNNING)))
        if not action:
            return None
        AutomationService.add_event(action_id, "worker", "aborted", {"reason": reason}, level="warning")
        status = "unknown_outcome" if action["kind"] in WRITE_KINDS else "queued"
        if reason == "no browser" and action["status"] == "running_ext" and not (action["result"] or {}).get("executed"):
            # no window ever opened: nothing can have gone out, so it is a new attempt, not one more check (2026-11-19:
            # these piled up as "unknown" and the LinkedIn lane spent the day re-checking them)
            status = "queued"
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

    # ── Live CAPTCHA session: you solve the challenge in noVNC, the system does the rest ──
    @staticmethod
    def captcha_session_active(state: Optional[dict] = None) -> bool:
        state = state or AutomationService.state()
        until = state.get("captcha_session_until")
        return bool(until and until > now())

    @staticmethod
    def _is_captcha_item(action: dict) -> bool:
        from app.services.site_service import SiteService
        return action.get("error_code") == "captcha" or bool(SiteService.block_kind(action.get("error_text") or ""))

    @staticmethod
    def captcha_session_start(minutes: int = 60) -> dict:
        """Puts every apply stuck on a CAPTCHA back in the queue, marked live, and for `minutes` only those run (one at a
        time): the worker opens each one in the browser you watch in noVNC and waits for you to solve the challenge."""
        minutes = max(10, min(int(minutes or 60), 240))
        items = [a for a in _rows("""SELECT * FROM public.automation_actions WHERE kind = 'apply' AND status = 'needs_user'
                                     ORDER BY rank, sort_at DESC""") if AutomationService._is_captcha_item(a)]
        for a in items:
            _rows("""UPDATE public.automation_actions SET status = 'queued', lane = 'ats', error_code = NULL, error_text = NULL, questions = '[]',
                            run_now = TRUE, last_run_fingerprint = NULL, result = result || '{"live_captcha": true}'::jsonb, updated_at = NOW()
                      WHERE id = %s""", (a["id"],))
            AutomationService.add_event(a["id"], "user", "captcha_session", {"minutes": minutes})
        _rows("UPDATE public.automation_state SET captcha_session_until = NOW() + make_interval(mins => %s) WHERE id = 1", (minutes,))
        return {"queued": len(items), "minutes": minutes, "ids": [a["id"] for a in items]}

    @staticmethod
    def captcha_session_stop() -> dict:
        """Ends the session: what is still waiting goes back to you, as it was."""
        _rows("UPDATE public.automation_state SET captcha_session_until = NULL WHERE id = 1")
        back = _rows("""UPDATE public.automation_actions SET status = 'needs_user', error_code = 'captcha',
                               error_text = 'Sessão de CAPTCHA encerrada antes desta vaga', run_now = FALSE, updated_at = NOW()
                         WHERE status IN ('queued', 'escalated') AND (result->>'live_captcha')::boolean IS TRUE RETURNING id""")
        _rows("UPDATE public.automation_actions SET result = result - 'live_captcha' WHERE (result->>'live_captcha')::boolean IS TRUE AND status <> 'running_ext' AND status <> 'running_claude'")
        return {"returned": len(back)}

    # ── Token plan, phase 0: what is checked before a Claude run is spent ──
    ENGINE_VERSION = "2026-11-16"   # bump when the engine changes in a way that makes a failed run worth trying again

    @staticmethod
    def _url_key(url: str) -> str:
        """The same job page under different tracking parameters is one page."""
        p = urlparse(url or "")
        return f"{(p.hostname or '').lower()}{p.path.rstrip('/')}"

    @staticmethod
    def _run_fingerprint(cur, action: dict) -> str:
        """What a new run could see differently: the engine, your answers, your actions on this item, the site account."""
        cur.execute("SELECT COALESCE(MAX(updated_at)::text, '') AS t, COUNT(*) AS n FROM public.automation_answers")
        answers = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS n FROM public.automation_events WHERE action_id = %s AND source = 'user'", (action["id"],))
        yours = cur.fetchone()["n"]
        host = (urlparse(action.get("target_url") or "").hostname or "").lower()
        cur.execute("SELECT COALESCE(MAX(updated_at)::text, '') AS t FROM public.automation_site_accounts WHERE %s LIKE '%%' || domain", (host,))
        account = cur.fetchone()["t"]
        confirmed = bool((action.get("result") or {}).get("confirmed"))
        raw = f"{AutomationService.ENGINE_VERSION}|{answers['t']}|{answers['n']}|{yours}|{account}|{confirmed}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _claude_gate(cur, action: dict, cfg: dict, fingerprint: str) -> Optional[tuple]:
        """(code, text, discard) when a run would be spent for nothing; None to run it."""
        budget = int(cfg.get("max_tokens_per_action") or 1_500_000)
        if int(action.get("tokens_spent") or 0) >= budget:
            return ("token_budget", f"Esta ação já usou {int(action['tokens_spent']):,} tokens (teto {budget:,}): fica com você.", False)
        from app.services.site_service import SiteService
        block = SiteService.human_block(action.get("target_url") or "") if not (action.get("result") or {}).get("live_captcha") else None
        if block:
            return ("captcha", "Este site pediu CAPTCHA e o solver automático não passou nas últimas tentativas: resolva pelo noVNC e use Tentar de novo.", False)
        twin = _twin_apply(cur, action)
        if twin:
            return ("duplicate", f"Mesma vaga em outro local: a candidatura #{twin['id']} ({twin['status']}) já cuida dela.", True)
        key = AutomationService._url_key(action.get("target_url") or "")
        if key:
            cur.execute("""SELECT id, status, target_url FROM public.automation_actions
                            WHERE id <> %s AND kind = %s AND status = ANY(%s) ORDER BY updated_at DESC LIMIT 50""",
                        (action["id"], action["kind"], ["running_ext", "running_claude", "verifying", "unknown_outcome", "done", "needs_user"]))
            for other in cur.fetchall():
                if AutomationService._url_key(other["target_url"]) != key:
                    continue
                if other["status"] == "needs_user":
                    return ("duplicate", f"Mesma página da ação #{other['id']}, que já está com você.", False)
                return ("duplicate", f"Mesma página da ação #{other['id']} ({other['status']}).", True)
        if action.get("last_run_fingerprint") and action["last_run_fingerprint"] == fingerprint and int(action.get("claude_attempts") or 0) > 0:
            return ("no_change", "Nada mudou desde a última tentativa do Claude (sem resposta nova, sem conta nova, mesma versão): fica com você.", False)
        return None

    # ── Claude fallback ──────────────────────────────────────────────────
    @staticmethod
    def claude_claim(runner: str, hermes: bool = False, lanes: Optional[List[str]] = None) -> dict:
        """The next stuck action for the routine on the host, or why there is none. One attempt per action.
        `hermes`: the runner has Lolo's Hermes (a free model). While the breaker pauses Claude, it still gets company forms,
        marked claude_paused: Hermes alone works them, and what it does not finish waits for Claude (status "deferred")."""
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
                only_now = not AutomationService.in_window()   # outside the window, only what you approved or asked for
                halted = state["halted_lanes"] or []
                wanted = lanes
                lanes = [l for l in (cfg.get("lanes") or []) if "all" not in halted and l not in halted and (not wanted or l in wanted)]
                claude_paused = bool(state.get("claude_paused_until") and state["claude_paused_until"] > now())
                if claude_paused and not hermes:
                    conn.commit()
                    return {"action": None, "reason": "breaker"}
                if claude_paused:
                    lanes = [l for l in lanes if l == "ats"]
                live = AutomationService.captcha_session_active(state)
                cur.execute("""SELECT * FROM public.automation_actions
                                WHERE status = 'escalated' AND lane = ANY(%s)
                                  AND (scheduled_for IS NULL OR scheduled_for <= NOW())
                                  AND (run_now OR approved_at IS NOT NULL OR NOT %s)
                                  AND (NOT %s OR (result->>'live_captcha')::boolean IS TRUE)
                                ORDER BY rank, sort_at DESC LIMIT 20 FOR UPDATE SKIP LOCKED""", (lanes, only_now, live))
                action = None
                for row in cur.fetchall():
                    candidate = dict(row)
                    fingerprint = AutomationService._run_fingerprint(cur, candidate)
                    gate = AutomationService._claude_gate(cur, candidate, cfg, fingerprint)
                    if gate is None:
                        action = candidate
                        break
                    code, text, discard = gate
                    if discard:
                        cur.execute("""UPDATE public.automation_actions SET status = 'discarded', error_code = %s, error_text = %s, finished_at = NOW(),
                                              lease_owner = NULL, updated_at = NOW() WHERE id = %s""", (code, text, candidate["id"]))
                    else:
                        cur.execute("""UPDATE public.automation_actions SET status = 'needs_user', error_code = %s, error_text = %s,
                                              lease_owner = NULL, lease_until = NULL, updated_at = NOW() WHERE id = %s""", (code, text, candidate["id"]))
                    _event(cur, candidate["id"], "backend", f"claude_gate:{code}", {"text": text})
                if action is None:
                    conn.commit()
                    return {"action": None, "reason": "outside_window" if only_now else ("breaker" if claude_paused else "empty")}
                cur.execute("""UPDATE public.automation_actions
                                  SET status = 'running_claude', executor = 'claude', claude_attempts = claude_attempts + 1,
                                      last_run_fingerprint = %s,
                                      lease_owner = %s, lease_until = NOW() + make_interval(mins => %s), updated_at = NOW()
                                WHERE id = %s RETURNING *""", (fingerprint, runner, 35 if (action.get("result") or {}).get("live_captcha") else 12, action["id"]))
                action = dict(cur.fetchone())
                cur.execute("INSERT INTO public.automation_runs (kind, action_id) VALUES ('claude', %s) RETURNING id", (action["id"],))
                run_id = cur.fetchone()["id"]
            conn.commit()
        finally:
            conn.close()
        return {"action": {**AutomationService._run_info(action, state), "run_id": run_id, "dossier": AutomationService._dossier(action),
                           "models": AutomationService.model_hint(action), "claude_paused": claude_paused,
                           "agent_engine": AutomationService.ai_engine()["agent"]}, "reason": None}

    @staticmethod
    def model_hint(action: dict) -> dict:
        """Token plan, phase 3: on a host where Haiku keeps failing and never finished, the chain starts at Sonnet."""
        host = (urlparse(action.get("target_url") or "").hostname or "").lower()
        if not host:
            return {}
        row = _one("""SELECT COUNT(*) FILTER (WHERE model = 'claude-haiku-5-5' AND NOT ok) AS bad,
                             COUNT(*) FILTER (WHERE model LIKE 'claude-haiku-5-5%%' AND ok) AS good
                        FROM public.automation_runs WHERE kind = 'claude' AND host = %s""", (host,)) or {}
        return {"skip_haiku": int(row.get("bad") or 0) >= 3 and int(row.get("good") or 0) == 0}

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
            if action.get("lane") == "ats":
                try:
                    from app.services.ats_auth_service import AtsAuthService
                    email = ((dossier.get("facts") or {}).get("contact") or {}).get("email") or "pjaragaojr@gmail.com"
                    dossier["site_account"] = AtsAuthService.get_or_create_account(action.get("target_url") or "", email=email)
                except Exception as e:
                    log.warning("site_account lookup failed: %s", e)
        return dossier

    @staticmethod
    def claude_result(action_id: int, run_id: int, status: str, summary: str = "", questions: Optional[list] = None,
                      audit_flags: Optional[list] = None, cost_usd: Optional[float] = None, transcript: Optional[dict] = None,
                      usage: Optional[dict] = None, provider_error: bool = False) -> Optional[dict]:
        usage = usage or {}
        tokens = sum(int(usage.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"))
        target = _one("SELECT target_url FROM public.automation_actions WHERE id = %s", (action_id,)) or {}
        host = (urlparse(target.get("target_url") or "").hostname or "").lower()
        from app.services.site_service import SiteService
        block = SiteService.block_kind(summary) if status == "needs_user" else None
        result_class = "provider_error" if provider_error else (block or status)
        _rows("""UPDATE public.automation_runs SET finished_at = NOW(), ok = %s, cost_usd = %s, summary = %s, model = %s,
                        input_tokens = %s, output_tokens = %s, cache_read_tokens = %s, cache_write_tokens = %s, host = %s, result_class = %s
                  WHERE id = %s""",
              (status in ("done", "job_closed", "already_applied") and not audit_flags, cost_usd,
               Json({"summary": summary, "audit_flags": audit_flags or [], **(transcript or {})}), (usage.get("model") or "")[:80] or None,
               usage.get("input_tokens"), usage.get("output_tokens"), usage.get("cache_read_tokens"), usage.get("cache_write_tokens"),
               host or None, result_class, run_id))
        if tokens:
            _rows("UPDATE public.automation_actions SET tokens_spent = tokens_spent + %s WHERE id = %s", (tokens, action_id))
        action = _one("SELECT * FROM public.automation_actions WHERE id = %s AND status = 'running_claude'", (action_id,))
        if not action:
            return None
        if provider_error:   # a usage limit, a 5xx, a quota: every run pauses, and this one did not count
            minutes = int((config().get("claude") or {}).get("breaker_minutes") or 30)
            _rows("UPDATE public.automation_state SET claude_paused_until = NOW() + make_interval(mins => %s) WHERE id = 1", (minutes,))
            AutomationService.add_event(action_id, "claude", "breaker", {"summary": summary[:300], "minutes": minutes}, level="warning")
            return _one("""UPDATE public.automation_actions SET status = 'escalated', claude_attempts = GREATEST(claude_attempts - 1, 0),
                                  last_run_fingerprint = NULL, scheduled_for = NOW() + make_interval(mins => %s), lease_owner = NULL,
                                  lease_until = NULL, updated_at = NOW() WHERE id = %s RETURNING *""", (minutes, action_id))
        if status == "deferred":   # Hermes did not finish it (Claude paused or off, or Hermes down): tried again later, no attempt spent
            state = _one("SELECT claude_paused_until FROM public.automation_state WHERE id = 1") or {}
            AutomationService.add_event(action_id, "claude", "hermes_deferred", {"summary": summary[:300]})
            return _one("""UPDATE public.automation_actions SET status = 'escalated', claude_attempts = GREATEST(claude_attempts - 1, 0),
                                  last_run_fingerprint = NULL, scheduled_for = GREATEST(COALESCE(%s, NOW()), NOW() + interval '15 minutes'), lease_owner = NULL,
                                  lease_until = NULL, updated_at = NOW() WHERE id = %s RETURNING *""", (state.get("claude_paused_until"), action_id))
        if block:
            SiteService.record_block(target.get("target_url") or host, summary)
            if (action.get("result") or {}).get("live_captcha") and AutomationService.captcha_session_active():
                AutomationService.add_event(action_id, "claude", "captcha_back_to_worker", {"summary": summary[:300]})
                return _one("""UPDATE public.automation_actions SET status = 'queued', run_now = TRUE, last_run_fingerprint = NULL,
                                      claude_attempts = GREATEST(claude_attempts - 1, 0), lease_owner = NULL, lease_until = NULL, updated_at = NOW()
                                WHERE id = %s RETURNING *""", (action_id,))
        AutomationService.add_event(action_id, "claude", f"result:{status}", {"summary": summary, "audit_flags": audit_flags or []},
                                    level="error" if audit_flags else "info")
        if audit_flags:   # it touched something outside the target: you look before anything else happens
            AutomationService.halt(f"Claude fora do alvo na ação #{action_id}: {'; '.join(map(str, audit_flags))[:300]}", [action["lane"]], source="claude")
            return AutomationService._to_user(action_id, "claude_audit", f"Saiu do alvo: {'; '.join(map(str, audit_flags))[:500]}")
        if status == "done":   # the worker looks at the page: the model saying so is not enough
            return _one("""UPDATE public.automation_actions SET status = 'unknown_outcome', scheduled_for = NULL, lease_owner = NULL,
                                  result = result || %s, updated_at = NOW() WHERE id = %s RETURNING *""",
                        (Json({"executed": True, "claude_summary": summary, "executed_at": now().isoformat()}), action_id))
        if status in ("job_closed", "already_applied"):
            return AutomationService.escalate(action_id, status, summary or status, [], "claude")
        summary_text = summary or "O Claude não conseguiu concluir"
        resolved = AutomationService._resolve_before_user(action, "claude_stopped", summary_text, questions, source="claude")
        if resolved is not None:
            return resolved
        return AutomationService._to_user(action_id, "claude_stopped", summary_text, questions)

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
        _rows("DELETE FROM public.approval_links WHERE expires_at < NOW() - INTERVAL '30 days'")   # each Lolo summary makes one

    @staticmethod
    def prepare_documents() -> int:
        """Approved jobs: the CV and the cover letter are generated now, a few jobs at once (blocking: call it from a thread), and
        read by the reviewer agent (cv_review: agent) or by you (cv_review: you, the first 20 on the main account)."""
        import asyncio
        from app.services.cv_review_service import CvReviewService, reasons
        from app.services.job_pipeline_service import JobPipelineService
        done = 0
        state = AutomationService.state()
        by_agent = (config().get("jobs") or {}).get("cv_review", "agent") == "agent"
        from app.services.site_service import SiteService, TextCache, archetype_of, text_key
        def one(action: dict) -> int:
            try:
                # token plan, phase 3: no documents for a site that only you can pass, nor for a page another action holds
                block = SiteService.human_block(action.get("target_url") or "")
                if block:
                    AutomationService._to_user(action["id"], "captcha", "Este site pediu CAPTCHA nas últimas tentativas: os documentos esperam você resolver.")
                    return 0
                made = asyncio.run(JobPipelineService.generate_docs(action["target_id"])) or []
                job = _one("SELECT job_title, resume_markdown, cover_letter, language, description FROM public.job_listings WHERE id = %s", (action["target_id"],)) or {}
                if not job.get("resume_markdown"):
                    # the writer (Sonnet) answered nothing: usually a session limit. The job stays approved and is tried
                    # again 10 min later; only the third failure in a row goes to you (2026-11-17)
                    tries = (_one("""SELECT COUNT(*) AS n FROM public.automation_events WHERE action_id = %s AND event = 'docs_retry'
                                       AND at > NOW() - interval '6 hours'""", (action["id"],)) or {}).get("n") or 0
                    if tries < 2:
                        AutomationService.add_event(action["id"], "reviewer", "docs_retry", {"try": tries + 1}, level="warning")
                        return 0
                    raise RuntimeError("o CV não foi gerado (3 tentativas)")
                if "resume_archetype" in made:   # the CV the reviewer already approved for this family: no new review
                    AutomationService.add_event(action["id"], "reviewer", "cv_archetype", {"archetype": archetype_of(job.get("job_title") or "")})
                    _rows("UPDATE public.automation_actions SET status = 'queued', updated_at = NOW() WHERE id = %s", (action["id"],))
                    return 1
                if by_agent:
                    verdict = asyncio.run(CvReviewService.run(action["target_id"]))
                    AutomationService.add_event(action["id"], "reviewer", "cv_review", {k: verdict[k] for k in ("approved", "rounds", "history")},
                                                level="info" if verdict["approved"] else "warning")
                    if verdict["approved"]:
                        _rows("UPDATE public.automation_actions SET status = 'queued', updated_at = NOW() WHERE id = %s", (action["id"],))
                        arch = archetype_of(job.get("job_title") or "") if (config().get("jobs") or {}).get("cv_archetypes", True) else None
                        if arch:   # the first approved CV of a family serves the next jobs of that family
                            from app.api.actions import get_job_lang
                            key = text_key("cv", arch, "pt" if get_job_lang(job) == "Portuguese" else "en")
                            fresh = _one("SELECT resume_markdown FROM public.job_listings WHERE id = %s", (action["target_id"],)) or {}
                            if not TextCache.get(key) and fresh.get("resume_markdown"):
                                TextCache.put(key, "cv", fresh["resume_markdown"])
                    else:   # still wrong after being redone: it waits for you, with the reasons
                        _rows("""UPDATE public.automation_actions SET status = 'review_docs', error_code = 'cv_review_failed', error_text = %s,
                                        updated_at = NOW() WHERE id = %s""",
                              (f"O revisor recusou depois de {verdict['rounds']} refação(ões):\n{reasons(verdict)}", action["id"]))
                else:
                    review = state["account_kind"] == "main" and state["review_cv_left"] > 0
                    _rows("UPDATE public.automation_actions SET status = %s, updated_at = NOW() WHERE id = %s",
                          ("review_docs" if review else "queued", action["id"]))
                return 1
            except Exception as e:
                log.warning("documents for action %s not generated: %s", action["id"], e)
                AutomationService._to_user(action["id"], "documents_failed", f"Não consegui gerar os documentos: {e}")
                return 0

        # 2026-11-17: several jobs at once (each is minutes of Sonnet: CV, letter, review rounds), as many as the Claude shim
        # runs in parallel; one at a time took half an hour for 14 approved jobs
        parallel = max(1, int((config().get("jobs") or {}).get("docs_parallel", 3)))
        rows = _rows("""SELECT * FROM public.automation_actions a WHERE kind = 'apply' AND status = 'approved'
                           AND NOT EXISTS (SELECT 1 FROM public.automation_events e WHERE e.action_id = a.id AND e.event = 'docs_retry'
                                            AND e.at > NOW() - interval '10 minutes')
                         ORDER BY rank, sort_at DESC LIMIT %s""", (parallel,))
        if len(rows) <= 1:
            return sum(one(a) for a in rows)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            done = sum(pool.map(one, rows))
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
                {"post_url": e["post_url"], "post_head": (e.get("post_text") or "")[:500], "post_full": (e.get("post_text") or "")[:6000],
                 "author": e.get("author_name"), "text": e["comment_draft"],
                 "relevance": e.get("relevance"), "reason": e.get("reason"), "variants": e.get("comment_variants") or {}},
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
        for hour in cfg.get("reply_scan_hours") or []:
            if local.hour >= hour:
                made += bool(AutomationService.create_action(
                    "reply_scan", f"reply_scan:{day}:{hour}", "Respostas aos seus comentários", NOTIFICATIONS_URL, {"limit": 10},
                    status="queued", rank=38))
        for hour in cfg.get("inbox_scan_hours") or []:
            if local.hour >= hour:
                made += bool(AutomationService.create_action(
                    "inbox_scan", f"inbox_scan:{day}:{hour}", "Convites e mensagens", RECEIVED_INVITES_URL, {"limit": 10},
                    status="queued", rank=37))
        if AutomationService.saved_import_due(local) and not _one(
                "SELECT 1 FROM public.automation_actions WHERE kind = 'saved_import' AND status = ANY(%s) LIMIT 1", (list(OPEN),)):
            made += bool(AutomationService.create_action(
                "saved_import", f"saved_import:{day}:{local.hour}", "Vagas salvas no LinkedIn", SAVED_JOBS_URL, {}, status="queued", rank=39))
        for hour in cfg.get("follow_scan_hours") or []:
            if local.hour >= hour:
                target = JobSearchService.next_follow_scan()
                if target:
                    made += bool(AutomationService.create_action(
                        "follow_scan", f"follow_scan:{target['key']}", target["name"], target["url"], target, status="queued", rank=43))
        return made

    # ── Your saved jobs on LinkedIn ──────────────────────────────────────
    @staticmethod
    def saved_import_settings(state: Optional[dict] = None) -> dict:
        state = state or AutomationService.state()
        return {**SAVED_IMPORT_DEFAULT, **(state.get("saved_import") or {})}

    @staticmethod
    def set_saved_import(enabled: bool, day_start: int, day_end: int, day_every: int, night_every: int) -> dict:
        value = {"enabled": enabled, "day_start": day_start, "day_end": day_end, "day_every": day_every, "night_every": night_every}
        row = _one("UPDATE public.automation_state SET saved_import = %s, updated_at = NOW() WHERE id = 1 RETURNING *", (Json(value),))
        return AutomationService.saved_import_settings(row)

    @staticmethod
    def saved_import_due(local: datetime, settings_: Optional[dict] = None) -> bool:
        """Whether this hour is one of the slots: every day_every hours counted from day_start, during the day (which may
        cross midnight); every night_every hours counted from day_end, outside it."""
        s = settings_ or AutomationService.saved_import_settings()
        if not s.get("enabled"):
            return False
        start, end, hour = s["day_start"] % 24, s["day_end"] % 24, local.hour
        by_day = start <= hour < end if start < end else (hour >= start or hour < end)
        if start == end:   # the whole day is "day"
            by_day = True
        every, origin = (s["day_every"], start) if by_day else (s["night_every"], end)
        return bool(every) and (hour - origin) % every == 0

    @staticmethod
    def saved_import_overview() -> dict:
        """What Configurações shows: the hours and the last reads."""
        runs = _rows("""SELECT id, status, run_now, created_at, finished_at, result, error_code, error_text FROM public.automation_actions
                         WHERE kind = 'saved_import' ORDER BY id DESC LIMIT 8""")
        return {"settings": AutomationService.saved_import_settings(), "runs": runs}

    @staticmethod
    def run_saved_import() -> dict:
        """Now (Lolo, or the button in Configurações): one read at a time; a failed one waiting for you is replaced by this."""
        running = _one("""SELECT * FROM public.automation_actions WHERE kind = 'saved_import' AND status = ANY(%s)
                           ORDER BY id DESC LIMIT 1""", (["queued"] + list(RUNNING),))
        if running:
            _rows("UPDATE public.automation_actions SET run_now = TRUE WHERE id = %s", (running["id"],))
            return {**running, "already": True}
        _rows("""UPDATE public.automation_actions SET status = 'cancelled', finished_at = NOW(), updated_at = NOW()
                  WHERE kind = 'saved_import' AND status IN ('needs_user', 'escalated')""")
        # run_now: it does not wait for a slot, and Lolo tells you what came in
        action = AutomationService.create_action("saved_import", f"saved_import:now:{now().isoformat()}", "Vagas salvas no LinkedIn",
                                                 SAVED_JOBS_URL, {}, status="queued", rank=39)
        return _one("UPDATE public.automation_actions SET run_now = TRUE WHERE id = %s RETURNING *", (action["id"],))

    @staticmethod
    def run_scan(kind: str) -> dict:
        """inbox_scan / reply_scan right now: one at a time; one already waiting is just moved to the front."""
        running = _one("""SELECT * FROM public.automation_actions WHERE kind = %s AND status = ANY(%s) ORDER BY id DESC LIMIT 1""",
                       (kind, ["queued"] + list(RUNNING)))
        if running:
            _rows("UPDATE public.automation_actions SET run_now = TRUE WHERE id = %s", (running["id"],))
            return {**running, "already": True}
        url, title = ((RECEIVED_INVITES_URL, "Convites e mensagens") if kind == "inbox_scan" else (NOTIFICATIONS_URL, "Respostas aos seus comentários"))
        action = AutomationService.create_action(kind, f"{kind}:now:{now().isoformat()}", title, url, {"limit": 10}, status="queued",
                                                 rank=37 if kind == "inbox_scan" else 38)
        return _one("UPDATE public.automation_actions SET run_now = TRUE WHERE id = %s RETURNING *", (action["id"],))

    @staticmethod
    def expire_stale_proposals() -> None:
        _rows("""UPDATE public.automation_actions SET status = 'expired', finished_at = NOW(), updated_at = NOW()
                  WHERE status = 'proposed' AND kind IN ('comment', 'reply', 'message') AND created_at < NOW() - INTERVAL '7 days'""")
        # a job you already moved on (applied by hand, rejected, archived) leaves the approval list
        _rows("""UPDATE public.automation_actions a SET status = 'discarded', error_code = 'already_handled', finished_at = NOW(), updated_at = NOW(),
                        error_text = 'Saiu da lista: a vaga já está como ' || j.status
                   FROM public.job_listings j
                  WHERE a.status = 'proposed' AND a.kind = 'apply' AND a.target_type = 'job' AND j.id = a.target_id
                    AND j.status NOT IN ('new', 'scraped', 'discovered')""")
        # a job on the list for proposal_days with a score below proposal_keep_score and no answer: it leaves the list, and
        # the job goes to Descartadas with the reason (recoverable) — decided 2026-11-22, 10 days and 80
        jobs_cfg = config().get("jobs") or {}
        days, keep = int(jobs_cfg.get("proposal_days", 10)), int(jobs_cfg.get("proposal_keep_score", 80))
        expired = _rows("""UPDATE public.automation_actions a SET status = 'expired', error_code = 'stale_proposal', finished_at = NOW(), updated_at = NOW(),
                                  error_text = 'Saiu da lista: ' || %s || ' dias sem resposta, nota ' || j.triage_score
                             FROM public.job_listings j
                            WHERE a.status = 'proposed' AND a.kind = 'apply' AND a.target_type = 'job' AND j.id = a.target_id
                              AND a.created_at < NOW() - make_interval(days => %s) AND j.triage_score IS NOT NULL AND j.triage_score < %s
                        RETURNING j.id, j.triage_score""", (str(days), days, keep))
        for r in expired:
            _rows("""UPDATE public.job_listings SET triage_outcome = 'discarded', updated_at = NOW(),
                            triage_reason = %s || COALESCE(' ' || triage_reason, '') WHERE id = %s AND status = 'discovered'""",
                  (f"Expirou: {days} dias na lista sem resposta (nota {r['triage_score']}).", r["id"]))

    @staticmethod
    def tick() -> None:
        """Blocking: main.py calls it from a thread. Off, it only keeps the books."""
        from app.services.job_search_service import JobSearchService
        from app.services.bot_service import BotService
        AutomationService.housekeeping()
        AutomationService.expire_stale_proposals()
        if AutomationService.state().get("mode") != "off":
            AutomationService.schedule_reads()
            # documents for approved jobs run in their own loop (main._documents, 2026-11-17): minutes of Sonnet per job
            # never hold the books, the job reading or the notifications
            JobSearchService.triage_pending()
            JobSearchService.propose_ready()
            AutomationService.sync_proposals()
            JobSearchService.score_proposed()
        try:   # what to tell you on WhatsApp; a failure here never holds the queue
            BotService.collect()
        except Exception as e:
            log.warning("bot notifications not collected: %s", e)
