"""Helpers for external ATS runs: runtime secrets, ATS host policy, email OTP polling,
persistent site credentials, Playwright MCP readiness checks, and S22 micro-tasks.
"""
from __future__ import annotations

import base64
import fcntl
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parseaddr
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


DEFAULT_ENV_FILES = (
    os.path.expanduser("~/.config/careerops/runner.env"),
    "/home/paulojr/lolo-bot/data/.env",
)
DEFAULT_GMAIL_TOKEN = Path("/home/paulojr/lolo-bot/data/google_token.json")
DEFAULT_GMAIL_SECRET = Path("/home/paulojr/lolo-bot/data/google_client_secret.json")
DEFAULT_S22_URL = "http://192.168.1.29:8081/v1"
DEFAULT_S22_MODEL = "gemma-4-E2B-litert"
DEFAULT_S22_KEY_FILE = Path("/mnt/c/Users/paulojr/S22/llm-api-key.txt")
S22_LOCK_PATH = Path("/tmp/s22-llm.lock")
GMAIL_LOCK_PATH = Path("/tmp/careerops-gmail.lock")

KNOWN_ATS_EXACT_HOSTS = frozenset({
    "jobs.ashbyhq.com",
    "app.ashbyhq.com",
    "boards.greenhouse.io",
    "boards.eu.greenhouse.io",
    "job-boards.greenhouse.io",
    "job-boards.eu.greenhouse.io",
    "jobs.lever.co",
    "jobs.eu.lever.co",
    "jobs.smartrecruiters.com",
    "careers.smartrecruiters.com",
    "apply.workable.com",
    "jobs.workable.com",
    "app.dover.com",
    "app.dover.io",
    "jobs.gem.com",
    "app.loxo.co",
    "app.eu.loxo.co",
    "wellfound.com",
    "www.wellfound.com",
    "ats.rippling.com",
    "apply.rippling.com",
    "app.rippling.com",
    "builtin.com",
    "www.builtin.com",
})

KNOWN_ATS_SUFFIXES = (
    ".greenhouse.io",
    ".lever.co",
    ".ashbyhq.com",
    ".myworkdayjobs.com",
    ".myworkdaysite.com",
    ".smartrecruiters.com",
    ".icims.com",
    ".breezy.hr",
    ".workable.com",
    ".bamboohr.com",
    ".recruitee.com",
    ".teamtailor.com",
    ".personio.de",
    ".personio.com",
    ".jobvite.com",
    ".successfactors.com",
    ".successfactors.eu",
    ".taleo.net",
    ".oraclecloud.com",
    ".dayforcehcm.com",
    ".ultipro.com",
    ".paylocity.com",
    ".paycomonline.net",
    ".adp.com",
    ".pinpointhq.com",
    ".dover.com",
    ".rippling.com",
    ".hibob.com",
    ".loxo.co",
    ".gupy.io",
    ".solides.com",
    ".inhire.app",
    ".kenoby.com",
    ".vagas.com.br",
    ".infojobs.com.br",
    ".compleo.com.br",
    ".quickin.io",
    ".jazzhr.com",
    ".applytojob.com",
    ".fountain.com",
    ".hirehive.com",
    ".darwinbox.com",
    ".zohorecruit.com",
    ".gem.com",
    ".comeet.co",
    ".keka.com",
    ".kula.ai",
)

BLOCKED_ON_ATS_SUFFIXES = ("linkedin.com", "lnkd.in")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_HREF_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
_URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)

