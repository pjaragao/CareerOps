"""Reading of the mailbox: answers to your applications. Two ways in: the IMAP check here is read-only by construction (the
folder is opened with EXAMINE and messages fetched with BODY.PEEK); Lolo reads Gmail with its own access and sends the
messages to ingest(), and then archives what this reading says needs nothing from you (a confirmation, a "viewed", a
rejection), leaving a next step in the inbox for you. Nothing is ever deleted or answered. The AI that reads a message has
no tools: a malicious email can at worst confuse the reading of itself."""
import asyncio
import email
import email.policy
import imaplib
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from typing import List, Optional

from app.core.config import settings
from app.services.automation_service import _one, _rows, config
from app.services.skill_service import SkillService

log = logging.getLogger("email_monitor")

CLASSES = ("confirmation", "viewed", "rejection", "interview", "assessment", "recruiter_question", "offer", "linkedin_alert", "other")
ALERT_KINDS = ("restriction", "unusual_activity", "verification_code", "new_sign_in", "other")
# a warning that stops the LinkedIn lanes, as a warning on the page does
HALTING_ALERTS = ("restriction", "unusual_activity")
THEMES = ("experiência", "habilidade técnica", "senioridade", "idioma", "localização/visto", "pretensão salarial", "entrevista",
          "formato do CV", "outro")
ATS_DOMAINS = ("greenhouse", "lever.co", "workday", "myworkday", "ashbyhq", "gupy", "smartrecruiters", "icims", "workable", "teamtailor",
               "bamboohr", "jobvite", "recruitee", "breezy", "taleo", "successfactors", "personio", "rippling")
# Words of an answer about an application. Job alerts and newsletters are filtered out below.
KEYWORDS = re.compile(r"your application|application (for|to|was|received|status|update)|thank you for applying|thanks for applying|"
                      r"interview|next steps?|unfortunately|not moving forward|move forward|we regret|assessment|coding challenge|"
                      r"candidatura|processo seletivo|entrevista|infelizmente|agradecemos seu interesse|próxima etapa|proxima etapa", re.I)
NOISE = re.compile(r"job alert|jobs? for you|new jobs|recommended jobs|vagas para voc|alerta de vaga|newsletter|unsubscribe from job|digest", re.I)
NOISE_SENDERS = re.compile(r"jobalerts?|newsletter|news@|marketing|notifications-noreply", re.I)
# LinkedIn writing about the account, not about a job
LINKEDIN_ALERT = re.compile(r"unusual|suspicious|restrict|security|verif|sign[- ]?in|new device|password|locked|limited|"
                            r"atividade (incomum|suspeita)|restri|seguran|verifica|c[oó]digo|novo dispositivo|senha|bloque|limitad", re.I)
MAX_CHARS = 4000


def _email_config() -> dict:
    return config().get("email") or {}


def _domain(sender: str) -> str:
    return (parseaddr(sender)[1].rpartition("@")[2] or "").lower()


def _text_of(msg) -> str:
    """The message as plain text, no attachments."""
    part = msg.get_body(preferencelist=("plain", "html")) if hasattr(msg, "get_body") else None
    if part is None:
        return ""
    try:
        text = part.get_content()
    except Exception:
        return ""
    if part.get_content_type() == "text/html":
        text = unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", text)))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def is_candidate(sender: str, subject: str, body: str, company_keys: List[str]) -> bool:
    """Whether this message may be about an application. Nothing else reaches the AI."""
    if NOISE.search(subject) or NOISE_SENDERS.search(parseaddr(sender)[1]):
        return False
    domain = _domain(sender)
    if any(a in domain for a in ATS_DOMAINS):
        return True
    if domain.endswith("linkedin.com"):
        if LINKEDIN_ALERT.search(subject):
            return True
        return bool(re.search(r"your application|sua candidatura|application (was )?(sent|viewed)|candidatura (foi )?(enviada|visualizada)", subject, re.I))
    if any(k and k in domain.replace("-", "") for k in company_keys):
        return True
    return bool(KEYWORDS.search(subject) or (KEYWORDS.search(body[:1500]) and any(k and k in body[:1500].lower() for k in company_keys)))


