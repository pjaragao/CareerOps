"""Deterministic form of the resume: the contact line and the characters an ATS (applicant tracking system) trips on.

What the writer (an AI) is bad at is done here in code, every time a resume is saved: the contact line is rebuilt from the
profile (real phone, e-mail, LinkedIn and GitHub as links that look like links, the job's portfolio link), and characters that
many ATS parsers misread (Unicode minus, arrows, curly quotes, en/em dashes) become plain ASCII. The content of the resume
is never touched. Idempotent: running it twice gives the same text.
"""
import re
from typing import Dict, List, Optional

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# a phone with digits (a real one or the placeholder 00 00000-0000); never a year range or a version
PHONE_RE = re.compile(r"^\s*(?:\+?\d{1,3}\s*)?(?:\(?\d{2}\)?\s*)?\d{4,5}[-\s]?\d{4}\s*$")
PLACEHOLDER_PHONE_RE = re.compile(r"(?:\+?55\s*)?\(?0{2}\)?\s*0{4,5}[-\s]?0{4}|\b0{2}\s+0{4,5}-0{4}\b")
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w%-]+", re.I)
GITHUB_RE = re.compile(r"github\.com/[\w-]+", re.I)
MD_LINK_RE = re.compile(r"^\[(?P<text>[^\]]*)\]\((?P<url>[^)]*)\)$")

REPLACEMENTS = {
    "−": "-",   # minus sign
    "–": "-", "—": "-", "‒": "-", "―": "-",   # en dash, em dash, figure dash, horizontal bar
    "→": "->", "⇒": "->", "←": "<-",
    "≥": ">=", "≤": "<=", "×": "x", "≠": "!=",
    "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...",
    " ": " ", " ": " ", " ": " ",
    "​": "", "‌": "", "‍": "", "﻿": "",
    "•": "-", "●": "-", "▪": "-", "‣": "-",
}
BULLET_AT_START = re.compile(r"^(\s*)[•●▪‣◦⁃]\s+")
# characters that are never safe in an ATS-bound resume (emoji, pictographs, box drawing)
RISKY = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿─-╿️]")


def ascii_clean(text: str) -> str:
    text = BULLET_AT_START.sub(lambda m: f"{m.group(1)}- ", text.replace("\r\n", "\n"))
    for src, dst in REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = RISKY.sub("", text)
    return re.sub(r"[ \t]{2,}(?=\S)", lambda m: m.group(0) if m.string[:m.start()].endswith("\n") else " ", text)


def _personal() -> Dict[str, str]:
    """The profile's contact data (live profile in the database); empty when unavailable."""
    try:
        from app.services.profile_service import ProfileService
        data = (ProfileService.get_profile() or {}).get("data") or {}
        return {k: str(v or "").strip() for k, v in (data.get("personal") or {}).items()}
    except Exception:
        return {}


def _strip_scheme(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url.strip().rstrip("/"))


def contact_line_index(lines: List[str]) -> Optional[int]:
    for i, line in enumerate(lines[:15]):
        if EMAIL_RE.search(line) and not line.lstrip().startswith("#"):
            return i
    return None


def _segments(line: str) -> List[str]:
    """The contact line split by '|', keeping a markdown link whole."""
    parts, depth, cur = [], 0, ""
    for ch in line:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "|" and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    return [p for p in parts if p]


def rebuild_contact(line: str, personal: Dict[str, str], portfolio_link: Optional[str], portuguese: bool = False) -> str:
    """Location first (whatever is not a contact item stays), then e-mail, phone, LinkedIn, GitHub and the portfolio link."""
    others: List[str] = []
    email = phone = linkedin = github = ""
    for seg in _segments(line):
        text = (MD_LINK_RE.match(seg).group("text") if MD_LINK_RE.match(seg) else seg).strip()
        if "portf" in seg.lower() and ("vercel.app" in seg.lower() or MD_LINK_RE.match(seg)):
            continue   # rebuilt below from the job's link
        if EMAIL_RE.search(text):
            email = EMAIL_RE.search(text).group(0)
        elif LINKEDIN_RE.search(text):
            linkedin = LINKEDIN_RE.search(text).group(0)
        elif GITHUB_RE.search(text):
            github = GITHUB_RE.search(text).group(0)
        elif PHONE_RE.match(text) or PLACEHOLDER_PHONE_RE.search(text):
            phone = text
        else:
            others.append(seg)
    email = personal.get("email") or email
    real_phone = personal.get("phone", "")
    if real_phone and not PLACEHOLDER_PHONE_RE.search(real_phone):
        phone = real_phone   # the live profile wins over a placeholder the writer copied from the base resume
    linkedin = _strip_scheme(personal.get("linkedin") or linkedin)
    github = _strip_scheme(personal.get("github") or github)
    items = list(others)
    if email:
        items.append(email)
    if phone:
        items.append(phone)
    if linkedin:
        items.append(f"[{linkedin}](https://www.{linkedin})")
    if github:
        items.append(f"[{github}](https://{github})")
    if portfolio_link:
        label = "Portfólio" if portuguese else "Portfolio"
        items.append(f"[{label}: pjaragao-portfolio.vercel.app]({portfolio_link})")
    return " | ".join(items)


PT_HEADING = re.compile(r"^##\s+(resumo|experi[eê]ncia|forma[cç][aã]o|compet[eê]ncias|idiomas)", re.I | re.M)


def is_portuguese(markdown: str) -> bool:
    return bool(PT_HEADING.search(markdown or ""))


def normalize(markdown: str, portfolio_link: Optional[str] = None, portuguese: bool = False,
              personal: Optional[Dict[str, str]] = None) -> str:
    if not markdown or not markdown.strip():
        return markdown
    portuguese = portuguese or is_portuguese(markdown)
    text = ascii_clean(markdown)
    lines = text.split("\n")
    i = contact_line_index(lines)
    if i is not None:
        lines[i] = rebuild_contact(lines[i], personal if personal is not None else _personal(), portfolio_link, portuguese)
    return "\n".join(lines)