OTP_PATTERNS = (
    re.compile(
        r"(?:security\s+code|verification\s+code|confirmation\s+code|access\s+code|paste\s+this\s+code|c[oó]digo)"
        r"[^:\n]{0,80}:\s*([A-Za-z0-9]{4,10})\b",
        re.I,
    ),
    re.compile(
        r"(?:security\s+code|verification\s+code|confirmation\s+code|access\s+code|"
        r"one[- ]time\s+(?:code|passcode|password)|passcode|otp|c[oó]digo(?:\s+de\s+(?:verifica[çc][aã]o|acesso|seguran[çc]a))?)"
        r"[^a-z0-9]{0,24}([A-Z0-9]{4,10})\b",
        re.I,
    ),
    re.compile(r"\b(\d{6,8})\b\s+(?:is your|é o seu)\s+(?:code|c[oó]digo)", re.I),
    re.compile(r"(?:enter|use|type|digite|informe)[^.\n]{0,40}\b([A-Z0-9]{6,8})\b", re.I),
)
_OTP_DIGIT_FALLBACK_RE = re.compile(r"(?:^|[\s:>])(\d{6,8})(?=[\s.<]|$)")
LINK_KEYWORDS = (
    "verify", "confirm", "activate", "magic", "login", "sign-in", "signin",
    "reset", "password", "token=", "code=", "auth", "verify-email", "challenge",
)


def parse_env_file(path: Path) -> Dict[str, str]:
    """Parses KEY=VALUE lines from an env file without executing shell commands."""
    out: Dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return out
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_runtime_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Merges caller env over default careerops / lolo-bot env files cleanly."""
    merged: Dict[str, str] = {}
    raw_files = (base_env or os.environ).get("CAREEROPS_ENV_FILES")
    env_files = [Path(p) for p in raw_files.split(":") if p] if raw_files is not None else [Path(p) for p in DEFAULT_ENV_FILES]
    for path in reversed(env_files):
        merged.update(parse_env_file(path))
    merged.update(os.environ)
    if base_env:
        merged.update(base_env)
    if not merged.get("S22_LLM_API_KEY"):
        key_file = Path(merged.get("S22_LLM_KEY_FILE") or str(DEFAULT_S22_KEY_FILE))
        if key_file.is_file():
            try:
                merged["S22_LLM_API_KEY"] = key_file.read_text(encoding="utf-8").strip()
            except OSError:
                pass
    return merged


_SECOND_LEVEL_TLDS = {"com", "co", "org", "net", "edu", "gov", "ac", "ne", "or"}


def _registrable_domain(host: str) -> str:
    """Returns the registrable base domain (handling 2-label ccTLDs like .com.br / .co.uk)."""
    clean = host.lower().strip(".")
    parts = [p for p in clean.split(".") if p]
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in _SECOND_LEVEL_TLDS:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return clean


def allowed_hosts_for_action(action: Dict[str, Any]) -> set:
    """Computes initially seeded allowed hostnames for the run's action."""
    hosts = set()
    lane = action.get("lane")
    for raw_url in (action.get("target_url"), ((action.get("dossier") or {}).get("job") or {}).get("url")):
        host = urllib.parse.urlparse(str(raw_url or "")).hostname
        if not host:
            continue
        lower = host.lower().rstrip(".")
        if lane == "ats":
            if any(lower == b or lower.endswith("." + b) for b in BLOCKED_ON_ATS_SUFFIXES):
                continue
            hosts.add(lower)
            reg = _registrable_domain(lower)
            if reg:
                hosts.add(reg)
        else:
            hosts.add(lower)
    if lane == "ats":
        hosts |= set(KNOWN_ATS_EXACT_HOSTS)
    else:
        hosts |= {"www.linkedin.com", "linkedin.com"}
    return hosts


def is_host_allowed(hostname: Optional[str], lane: str, seeded_hosts: Iterable[str]) -> bool:
    """Checks whether navigating to hostname is permitted for this lane and target."""
    if not hostname:
        return False
    host = hostname.lower().rstrip(".")
    if lane == "ats":
        if any(host == b or host.endswith("." + b) for b in BLOCKED_ON_ATS_SUFFIXES):
            return False
        if any(host == s or host.endswith("." + s) for s in seeded_hosts):
            return True
        return any(host == suf.lstrip(".") or host.endswith(suf) for suf in KNOWN_ATS_SUFFIXES)
    return host in seeded_hosts