def _company_key(name: Optional[str]) -> str:
    name = re.sub(r"\b(inc|llc|ltd|ltda|s\.?a\.?|gmbh|corp|corporation|company|group)\b\.?", " ", (name or "").lower())
    return re.sub(r"[^a-z0-9]+", "", name)


def match_job(sender: str, subject: str, body: str, jobs: List[dict]) -> Optional[int]:
    """The one job this message is about, by the company in the sender's domain or the subject, the title breaking a tie.
    Two possible jobs and no way to tell = none: it goes to "sem vaga associada"."""
    domain = _domain(sender).replace("-", "")
    head = f"{subject}\n{body[:1500]}".lower()
    squeezed = re.sub(r"[^a-z0-9]+", "", head)
    found = []
    for job in jobs:
        key = _company_key(job.get("company"))
        if len(key) >= 3 and (key in domain or key in squeezed):
            found.append(job)
    if len(found) == 1:
        return found[0]["id"]
    titled = [j for j in found if (j.get("job_title") or "").lower() and (j["job_title"] or "").lower() in head]
    return titled[0]["id"] if len(titled) == 1 else None


def _status_change(classification: str, confidence: float, job: Optional[dict], baseline: bool) -> Optional[str]:
    """What this reading does to the job. The first read only suggests; so does everything until you switch auto_status on."""
    cfg = _email_config()
    if baseline or not job or not cfg.get("auto_status"):
        return None
    status = job.get("status")
    if classification == "rejection" and confidence >= float(cfg.get("rejection_confidence", 0.9)) and status in ("applied", "interviewing"):
        return "rejected"
    if classification == "interview" and status == "applied":
        return "interviewing"
    if classification == "offer" and status in ("applied", "interviewing"):
        return "offer"
    return None


