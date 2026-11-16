"""ATS portal credentials and email verification helper (OTP codes & confirmation links)."""
import email
import email.policy
import imaplib
import json
import logging
import os
import re
import secrets
import string
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor

log = logging.getLogger("ats_auth")

MULTI_TENANT_ATS = (
    "myworkdayjobs.com", "myworkday.com", "personio.com", "personio.de", "hibob.com", "bamboohr.com",
    "recruitee.com", "breezy.hr", "gupy.io", "teamtailor.com", "oraclecloud.com", "successfactors.com",
    "successfactors.eu", "taleo.net", "icims.com", "avature.net", "dayforcehcm.com", "ultipro.com",
    "pinpointhq.com", "rippling.com", "loxo.co",
)
STRIP_SUBDOMAINS = ("www.", "jobs.", "careers.", "apply.", "app.", "applicants.", "explore-jobs.", "empleo.")

OTP_CONTEXT_RE = re.compile(
    r"(?:security\s+code|verification\s+code|verify\s+your\s+email|one[- ]time\s+(?:code|passcode|pin)|"
    r"c[oó]digo\s+(?:de\s+)?(?:seguran[cç]a|verifica[cç][aã]o|acesso|confirma[cç][aã]o)|passcode|\botp\b|pin\b)"
    r"(?:[^\w\n]{0,40}|[^:\n]{0,80}[:\-])\s*\n*\s*([A-Za-z0-9]{4,10})\b",
    re.I,
)
OTP_FALLBACK_DIGIT_RE = re.compile(r"(?:^|\s)(\d{6,8})(?:\s|$|<|\.)")
URL_RE = re.compile(r"https?://[^\s<>\"')\]}]+", re.I)
LINK_PRIORITY_RE = re.compile(r"(?:verif|confirm|activ|token|reset|password|magic|auth|signin|sign-in|otp|security|validate)", re.I)
LINK_NOISE_RE = re.compile(
    r"(?:unsubscribe|preferences|privacy|terms|linkedin\.com|twitter\.com|x\.com|facebook\.com|instagram\.com|"
    r"\.(?:png|jpe?g|gif|svg|css|woff2?|ico)(?:\?|$))",
    re.I,
)