def domain_candidates(domain: str) -> List[str]:
    """Extracts meaningful keywords from a domain for Gmail search filtering."""
    host = urllib.parse.urlparse(domain if "://" in domain else f"https://{domain}").hostname or domain
    host = host.lower().strip(".")
    parts = [p for p in host.split(".") if p and p not in ("www", "jobs", "careers", "apply", "boards", "app", "eu", "us", "com", "io", "co", "net", "org", "br")]
    out = [host]
    for p in parts:
        if len(p) >= 3 and p not in out:
            out.append(p)
    return out


def extract_verification_text(subject: str, body_text: str) -> Tuple[str, str]:
    """Deterministically extracts OTP code and verification/reset URL from email text."""
    combined = f"{subject}\n{body_text}"
    code = ""
    for idx, pat in enumerate(OTP_PATTERNS):
        m = pat.search(combined)
        if m:
            candidate = m.group(1).strip()
            has_digit = any(c.isdigit() for c in candidate)
            is_code_alpha = len(candidate) >= 6 and (
                candidate.isupper() or (idx == 0 and not candidate.istitle())
            )
            if has_digit or is_code_alpha:
                code = candidate
                break
    if not code and any(kw in combined.lower() for kw in ("code", "código", "codigo", "verify", "verificação", "verificacao")):
        m = _OTP_DIGIT_FALLBACK_RE.search(combined)
        if m:
            code = m.group(1).strip()
    link = ""
    for url in _URL_RE.findall(combined):
        cleaned = url.rstrip(".,;:)")
        low = cleaned.lower()
        if any(ext in low for ext in (".png", ".jpg", ".gif", ".css", "unsubscribe")):
            continue
        if any(kw in low for kw in LINK_KEYWORDS):
            link = cleaned
            break
    return code, link


def _html_to_text(html: str) -> str:
    def repl(m: re.Match) -> str:
        href = m.group(1)
        label = _TAG_RE.sub("", m.group(2)).strip()
        return f" {label} ({href}) " if href.startswith("http") else f" {label} "
    text = _HREF_RE.sub(repl, html or "")
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _extract_payload_text(payload: Dict[str, Any]) -> str:
    mime = (payload.get("mimeType") or "").lower()
    body_data = (payload.get("body") or {}).get("data")
    parts = payload.get("parts") or []
    texts: List[str] = []
    if body_data:
        try:
            raw = base64.urlsafe_b64decode(body_data + "===").decode("utf-8", "ignore")
            texts.append(_html_to_text(raw) if "html" in mime else raw)
        except Exception:
            pass
    for p in parts:
        sub = _extract_payload_text(p)
        if sub:
            texts.append(sub)
    return "\n".join(t for t in texts if t).strip()


def _json_request(url: str, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 20) -> Tuple[int, Dict[str, Any]]:
    hdrs = dict(headers or {})
    raw_body = None
    if data is not None:
        raw_body = json.dumps(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=raw_body, headers=hdrs, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "ignore")
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")
        try:
            return exc.code, json.loads(body) if body else {}
        except ValueError:
            return exc.code, {"error": body}


def _api_call(path: str, payload: Dict[str, Any], env: Dict[str, str], timeout: int = 15) -> Dict[str, Any]:
    raw_base = (env.get("CAREEROPS_API_BASE") or env.get("CAREEROPS_API_URL") or "http://127.0.0.1:8005/api").rstrip("/")
    api_base = raw_base if raw_base.endswith("/api") else f"{raw_base}/api"
    token = env.get("CAREEROPS_WORKER_TOKEN") or ""
    if not token:
        return {}
    headers = {"X-CareerOps-Token": token, "X-Automation-Worker": env.get("WORKER_ID", "claude-runner")}
    status, body = _json_request(f"{api_base}{path}", data=payload, headers=headers, timeout=timeout)
    return body if 200 <= status < 300 else {}