class EmailMonitorService:
    @staticmethod
    def configured() -> bool:
        return bool(settings.GMAIL_ADDRESS and settings.GMAIL_APP_PASSWORD)

    @staticmethod
    def _jobs() -> List[dict]:
        return _rows("""SELECT id, company, job_title, status FROM public.job_listings
                         WHERE status IN ('applied', 'interviewing', 'offer', 'rejected', 'done')""")

    @staticmethod
    def fetch_since(since: datetime) -> List[dict]:
        """Messages received since then, read-only. EXAMINE + BODY.PEEK leave every message exactly as it was."""
        out = []
        with imaplib.IMAP4_SSL(settings.GMAIL_IMAP_HOST) as box:
            box.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
            box.select("INBOX", readonly=True)
            typ, data = box.search(None, "SINCE", since.strftime("%d-%b-%Y"))
            if typ != "OK":
                raise RuntimeError(f"IMAP search failed: {typ}")
            for num in data[0].split():
                typ, parts = box.fetch(num, "(BODY.PEEK[]<0.200000>)")   # the text is at the start; attachments are not needed
                if typ != "OK" or not parts or not isinstance(parts[0], tuple):
                    continue
                out.append(parts[0][1])
        return out

    @staticmethod
    def _parse(raw: bytes) -> dict:
        msg = email.message_from_bytes(raw, policy=email.policy.default)
        try:
            received = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
        except (TypeError, ValueError):
            received = None
        refs = (msg.get("References") or "").split()
        return {"message_id": (msg.get("Message-ID") or "").strip(), "thread_id": refs[0] if refs else (msg.get("Message-ID") or "").strip(),
                "sender": str(msg.get("From") or ""), "subject": str(msg.get("Subject") or ""), "received_at": received, "body": _text_of(msg)}

    @staticmethod
    def process(messages: List[dict], baseline: bool = False, source: str = "imap") -> dict:
        """Filters, reads and records. A message already recorded is skipped, so running twice changes nothing."""
        from app.services.automation_service import LINKEDIN_LANES, AutomationService
        from app.services.bot_service import BotService
        jobs = EmailMonitorService._jobs()
        by_id = {j["id"]: j for j in jobs}
        keys = [_company_key(j.get("company")) for j in jobs]
        keys = [k for k in keys if len(k) >= 3]
        ids = [m["message_id"] for m in messages if m.get("message_id")]
        known = {r["message_id"] for r in _rows("SELECT message_id FROM public.job_email_events WHERE message_id = ANY(%s)", (ids,))}
        stats = {"read": len(messages), "candidates": 0, "recorded": 0, "status_changes": 0, "failed": 0, "feedback": 0, "alerts": 0}
        counts: dict = {}
        closed: List[str] = []   # what only confirms an application: one line each in a single message
        for m in messages:
            if not m.get("message_id") or m["message_id"] in known or not is_candidate(m["sender"], m["subject"], m["body"], keys):
                continue
            stats["candidates"] += 1
            try:
                reading = asyncio.run(SkillService.run_skill("jobs/email_classify.md", {
                    "sender": m["sender"][:300], "subject": m["subject"][:300], "body": m["body"][:MAX_CHARS]}))
            except Exception as e:
                log.warning("message not read: %s", e)
                stats["failed"] += 1
                continue
            if not isinstance(reading, dict) or reading.get("classification") not in CLASSES:
                stats["failed"] += 1
                continue
            confidence = max(0.0, min(1.0, float(reading.get("confidence") or 0)))
            classification = reading["classification"]
            alert = reading.get("alert_kind") if classification == "linkedin_alert" and reading.get("alert_kind") in ALERT_KINDS else None
            if classification == "linkedin_alert" and not _domain(m["sender"]).endswith("linkedin.com"):
                classification, alert = "other", None   # only LinkedIn itself speaks for the account
            job_id = match_job(m["sender"], m["subject"], m["body"], jobs) if classification != "linkedin_alert" else None
            job = by_id.get(job_id)
            new_status = _status_change(classification, confidence, job, baseline)
            old_status = (job or {}).get("status")
            # what you should look at: no job found, something that asks for you, or a job status that does not match
            review = (classification not in ("other", "linkedin_alert") and not job) or classification in ("assessment", "recruiter_question", "interview", "offer") \
                or (classification in ("confirmation", "viewed") and bool(job) and job["status"] != "applied" and job["status"] != "interviewing")
            mail_action = _mail_action(classification, confidence, source)
            row = _one("""
                INSERT INTO public.job_email_events (message_id, thread_id, job_id, received_at, sender_domain, subject, classification, confidence,
                                                     summary, evidence_quote, status_applied, needs_review, baseline, alert_kind, source, mail_action)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO NOTHING RETURNING id""",
                       (m["message_id"][:500], (m.get("thread_id") or "")[:500], job_id, m.get("received_at"), _domain(m["sender"])[:200], m["subject"][:300], classification,
                        confidence, (reading.get("summary") or "")[:500], (reading.get("evidence") or "")[:400], new_status, review, baseline, alert, source, mail_action))
            if not row:
                continue
            stats["recorded"] += 1
            counts[classification] = counts.get(classification, 0) + 1
            if new_status:
                _rows("UPDATE public.job_listings SET status = %s, updated_at = NOW() WHERE id = %s", (new_status, job_id))
                stats["status_changes"] += 1
                job["status"] = new_status
            feedback = _save_feedback(row["id"], job, m, reading) if classification not in ("other", "linkedin_alert") else []
            stats["feedback"] += len(feedback)
            halted = False
            if alert in HALTING_ALERTS and confidence >= 0.8 and _recent(m.get("received_at")):
                AutomationService.halt(f"Aviso do LinkedIn por e-mail: {(reading.get('summary') or m['subject'])[:200]}", LINKEDIN_LANES,
                                       source="email", ramp_down=True)
                halted = True
            if alert:
                stats["alerts"] += 1
            if classification in ("confirmation", "viewed"):
                closed.append(f"{_where(job, m)} — {'recebida' if classification == 'confirmation' else 'visualizada'}")
            elif not baseline:
                BotService.email_notice(row["id"], classification, alert, halted, reading, job, m, feedback, archived=mail_action == "archive",
                                        status_change=(old_status, new_status) if new_status else None, confidence=confidence)
        archiving = source != "imap"
        if baseline and stats["recorded"]:
            BotService.notify("email_summary", (
                "📬 Comecei a acompanhar seu e-mail de candidaturas. Nesta primeira leitura nenhuma vaga muda de status: as respostas "
                "ficam em Automação → Respostas e os feedbacks em Sugestões, para você conferir."
                + (" Confirmações e recusas antigas eu li e arquivei; o que fala de próxima etapa ficou na caixa de entrada." if archiving else "")),
                key=f"email_baseline:{source}")
        elif closed:
            BotService.notify("email_summary", f"📬 *Confirmações de candidatura*{' (li e arquivei)' if archiving else ''}\n"
                              + "\n".join(f"• {c}" for c in closed[:30]))
        # to archive now: what this reading decided, and what an earlier run decided but was not archived yet
        stats["archive"] = [r["message_id"] for r in _rows("""SELECT message_id FROM public.job_email_events
                                                               WHERE message_id = ANY(%s) AND mail_action = 'archive' AND mail_done_at IS NULL""", (ids,))]
        return stats

    @staticmethod
    def mark_archived(message_ids: List[str]) -> int:
        return len(_rows("""UPDATE public.job_email_events SET mail_done_at = NOW()
                             WHERE message_id = ANY(%s) AND mail_action = 'archive' AND mail_done_at IS NULL RETURNING id""", (message_ids,)))

    @staticmethod
    def ingest(messages: List[dict], source: str = "lolo", baseline: Optional[bool] = None) -> dict:
        """Messages someone else read from the mailbox (Lolo, with its own Gmail access): the same filter and reading. A first
        read sent in several parts says so in each one, so none of them changes a status."""
        if baseline is None:
            baseline = not _one("SELECT 1 AS y FROM public.automation_runs WHERE kind = 'email' AND ok LIMIT 1")
        run = _one("INSERT INTO public.automation_runs (kind) VALUES ('email') RETURNING id")
        try:
            stats = EmailMonitorService.process(messages, baseline, source)
            _rows("UPDATE public.automation_runs SET finished_at = NOW(), ok = TRUE, summary = %s::jsonb WHERE id = %s",
                  (_json({**{k: v for k, v in stats.items() if k != "archive"}, "baseline": baseline, "source": source}), run["id"]))
            return {"ok": True, **stats, "baseline": baseline}
        except Exception as e:
            log.warning("email ingest failed: %s", e)
            _rows("UPDATE public.automation_runs SET finished_at = NOW(), ok = FALSE, summary = %s::jsonb WHERE id = %s", (_json({"error": str(e)[:500]}), run["id"]))
            raise

    @staticmethod
    def gmail_query(days: int = 2) -> str:
        """What Lolo searches in Gmail: senders and words of an answer about an application, LinkedIn's account notices, and the
        companies you applied to. Everything it finds still goes through the filter above."""
        companies = [k for k in (_company_key(r["company"]) for r in _rows("""
            SELECT company FROM public.job_listings WHERE status IN ('applied', 'interviewing', 'offer') AND company IS NOT NULL
             ORDER BY updated_at DESC NULLS LAST LIMIT 40""")) if len(k) >= 4]
        senders = [d.split(".")[0] for d in ATS_DOMAINS] + ["security-noreply@linkedin.com", "jobs-noreply@linkedin.com"] + companies
        words = ['"your application"', '"sua candidatura"', '"thank you for applying"', "interview", "entrevista", '"processo seletivo"',
                 '"next steps"', "unfortunately", "infelizmente", '"not moving forward"', "assessment"]
        return (f"newer_than:{max(1, min(int(days), 60))}d -in:sent -in:drafts -in:chats -category:promotions "
                f"(from:({' OR '.join(dict.fromkeys(senders))}) OR {' OR '.join(words)})")

    @staticmethod
    def run() -> dict:
        """One check (blocking). The first one looks further back, only as suggestions."""
        if not EmailMonitorService.configured():
            return {"ok": False, "detail": "GMAIL_ADDRESS / GMAIL_APP_PASSWORD não configurados"}
        last = _one("SELECT started_at FROM public.automation_runs WHERE kind = 'email' AND ok ORDER BY started_at DESC LIMIT 1")
        baseline = not last
        days = _email_config().get("first_run_days", 45)
        since = (last["started_at"] - timedelta(days=1)) if last else datetime.now(timezone.utc) - timedelta(days=days)
        run = _one("INSERT INTO public.automation_runs (kind) VALUES ('email') RETURNING id")
        try:
            messages = [EmailMonitorService._parse(raw) for raw in EmailMonitorService.fetch_since(since)]
            stats = EmailMonitorService.process(messages, baseline)
            _rows("UPDATE public.automation_runs SET finished_at = NOW(), ok = TRUE, summary = %s::jsonb WHERE id = %s", (_json({**stats, "baseline": baseline}), run["id"]))
            log.info("email check: %s", stats)
            return {"ok": True, **stats, "baseline": baseline}
        except Exception as e:
            log.warning("email check failed: %s", e)
            _rows("UPDATE public.automation_runs SET finished_at = NOW(), ok = FALSE, summary = %s::jsonb WHERE id = %s", (_json({"error": str(e)[:500]}), run["id"]))
            return {"ok": False, "detail": str(e)[:500]}

    @staticmethod
    def due() -> bool:
        """Whether today's check is still to run (or the checks are due, with a shorter email_check_hours)."""
        from zoneinfo import ZoneInfo
        cfg = _email_config()
        local = datetime.now(ZoneInfo(settings.APP_TIMEZONE))
        if not EmailMonitorService.configured() or (local.hour, local.minute) < (cfg.get("hour", 7), cfg.get("minute", 30)):
            return False
        start = local.replace(hour=cfg.get("hour", 7), minute=cfg.get("minute", 30), second=0, microsecond=0)
        return not _one("SELECT 1 AS y FROM public.automation_runs WHERE kind = 'email' AND ok AND started_at >= %s LIMIT 1", (start,))

    # ── Screens ──────────────────────────────────────────────────────────
    @staticmethod
    def events_view(limit: int = 100) -> dict:
        items = _rows("""
            SELECT e.*, j.job_title, j.company, j.status AS job_status FROM public.job_email_events e
              LEFT JOIN public.job_listings j ON j.id = e.job_id
             ORDER BY e.received_at DESC NULLS LAST LIMIT %s""", (limit,))
        last = _one("SELECT started_at, finished_at, ok, summary FROM public.automation_runs WHERE kind = 'email' ORDER BY started_at DESC LIMIT 1")
        return {"items": items, "last_run": last, "configured": EmailMonitorService.configured(), "auto_status": bool(_email_config().get("auto_status"))}

    @staticmethod
    def review(event_id: int, classification: Optional[str], job_id: Optional[int]) -> Optional[dict]:
        """You read it: correct what the AI said and it leaves the review list. A status set by it is undone from the job itself."""
        if classification and classification not in CLASSES:
            return None
        return _one("""UPDATE public.job_email_events
                          SET classification = COALESCE(%s, classification), job_id = COALESCE(%s, job_id), needs_review = FALSE, reviewed_at = NOW()
                        WHERE id = %s RETURNING *""", (classification, job_id, event_id))

    @staticmethod
    def funnel() -> dict:
        """Applications → answers → interviews, by search, market, who executed it and how old the ad was when you applied.
        This is what says whether applying early really brings more interviews in your case."""
        def table(expr: str, extra_join: str = "") -> List[dict]:
            return _rows(f"""
                SELECT {expr} AS bucket, COUNT(*) AS applied,
                       COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM public.job_email_events e WHERE e.job_id = j.id
                                                       AND e.classification IN ('rejection', 'interview', 'assessment', 'recruiter_question', 'offer'))) AS answered,
                       COUNT(*) FILTER (WHERE j.status IN ('interviewing', 'offer')
                                           OR EXISTS (SELECT 1 FROM public.job_email_events e WHERE e.job_id = j.id AND e.classification IN ('interview', 'offer'))) AS interviews
                  FROM public.job_listings j {extra_join}
                 WHERE j.status IN ('applied', 'interviewing', 'offer', 'rejected', 'done')
                 GROUP BY 1 ORDER BY 2 DESC""")
        age = """CASE WHEN j.posted_at IS NULL OR j.applied_at IS NULL THEN 'sem dado'
                      WHEN j.applied_at - j.posted_at <= INTERVAL '24 hours' THEN 'até 24 h'
                      WHEN j.applied_at - j.posted_at <= INTERVAL '48 hours' THEN '24–48 h'
                      ELSE 'mais de 48 h' END"""
        return {"by_age": table(age), "by_search": table("COALESCE(j.search_slug, 'manual')"),
                "by_market": table("COALESCE(j.employer_market, 'sem dado')"),
                "by_executor": table("CASE WHEN j.applied_via_bot THEN 'sistema' ELSE 'você' END")}


