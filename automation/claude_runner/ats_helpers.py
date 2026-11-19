"""Helpers for external ATS runs: runtime secrets, ATS host policy, email OTP polling,
persistent site credentials, Playwright MCP readiness checks, and S22 micro-tasks.
"""
from __future__ import annotations

import base64
import fcntl
import json
import os
import re
import shutil
import subprocess
import tempfile
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
    if op == "new_password":
        payload["new_password"] = True
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


def _content_guard() -> Dict[str, Any]:
    """The NDA rules (config/automation.yml content_guard): topics for the prompt, patterns that refuse a draft."""
    path = Path(__file__).resolve().parents[2] / "config" / "automation.yml"
    try:
        import yaml
        guard = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("content_guard") or {}
    except Exception:
        guard = {}
    return {"topics": [str(t) for t in guard.get("topics") or []],
            "patterns": [re.compile(p, re.I) for p in guard.get("patterns") or []]}


ASK_WAIT_SECONDS = 600   # how long the agent waits, form open, for your WhatsApp answer


def ask_candidate(action_id: Any, question: str, options: Optional[list], field_type: str, env: Dict[str, str],
                  wait_seconds: int = ASK_WAIT_SECONDS, poll: int = 10) -> Dict[str, Any]:
    """A required question nothing answers: Lolo asks the candidate on WhatsApp and this waits for the answer
    (2026-11-16). {answer} to type as given; {answer: null, ...} when there is none (night, no reply in time)."""
    if not action_id or not (question or "").strip():
        return {"answer": None, "note": "no question or no task"}
    asked = _api_call(f"/automation/actions/{int(action_id)}/ask",
                      {"question": question[:1000], "options": [str(o)[:200] for o in (options or [])][:30],
                       "field_type": (field_type or "text")[:20]}, env)
    if asked.get("answer"):
        return {"answer": asked["answer"], "source": asked.get("source") or "candidate"}
    qid = asked.get("question_id")
    if not qid:
        return {"answer": None, "note": f"the candidate cannot be asked now ({asked.get('unavailable') or 'no answer from CareerOps'}): "
                                        "return needs_user with this question"}
    raw_base = (env.get("CAREEROPS_API_BASE") or env.get("CAREEROPS_API_URL") or "http://127.0.0.1:8005/api").rstrip("/")
    api_base = raw_base if raw_base.endswith("/api") else f"{raw_base}/api"
    deadline = time.monotonic() + max(0, wait_seconds)
    while time.monotonic() < deadline:
        time.sleep(poll)
        req = urllib.request.Request(f"{api_base}/automation/live-questions/{int(qid)}",
                                     headers={"X-CareerOps-Token": env.get("CAREEROPS_WORKER_TOKEN") or ""})
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                got = json.loads(res.read().decode("utf-8") or "{}")
        except (OSError, ValueError):
            continue
        if got.get("answer"):
            return {"answer": got["answer"], "source": "candidate (WhatsApp)"}
    return {"answer": None, "note": f"no answer within {wait_seconds // 60} min: return needs_user with this question "
                                    "(the candidate's later answer sends the form back to the queue)"}