def _load_gmail_access_token(env: Dict[str, str]) -> Optional[str]:
    tok_path = Path(env.get("CAREEROPS_GMAIL_TOKEN_PATH") or str(DEFAULT_GMAIL_TOKEN))
    sec_path = Path(env.get("CAREEROPS_GMAIL_SECRET_PATH") or str(DEFAULT_GMAIL_SECRET))
    if not tok_path.is_file():
        return None
    GMAIL_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GMAIL_LOCK_PATH, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        tok = json.loads(tok_path.read_text(encoding="utf-8"))
        # Try refresh proactively when refresh_token + client_secret exist and expiry is unknown/near
        access_token = tok.get("access_token")
        expiry_ts = 0.0
        exp = tok.get("expiry")
        if isinstance(exp, (int, float)):
            expiry_ts = float(exp)
        elif isinstance(exp, str) and exp:
            try:
                from datetime import datetime
                expiry_ts = datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp()
            except ValueError:
                expiry_ts = 0.0
        if access_token and expiry_ts - time.time() > 120:
            return access_token
        if tok.get("refresh_token") and sec_path.is_file():
            sec = json.loads(sec_path.read_text(encoding="utf-8"))
            cfg = sec.get("installed") or sec.get("web") or sec
            form = urllib.parse.urlencode({
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "refresh_token": tok["refresh_token"],
                "grant_type": "refresh_token",
            }).encode("utf-8")
            req = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST")
            with urllib.request.urlopen(req, timeout=15) as r:
                refreshed = json.loads(r.read().decode("utf-8"))
            if refreshed.get("access_token"):
                tok["access_token"] = refreshed["access_token"]
                if refreshed.get("expires_in"):
                    tok["expires_in"] = int(refreshed["expires_in"])
                    tok["expiry"] = time.time() + int(refreshed["expires_in"])
                tmp = tok_path.with_suffix(".tmp")
                tmp.write_text(json.dumps(tok, indent=2), encoding="utf-8")
                os.chmod(tmp, 0o600)
                os.replace(tmp, tok_path)
                return tok["access_token"]
        return access_token


def _mark_read_and_archive_gmail(msg_id: str, headers: Dict[str, str]) -> bool:
    """Marks a handled verification email as read and removes it from INBOX."""
    if not msg_id:
        return False
    status, _ = _json_request(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{urllib.parse.quote(str(msg_id))}/modify",
        data={"removeLabelIds": ["UNREAD", "INBOX"]},
        headers=headers,
        timeout=15,
    )
    return 200 <= status < 300