def _mail_action(classification: str, confidence: float, source: str) -> Optional[str]:
    """What Lolo does with the message in Gmail. The IMAP check never touches the mailbox."""
    if source == "imap":
        return None
    cfg = _email_config()
    if classification in (cfg.get("archive_classes") or ["confirmation", "viewed", "rejection"]) and confidence >= float(cfg.get("archive_confidence", 0.8)):
        return "archive"
    return "keep" if classification != "other" else None


def _where(job: Optional[dict], m: dict) -> str:
    if job:
        return " · ".join(x for x in (job.get("job_title"), job.get("company")) if x)
    name, addr = parseaddr(m.get("sender") or "")
    return f"{name or addr} ({(m.get('subject') or '')[:80]})"


def _recent(received_at, days: int = 2) -> bool:
    """A warning from last week says nothing about now: only a fresh one stops anything."""
    if not received_at:
        return True
    when = received_at if isinstance(received_at, datetime) else None
    if when is None:
        try:
            when = datetime.fromisoformat(str(received_at).replace("Z", "+00:00"))
        except ValueError:
            return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - when <= timedelta(days=days)


def _save_feedback(event_id: int, job: Optional[dict], m: dict, reading: dict) -> List[dict]:
    """The reasons beyond the polite "no", one row each, under a fixed theme so they can be grouped."""
    saved = []
    items = reading.get("feedback") if isinstance(reading.get("feedback"), list) else []
    for f in items[:5]:
        if not isinstance(f, dict) or not str(f.get("suggestion") or "").strip():
            continue
        target = f.get("target") if f.get("target") in ("cv", "me") else "me"
        theme = f.get("theme") if f.get("theme") in THEMES else "outro"
        row = _one("""INSERT INTO public.improvement_suggestions (email_event_id, job_id, company, target, theme, suggestion, evidence_quote)
                      VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                   (event_id, job["id"] if job else None, (job or {}).get("company") or _domain(m["sender"]), target, theme,
                    str(f["suggestion"]).strip()[:500], str(f.get("evidence") or "")[:400]))
        saved.append(row)
    return saved


def _json(value: dict) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, default=str)