def lookup_answer(question: str, env: Dict[str, str]) -> Dict[str, Any]:
    raw_base = (env.get("CAREEROPS_API_BASE") or env.get("CAREEROPS_API_URL") or "http://127.0.0.1:8005/api").rstrip("/")
    api_base = raw_base if raw_base.endswith("/api") else f"{raw_base}/api"
    token = env.get("CAREEROPS_WORKER_TOKEN") or ""
    if not token or not question.strip():
        return {"saved": [], "mapped": None}
    url = f"{api_base}/automation/answers/lookup?q={urllib.parse.quote(question[:500])}"
    req = urllib.request.Request(url, headers={"X-CareerOps-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError) as e:
        return {"saved": [], "mapped": None, "error": str(e)[:200]}


def _cache_key(company: str, question: str) -> str:
    norm = lambda t: re.sub(r"[^a-z0-9]+", "-", str(t or "").lower()).strip("-")
    return f"answer:{norm(company)}:{norm(question)}"[:300]


def _text_cache(env: Dict[str, str], key: str, text: Optional[str] = None) -> Optional[str]:
    """GET (text None) or PUT the backend's text cache; None when unavailable."""
    raw_base = (env.get("CAREEROPS_API_BASE") or env.get("CAREEROPS_API_URL") or "http://127.0.0.1:8005/api").rstrip("/")
    api_base = raw_base if raw_base.endswith("/api") else f"{raw_base}/api"
    token = env.get("CAREEROPS_WORKER_TOKEN") or ""
    if not token:
        return None
    url = f"{api_base}/automation/text-cache/{urllib.parse.quote(key, safe='')}"
    data = json.dumps({"kind": "answer", "text": text}).encode("utf-8") if text is not None else None
    req = urllib.request.Request(url, data=data, method="PUT" if text is not None else "GET",
                                 headers={"X-CareerOps-Token": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return (json.loads(r.read().decode("utf-8")) or {}).get("text")
    except (urllib.error.URLError, ValueError):
        return None


def write_answer(question: str, context: Dict[str, Any], env: Dict[str, str]) -> Dict[str, Any]:
    """An open motivation answer ("Why do you want to work at X?") written by Claude Sonnet 5.5 at HIGH effort through the Claude
    CLI, from the job and the candidate's resume. Sent as returned, no approval (the candidate's decision of 2026-11-15)."""
    guard = _content_guard()
    job = (context or {}).get("job") or {}
    key = _cache_key(job.get("company") or "", question) if job.get("company") else ""
    cached = _text_cache(env, key) if key else None
    if cached and not any(p.search(cached) for p in guard["patterns"]):
        return {"text": cached, "cached": True}   # token plan, phase 3: the same company asked the same before
    resume = str((context or {}).get("resume_markdown") or "")[:9000]
    facts = json.dumps((context or {}).get("facts") or {}, ensure_ascii=False, default=str)[:3000]
    prompt = (
        "Write the answer to ONE application-form question, in first person, as the candidate.\n"
        "Tone: between informal and formal, warm, with real enthusiasm. Concrete (the company, the role, what the candidate would bring), "
        "no clichés, no flattery, no bullet lists. 90-170 words unless the form limits the length (obey the limit).\n"
        "Write in the language of the question. Use ONLY facts from the resume and facts below; never invent employers, numbers or "
        "tools. Never mention these topics: " + "; ".join(guard["topics"]) + ". Output only the answer text, nothing else.\n\n"
        f"QUESTION: {question}\nJOB: {job.get('job_title') or ''} at {job.get('company') or ''} ({job.get('location') or ''})\n"
        f"JOB URL: {job.get('url') or ''}\n\nCANDIDATE FACTS:\n{facts}\n\nRESUME:\n{resume}\n"
    )
    cmd = [os.environ.get("CLAUDE_BIN") or shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude"),
           "-p", prompt, "--model", "claude-sonnet-5-5", "--effort", "high", "--tools", "", "--no-session-persistence",
           "--output-format", "json"]
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("CAREEROPS_")}
    with tempfile.TemporaryDirectory(prefix="write-answer-") as cwd:
        done = subprocess.run(cmd, cwd=cwd, env=clean_env, capture_output=True, text=True, timeout=300)
    try:
        data = json.loads(done.stdout)
    except ValueError:
        return {"error": f"claude exit {done.returncode}"}
    text = str(data.get("result") or "").strip()
    if data.get("is_error") or not text:
        return {"error": "empty answer"}
    if any(p.search(text) for p in guard["patterns"]):
        return {"error": "the draft mentioned a forbidden term; call again"}
    if key:
        _text_cache(env, key, text)
    return {"text": text}


CAPTCHA_SOLVE_TIMEOUT = 400   # worker limit 200 s (+45 s waiting for another tab); the pre-2026-11-19-night worker took up to 360 s


def solve_captcha(url: str, context: Dict[str, Any], env: Dict[str, str]) -> Dict[str, Any]:
    """The worker's CAPTCHA solver (worker/captcha_server.py, 127.0.0.1:8940 on this host) on the company-site browser.
    At most 3 calls per task: a challenge that keeps coming back is a site that wants a person."""
    tries = int(context.get("_captcha_tries") or 0)
    if tries >= 3:
        return {"solved": False, "error": "already tried 3 times in this task: stop with needs_user (CAPTCHA)"}
    context["_captcha_tries"] = tries + 1
    port = int(env.get("CAREEROPS_CAPTCHA_PORT") or 8940)
    token = env.get("CAREEROPS_WORKER_TOKEN") or ""
    req = urllib.request.Request(f"http://127.0.0.1:{port}/solve", data=json.dumps({"url": url[:500]}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-CareerOps-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=CAPTCHA_SOLVE_TIMEOUT) as res:
            out = json.loads(res.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        out = {"solved": False, "error": f"solver HTTP {e.code}"}
    except (OSError, ValueError) as e:
        out = {"solved": False, "error": f"solver unreachable: {e}"}
    if out.get("busy"):   # nothing was tried: it does not count as one of the 3
        context["_captcha_tries"] = tries
    action_id = context.get("_action_id")
    if action_id:
        try:
            _api_call(f"/automation/actions/{action_id}/events", {"source": "claude", "event": "captcha_auto",
                                                                  "data": {k: out.get(k) for k in ("solved", "kind", "how", "error")}}, env)
        except Exception:
            pass
    return out


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
            "name": "solve_captcha",
            "description": "A CAPTCHA (reCAPTCHA, hCaptcha, Cloudflare Turnstile) on the company form: the CareerOps solver passes it in the browser (checkbox, audio, image model; up to ~6 min). Pass the current page URL. Returns {solved, kind, how|error}. After it returns, take one snapshot and continue. Call it at most twice per page.",
            "inputSchema": {"type": "object", "properties": {"url": {"type": "string", "description": "The page the CAPTCHA is on"}}},
        },
        {
            "name": "wait_for_human",
            "description": "LIVE CAPTCHA SESSION ONLY: tells the candidate (WhatsApp) that a CAPTCHA is on the screen and waits up to `seconds` (max 120) while they solve it in the browser. Take a snapshot after it returns.",
            "inputSchema": {"type": "object", "properties": {"seconds": {"type": "integer"}}},
        },
        {
            "name": "lookup_answer",
            "description": "The candidate's saved answers closest to one form question, and the value the deterministic mapper gives for it. Use before stopping on a question the dossier does not answer.",
            "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
        },
        {
            "name": "ask_candidate",
            "description": "A REQUIRED form question that the dossier, standing answers and lookup_answer do not answer: the candidate is asked on WhatsApp and this waits (up to 10 min) with the form open. Returns {answer} to fill in exactly as given; {answer: null} means stop with needs_user and this question. Never for open motivation texts (use write_answer).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question exactly as the form shows it"},
                    "options": {"type": "array", "items": {"type": "string"}, "description": "The form's options, if it is a choice"},
                    "field_type": {"type": "string", "enum": ["text", "select", "radio", "checkbox", "number", "date"]},
                },
                "required": ["question"],
            },
        },
        {
            "name": "write_answer",
            "description": "Write an open motivation answer (e.g. 'Why do you want to work at X?', 'Why are you interested in us?') for the form. Uses the job and the resume; returns {text} to paste as is, no approval needed.",
            "inputSchema": {
                "type": "object",
                "properties": {"question": {"type": "string", "description": "The exact question, with any length limit"}},
                "required": ["question"],
            },
        },
        {
            "name": "site_account",
            "description": "Get, create, or update persistent login credentials for an ATS portal in CareerOps.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "enum": ["get", "get_or_create", "update", "new_password"],
                           "description": "new_password: a fresh password for a reset (saved; the candidate is told)"},
                    "domain": {"type": "string", "description": "ATS hostname"},
                    "email": {"type": "string"},
                    "password": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["op", "domain"],
            },
        },
    ]

    def __init__(self, env: Dict[str, str], on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                 context: Optional[Dict[str, Any]] = None):
        self.env = env
        self.context = context or {}
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
        if name == "solve_captcha":
            return solve_captcha(str(args.get("url") or ""), self.context, self.env)
        if name == "wait_for_human":
            action_id = (self.context or {}).get("_action_id")
            if action_id and not self.context.get("_told"):
                _api_call(f"/automation/actions/{action_id}/events", {"source": "claude", "event": "captcha_waiting", "data": {}}, self.env)
                self.context["_told"] = True
            seconds = max(10, min(int(args.get("seconds") or 60), 120))
            time.sleep(seconds)
            return {"waited": seconds}
        if name == "ask_candidate":
            return ask_candidate((self.context or {}).get("_action_id"), str(args.get("question") or ""), args.get("options") or [],
                                 str(args.get("field_type") or "text"), self.env)
        if name == "lookup_answer":
            return lookup_answer(str(args.get("question") or ""), self.env)
        if name == "write_answer":
            return write_answer(str(args.get("question") or ""), self.context, self.env)
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

    def rpc(self, req: Dict[str, Any]) -> Tuple[int, Optional[Dict[str, Any]]]:
        """One JSON-RPC request -> (HTTP status, body). Shared by the per-run server below and the Hermes bridge."""
        method = req.get("method")
        req_id = req.get("id")
        if req_id is None and str(method).startswith("notifications/"):
            return 202, None
        if method == "initialize":
            return 200, {"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": (req.get("params") or {}).get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}}, "serverInfo": {"name": "careerops", "version": "1.0"}}}
        if method == "tools/list":
            return 200, {"jsonrpc": "2.0", "id": req_id, "result": {"tools": self.TOOLS}}
        if method == "ping":
            return 200, {"jsonrpc": "2.0", "id": req_id, "result": {}}
        if method == "tools/call":
            params = req.get("params") or {}
            try:
                res = self._dispatch(params.get("name", ""), params.get("arguments") or {})
                return 200, {"jsonrpc": "2.0", "id": req_id,
                             "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": False}}
            except Exception as exc:
                return 200, {"jsonrpc": "2.0", "id": req_id,
                             "result": {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True}}
        return 200, {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

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
                code, payload = parent.rpc(req)
                self._send_json(code, payload)

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