def _search_gmail(domain: str, query: str, since_minutes: int, env: Dict[str, str]) -> List[Dict[str, Any]]:
    access_token = _load_gmail_access_token(env)
    if not access_token:
        return []
    days = max(1, (since_minutes + 1439) // 1440)
    terms = domain_candidates(domain)
    if query:
        terms.append(query)
    q_or = " OR ".join(f'"{t}"' for t in dict.fromkeys(terms[:5]))
    q_str = f"newer_than:{days}d ({q_or})" if q_or else f"newer_than:{days}d (verify OR code OR password OR otp)"
    hdrs = {"Authorization": f"Bearer {access_token}"}
    list_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?{urllib.parse.urlencode({'q': q_str, 'maxResults': 8})}"
    status, listed = _json_request(list_url, headers=hdrs, timeout=15)
    if status == 401:
        # Force refresh once
        tok_path = Path(env.get("CAREEROPS_GMAIL_TOKEN_PATH") or str(DEFAULT_GMAIL_TOKEN))
        if tok_path.is_file():
            tok = json.loads(tok_path.read_text(encoding="utf-8"))
            tok["expiry"] = 0.0
            tok_path.write_text(json.dumps(tok, indent=2), encoding="utf-8")
        access_token = _load_gmail_access_token(env)
        if not access_token:
            return []
        hdrs = {"Authorization": f"Bearer {access_token}"}
        status, listed = _json_request(list_url, headers=hdrs, timeout=15)
    if status != 200:
        return []
    cutoff_ms = int((time.time() - since_minutes * 60) * 1000)
    results: List[Dict[str, Any]] = []
    for item in (listed.get("messages") or [])[:6]:
        msg_id = item.get("id")
        if not msg_id:
            continue
        st, msg = _json_request(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=full", headers=hdrs, timeout=15)
        if st != 200:
            continue
        internal_ms = int(msg.get("internalDate") or 0)
        if internal_ms and internal_ms < cutoff_ms:
            continue
        headers_map = {h["name"].lower(): h["value"] for h in (msg.get("payload") or {}).get("headers") or [] if h.get("name")}
        subject = headers_map.get("subject", "")
        sender = parseaddr(headers_map.get("from", ""))[1] or headers_map.get("from", "")
        body_text = _extract_payload_text(msg.get("payload") or {}) or msg.get("snippet", "")
        code, link = extract_verification_text(subject, body_text)
        if not code and not link:
            continue
        results.append({
            "message_id": msg_id,
            "domain": domain,
            "sender": sender[:180],
            "subject": subject[:200],
            "code": code,
            "link": link,
            "snippet": body_text[:320],
        })
        if code or link:
            _api_call("/automation/email/verification/ingest", {
                "message_id": str(msg_id),
                "sender": sender[:500],
                "subject": subject[:1000],
                "body": body_text[:20000],
            }, env)
            _mark_read_and_archive_gmail(str(msg_id), hdrs)
    return results


def check_email_verification(domain: str, query: str = "", since_minutes: int = 20, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Checks Gmail first (so handled verification emails are also marked read & archived), then falls back to DB."""
    cfg = load_runtime_env(env)
    gmail_hits = _search_gmail(domain, query, since_minutes, cfg)
    if gmail_hits:
        best = gmail_hits[0]
        return {
            "found": True,
            "code": best["code"],
            "link": best["link"],
            "links": [best["link"]] if best["link"] else [],
            "subject": best["subject"],
            "sender": best["sender"],
            "snippet": best["snippet"],
            "source": "gmail",
        }
    hint = " ".join(p for p in (domain, query) if p).strip()
    db_res = _api_call("/automation/email/verification", {
        "query_hint": hint,
        "since_seconds": max(60, min(86400, int(since_minutes) * 60)),
        "wait_seconds": 0,
    }, cfg)
    if db_res.get("found"):
        links = list(db_res.get("links") or [])
        return {**db_res, "link": links[0] if links else "", "links": links}
    if cfg.get("CAREEROPS_ENV_FILES") != "" and (env or {}).get("CAREEROPS_ENV_FILES") != "":
        time.sleep(4)
        gmail_hits = _search_gmail(domain, query, since_minutes, cfg)
    if gmail_hits:
        best = gmail_hits[0]
        return {
            "found": True,
            "code": best["code"],
            "link": best["link"],
            "links": [best["link"]] if best["link"] else [],
            "subject": best["subject"],
            "sender": best["sender"],
            "snippet": best["snippet"],
            "source": "gmail",
        }
    return {"found": False, "code": "", "link": "", "links": [], "message": "No recent matching verification email found."}


def manage_site_account(op: str, domain: str, email: str = "", password: str = "", notes: str = "", env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Gets, creates, or updates persistent per-ATS credentials in CareerOps backend."""
    cfg = load_runtime_env(env)
    payload: Dict[str, Any] = {"domain": domain}
    if email:
        payload["email"] = email
    if op == "update":
        if password:
            payload["password"] = password
        if notes:
            payload["notes"] = notes
    return _api_call("/automation/site-accounts", payload, cfg)


def call_s22_micro(system_prompt: str, user_prompt: str, *, max_tokens: int = 256, env: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Calls Samsung S22 Ultra LiteRT-LM endpoint respecting 4096 ctx and concurrency=1."""
    cfg = load_runtime_env(env)
    api_key = cfg.get("S22_LLM_API_KEY") or ""
    if not api_key:
        return None
    base_url = (cfg.get("S22_LLM_BASE_URL") or DEFAULT_S22_URL).rstrip("/")
    model = cfg.get("S22_LLM_MODEL") or DEFAULT_S22_MODEL
    capped_tokens = min(int(max_tokens), 1024)
    payload = {
        "model": model,
        "stream": False,
        "temperature": 0,
        "max_tokens": capped_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {"role": "system", "content": system_prompt[:1200]},
            {"role": "user", "content": user_prompt[:7000]},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    S22_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(S22_LOCK_PATH, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        status, body = _json_request(f"{base_url}/chat/completions", data=payload, headers=headers, timeout=300)
    if status != 200:
        return None
    choices = body.get("choices") or []
    return ((choices[0].get("message") or {}).get("content") or "").strip() if choices else None


def probe_mcp_http(url: str, timeout: int = 8) -> bool:
    """Checks whether a Streamable HTTP Playwright MCP endpoint initializes cleanly."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "careerops-health", "version": "1.0"},
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            sid = r.headers.get("Mcp-Session-Id")
            body = r.read().decode("utf-8", "ignore")
            ok = r.status == 200 and '"result"' in body
        if sid:
            del_req = urllib.request.Request(url, headers={"Mcp-Session-Id": sid}, method="DELETE")
            try:
                urllib.request.urlopen(del_req, timeout=3).close()
            except Exception:
                pass
        return ok
    except Exception:
        return False


class CareerOpsMcpServer:
    """Ephemeral localhost Streamable HTTP MCP server exposing email & credential tools."""

    TOOLS = [
        {
            "name": "check_email",
            "description": "Search Gmail & CareerOps email store for a recent verification code (OTP), magic link, or password reset email for an ATS domain.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "ATS hostname or company domain, e.g. jobs.ashbyhq.com"},
                    "query": {"type": "string", "description": "Optional keyword (e.g. company name or subject)"},
                    "since_minutes": {"type": "integer", "description": "Look back window in minutes (default 20)"},
                },
                "required": ["domain"],
            },
        },
        {
            "name": "site_account",
            "description": "Get, create, or update persistent login credentials for an ATS portal in CareerOps.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "enum": ["get", "get_or_create", "update"]},
                    "domain": {"type": "string", "description": "ATS hostname"},
                    "email": {"type": "string"},
                    "password": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["op", "domain"],
            },
        },
    ]

    def __init__(self, env: Dict[str, str], on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        self.env = env
        self.on_tool_call = on_tool_call
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.url = ""

    def _dispatch(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if self.on_tool_call:
            self.on_tool_call(f"mcp__careerops__{name}", args)
        if name == "check_email":
            return check_email_verification(
                domain=str(args.get("domain") or ""),
                query=str(args.get("query") or ""),
                since_minutes=int(args.get("since_minutes") or 20),
                env=self.env,
            )
        if name == "site_account":
            return manage_site_account(
                op=str(args.get("op") or "get"),
                domain=str(args.get("domain") or ""),
                email=str(args.get("email") or ""),
                password=str(args.get("password") or ""),
                notes=str(args.get("notes") or ""),
                env=self.env,
            )
        raise ValueError(f"Unknown careerops MCP tool: {name}")

    def __enter__(self) -> "CareerOpsMcpServer":
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def _send_json(self, code: int, payload: Optional[Dict[str, Any]]) -> None:
                raw = json.dumps(payload).encode("utf-8") if payload is not None else b""
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Mcp-Session-Id", "careerops-local")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                if raw:
                    self.wfile.write(raw)

            def do_GET(self) -> None:
                self.send_response(405)
                self.end_headers()

            def do_DELETE(self) -> None:
                self._send_json(200, {"ok": True})

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                req = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                method = req.get("method")
                req_id = req.get("id")
                if req_id is None and str(method).startswith("notifications/"):
                    self._send_json(202, None)
                    return
                if method == "initialize":
                    self._send_json(200, {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": (req.get("params") or {}).get("protocolVersion") or "2024-11-05",
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "careerops", "version": "1.0"},
                        },
                    })
                elif method == "tools/list":
                    self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": {"tools": parent.TOOLS}})
                elif method == "tools/call":
                    params = req.get("params") or {}
                    try:
                        res = parent._dispatch(params.get("name", ""), params.get("arguments") or {})
                        self._send_json(200, {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": False},
                        })
                    except Exception as exc:
                        self._send_json(200, {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True},
                        })
                else:
                    self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}})

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        port = self._server.server_address[1]
        self.url = f"http://127.0.0.1:{port}/mcp"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