def _ensure_table() -> None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.automation_site_accounts (
                    id SERIAL PRIMARY KEY,
                    site_key TEXT NOT NULL UNIQUE,
                    domain TEXT NOT NULL,
                    email TEXT NOT NULL,
                    password TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    notes TEXT NOT NULL DEFAULT '',
                    last_used_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS public.automation_email_verifications (
                    id SERIAL PRIMARY KEY,
                    message_id TEXT UNIQUE,
                    sender TEXT NOT NULL DEFAULT '',
                    subject TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    code TEXT NOT NULL DEFAULT '',
                    links JSONB NOT NULL DEFAULT '[]'::jsonb,
                    received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                );
            """)
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


def site_key_for(url_or_domain: str) -> str:
    raw = (url_or_domain or "").strip().lower()
    if "://" in raw:
        host = (urlparse(raw).hostname or "").lower()
    else:
        host = raw.split("/")[0].split(":")[0].lower()
    if not host:
        return "unknown"
    host = host.removeprefix("www.")
    for suffix in MULTI_TENANT_ATS:
        if host == suffix or host.endswith("." + suffix):
            return host
    parts = host.split(".")
    for prefix in STRIP_SUBDOMAINS:
        clean_prefix = prefix.rstrip(".")
        while parts and len(parts) > 2 and parts[0] == clean_prefix:
            parts.pop(0)
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "edu", "gov") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts) if len(parts) <= 2 else ".".join(parts[-2:])
    return host


def generate_password(length: int = 16) -> str:
    """Strong ATS-compatible password with upper, lower, digit and safe punctuation (!@#)."""
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    lower = "abcdefghijkmnopqrstuvwxyz"
    digits = "23456789"
    special = "!@#"
    pool = upper + lower + digits + special
    chars = [
        secrets.choice(upper),
        secrets.choice(upper),
        secrets.choice(lower),
        secrets.choice(lower),
        secrets.choice(digits),
        secrets.choice(digits),
        secrets.choice(special),
        secrets.choice(special),
    ] + [secrets.choice(pool) for _ in range(max(4, length - 8))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def extract_verification(subject: str, body: str) -> Dict[str, Any]:
    """Pull OTP codes and confirmation/reset URLs out of an email subject + body."""
    combined = f"{subject}\n{body}"
    code = ""
    for m in OTP_CONTEXT_RE.finditer(combined):
        candidate = m.group(1).strip()
        if candidate.lower() in ("code", "here", "this", "your", "email", "below", "above", "sent", "link", "from", "enter", "continue"):
            continue
        if any(c.isdigit() for c in candidate) or (candidate.isupper() and 6 <= len(candidate) <= 10):
            code = candidate
            break
    if not code and re.search(r"verif|security|code|c[oó]digo|otp|passcode|confirm", subject + body[:400], re.I):
        m = OTP_FALLBACK_DIGIT_RE.search(combined)
        if m:
            code = m.group(1)
    urls = []
    for raw in URL_RE.findall(body or ""):
        clean = raw.rstrip(".,;:!?\"'")
        if clean not in urls and not LINK_NOISE_RE.search(clean):
            urls.append(clean)
    urls.sort(key=lambda u: (0 if LINK_PRIORITY_RE.search(u) else 1, len(u)))
    return {"code": code, "links": urls[:10]}


def _strip_html(raw: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", raw or "")))


class AtsAuthService:
    @staticmethod
    def ensure_table() -> None:
        _ensure_table()

    @staticmethod
    def get_or_create_account(url_or_domain: str, email: Optional[str] = None) -> Dict[str, Any]:
        key = site_key_for(url_or_domain)
        host = (urlparse(url_or_domain).hostname or url_or_domain or key).lower().removeprefix("www.")
        resolved_email = (email or os.getenv("CANDIDATE_EMAIL") or "pjaragaojr@gmail.com").strip()
        try:
            row = _one("SELECT * FROM public.automation_site_accounts WHERE site_key = %s", (key,))
        except Exception:
            _ensure_table()
            row = _one("SELECT * FROM public.automation_site_accounts WHERE site_key = %s", (key,))
        if row:
            _rows("UPDATE public.automation_site_accounts SET last_used_at = NOW() WHERE id = %s", (row["id"],))
            return {
                "site_key": row["site_key"],
                "domain": row["domain"],
                "email": row["email"],
                "password": row["password"],
                "status": row["status"],
                "notes": row["notes"],
                "is_new": False,
            }
        pwd = generate_password()
        AtsAuthService._tell_password(host, resolved_email, pwd, "conta nova")
        created = _one(
            """
            INSERT INTO public.automation_site_accounts (site_key, domain, email, password, status)
            VALUES (%s, %s, %s, %s, 'pending')
            ON CONFLICT (site_key) DO UPDATE SET last_used_at = NOW(), updated_at = NOW()
            RETURNING *
            """,
            (key, host[:255], resolved_email, pwd),
        )
        return {
            "site_key": created["site_key"],
            "domain": created["domain"],
            "email": created["email"],
            "password": created["password"],
            "status": created["status"],
            "notes": created["notes"],
            "is_new": True,
        }

    @staticmethod
    def _tell_password(domain: str, email: str, password: str, why: str) -> None:
        """You asked for every portal password the system creates or changes on WhatsApp (Lolo), each time it changes."""
        try:
            import hashlib
            from app.services.bot_service import BotService
            BotService.notify("site_password", f"🔐 Senha de portal ({why})\nSite: {domain}\nE-mail: {email}\nSenha: {password}",
                              {"domain": domain, "email": email}, urgent=False,
                              key=f"pwd:{domain}:{hashlib.sha256(password.encode()).hexdigest()[:12]}")
        except Exception as e:   # the account works anyway; you just were not told
            import logging
            logging.getLogger("ats_auth").warning("password notice failed for %s: %s", domain, e)

    @staticmethod
    def new_password(url_or_domain: str, email: Optional[str] = None) -> Dict[str, Any]:
        """A fresh password for a password reset (portals refuse the old one): saved, and sent to you."""
        acc = AtsAuthService.get_or_create_account(url_or_domain, email=email)
        return AtsAuthService.update_account(url_or_domain, status="reset", password=generate_password(), email=email,
                                             notes=(acc.get("notes") or "")[:900] or None)

    @staticmethod
    def update_account(url_or_domain: str, status: Optional[str] = None, password: Optional[str] = None,
                       email: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        acc = AtsAuthService.get_or_create_account(url_or_domain, email=email)
        if password and password != acc.get("password"):
            AtsAuthService._tell_password(acc.get("domain") or url_or_domain, email or acc.get("email") or "", password, "senha alterada")
        row = _one(
            """
            UPDATE public.automation_site_accounts
               SET status = COALESCE(NULLIF(%s, ''), status),
                   password = COALESCE(NULLIF(%s, ''), password),
                   email = COALESCE(NULLIF(%s, ''), email),
                   notes = COALESCE(%s, notes),
                   last_used_at = NOW(),
                   updated_at = NOW()
             WHERE site_key = %s RETURNING *
            """,
            (status or "", password or "", email or "", notes, acc["site_key"]),
        )
        return {
            "site_key": row["site_key"],
            "domain": row["domain"],
            "email": row["email"],
            "password": row["password"],
            "status": row["status"],
            "notes": row["notes"],
            "is_new": False,
        }

    @staticmethod
    def ingest_verification_email(message_id: str, sender: str, subject: str, body: str,
                                  received_at: Optional[datetime] = None) -> Dict[str, Any]:
        _ensure_table()
        extracted = extract_verification(subject, body)
        row = _one(
            """
            INSERT INTO public.automation_email_verifications (message_id, sender, subject, body, code, links, received_at)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s, NOW()))
            ON CONFLICT (message_id) DO UPDATE SET
                code = CASE WHEN EXCLUDED.code <> '' THEN EXCLUDED.code ELSE automation_email_verifications.code END,
                links = CASE WHEN jsonb_array_length(EXCLUDED.links) > 0 THEN EXCLUDED.links ELSE automation_email_verifications.links END
            RETURNING *
            """,
            (message_id[:500], sender[:500], subject[:1000], body[:20000], extracted["code"],
             json.dumps(extracted["links"]), received_at),
        )
        return row

    @staticmethod
    def _pull_imap(since_dt: datetime, query_hint: str) -> List[Dict[str, Any]]:
        if not (settings.GMAIL_ADDRESS and settings.GMAIL_APP_PASSWORD):
            return []
        found = []
        with imaplib.IMAP4_SSL(settings.GMAIL_IMAP_HOST) as box:
            box.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
            box.select("INBOX", readonly=True)
            typ, data = box.search(None, "SINCE", since_dt.strftime("%d-%b-%Y"))
            if typ != "OK" or not data or not data[0]:
                return []
            for num in data[0].split()[-25:]:
                typ, parts = box.fetch(num, "(BODY.PEEK[]<0.150000>)")
                if typ != "OK" or not parts or not isinstance(parts[0], tuple):
                    continue
                msg = email.message_from_bytes(parts[0][1], policy=email.policy.default)
                subject = str(msg.get("Subject") or "")
                sender = str(msg.get("From") or "")
                mid = (msg.get("Message-ID") or f"imap:{num.decode()}").strip()
                part = msg.get_body(preferencelist=("plain", "html"))
                body = part.get_content() if part else ""
                if part and part.get_content_type() == "text/html":
                    body = _strip_html(body)
                try:
                    rec = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else datetime.now(timezone.utc)
                except (TypeError, ValueError):
                    rec = datetime.now(timezone.utc)
                if rec.tzinfo is None:
                    rec = rec.replace(tzinfo=timezone.utc)
                row = AtsAuthService.ingest_verification_email(mid, sender, subject, body, rec)
                found.append(row)
        return found

    @staticmethod
    def find_verification(query_hint: str = "", since_seconds: int = 900, wait_seconds: int = 0) -> Dict[str, Any]:
        """Look for a recent verification code / confirmation link matching query_hint in DB (+ IMAP if configured)."""
        _ensure_table()
        deadline = time.monotonic() + max(0, min(int(wait_seconds or 0), 90))
        since_dt = datetime.now(timezone.utc) - timedelta(seconds=max(60, min(int(since_seconds or 900), 86400)))
        tokens = [t.lower() for t in re.findall(r"[a-z0-9]{3,}", query_hint or "") if t.lower() not in ("com", "org", "net", "www", "http", "https")]
        while True:
            try:
                AtsAuthService._pull_imap(since_dt, query_hint)
            except Exception as e:
                log.debug("imap verification poll skipped: %s", e)
            rows = _rows(
                """
                SELECT * FROM public.automation_email_verifications
                 WHERE received_at >= %s
                 ORDER BY received_at DESC, id DESC LIMIT 30
                """,
                (since_dt,),
            )
            for row in rows:
                hay = f"{row.get('sender', '')} {row.get('subject', '')} {row.get('body', '')[:2000]}".lower()
                if tokens and not any(tok in hay for tok in tokens):
                    continue
                if row.get("code") or row.get("links"):
                    return {
                        "found": True,
                        "source": "backend",
                        "sender": row.get("sender"),
                        "subject": row.get("subject"),
                        "code": row.get("code") or "",
                        "links": row.get("links") or [],
                        "body_excerpt": (row.get("body") or "")[:1200],
                        "received_at": row["received_at"].isoformat() if row.get("received_at") else None,
                    }
            if time.monotonic() >= deadline:
                return {"found": False, "code": "", "links": [], "message": "Nenhum código ou link de verificação encontrado"}
            time.sleep(3)
