"""A job from its link: fills title, company, location and description the way the extension's universal import does,
but from the app (no page open in the browser).

In order: the public APIs of the big ATSs (LinkedIn guest view, Greenhouse, Lever, Workable), then the schema.org
JobPosting most job pages embed for Google Jobs, then the page text read by the AI (jobs/extract.md). Nothing is saved
here: the form shows the result to review before saving."""
import html
import io
import json
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

import requests
from pypdf import PdfReader

from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor
from app.services.skill_service import SkillService

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
}
TIMEOUT = 20


class LinkError(Exception):
    """Something the person can act on (bad link, site blocked): shown as is."""


# ── HTML → text with paragraphs and bullets kept ──────────────────────────────────────────────────────────────
class _Text(HTMLParser):
    BLOCK = {"p", "div", "section", "article", "ul", "ol", "table", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "header", "footer"}
    SKIP = {"script", "style", "noscript", "svg", "template", "head", "nav", "button", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "br":
            self.out.append("\n")
        elif tag == "li":
            self.out.append("\n• ")
        elif tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK or tag == "li":
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(markup: str) -> str:
    if not markup:
        return ""
    p = _Text()
    p.feed(markup)
    text = "".join(p.out).replace("\xa0", " ")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", l).strip() for l in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n(•\s*)?\n(?=•)", "\n", text)          # no blank line inside a list
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _get(url: str, headers: dict | None = None) -> requests.Response:
    try:
        r = requests.get(url, headers=headers or HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException as e:
        raise LinkError(f"não consegui abrir o link ({e.__class__.__name__})")
    return r


def _job(title="", company="", location="", description="", **extra) -> dict:
    return {"title": (title or "").strip(), "company": (company or "").strip(), "location": (location or "").strip(),
            "description": (description or "").strip(), **{k: v for k, v in extra.items() if v}}


# ── Known job sites ───────────────────────────────────────────────────────────────────────────────────────────
def _linkedin_id(u) -> str | None:
    m = re.search(r"/jobs/view/(?:[^/]*-)?(\d{6,})", u.path)
    if m:
        return m.group(1)
    q = parse_qs(u.query)
    for key in ("currentJobId", "jobId"):
        if q.get(key) and q[key][0].isdigit():
            return q[key][0]
    return None


def _from_linkedin(job_id: str) -> dict | None:
    r = _get(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}")
    if r.status_code != 200:
        return None
    page = r.text
    def first(pattern):
        m = re.search(pattern, page, re.S)
        return html_to_text(m.group(1)) if m else ""
    desc = re.search(r'<div class="show-more-less-html__markup[^"]*">(.*?)</div>\s*<button', page, re.S) \
        or re.search(r'<div class="description__text[^"]*">(.*?)</section>', page, re.S)
    criteria = re.findall(r'<h3 class="description__job-criteria-subheader">\s*(.*?)\s*</h3>\s*<span[^>]*>\s*(.*?)\s*</span>', page, re.S)
    job = _job(
        title=first(r'<h2[^>]*top-card-layout__title[^>]*>(.*?)</h2>') or first(r'<h1[^>]*>(.*?)</h1>'),
        company=first(r'<a[^>]*topcard__org-name-link[^>]*>(.*?)</a>') or first(r'<span[^>]*topcard__flavor[^>]*>(.*?)</span>'),
        location=first(r'<span[^>]*topcard__flavor--bullet[^>]*>(.*?)</span>'),
        description=html_to_text(desc.group(1)) if desc else "",
        employment_type=next((html_to_text(v) for k, v in criteria if re.search(r"employment|emprego", k, re.I)), ""),
        seniority=next((html_to_text(v) for k, v in criteria if re.search(r"seniority|experi", k, re.I)), ""),
    )
    return job if job["title"] and job["description"] else None


def _from_greenhouse(u) -> dict | None:
    m = re.match(r"^/([^/]+)/jobs/(\d+)", u.path)
    if not m or "greenhouse.io" not in u.netloc:
        return None
    r = _get(f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}")
    if r.status_code != 200:
        return None
    d = r.json()
    return _job(d.get("title"), d.get("company_name") or m.group(1).replace("-", " ").title(),
                (d.get("location") or {}).get("name"), html_to_text(html.unescape(d.get("content") or "")))


def _from_lever(u) -> dict | None:
    m = re.match(r"^/([^/]+)/([0-9a-f-]{20,})", u.path)
    if not m or "lever.co" not in u.netloc:
        return None
    r = _get(f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}")
    if r.status_code != 200:
        return None
    d = r.json()
    parts = [d.get("descriptionPlain") or html_to_text(d.get("description") or "")]
    for block in d.get("lists") or []:
        parts.append(f"{block.get('text', '')}\n" + html_to_text(f"<ul>{block.get('content', '')}</ul>"))
    parts.append(d.get("additionalPlain") or html_to_text(d.get("additional") or ""))
    cat = d.get("categories") or {}
    return _job(d.get("text"), m.group(1).replace("-", " ").title(), cat.get("location") or ", ".join(cat.get("allLocations") or []),
                "\n\n".join(p for p in parts if p and p.strip()), employment_type=cat.get("commitment"), workplace=d.get("workplaceType"))


def _from_workable(u) -> dict | None:
    m = re.match(r"^/([^/]+)/j/([A-Za-z0-9]+)", u.path)
    if not m or "workable.com" not in u.netloc:
        return None
    r = _get(f"https://apply.workable.com/api/v1/accounts/{m.group(1)}/jobs/{m.group(2)}")
    if r.status_code != 200:
        return None
    d = r.json()
    loc = d.get("location") or {}
    parts = [html_to_text(d.get(k) or "") for k in ("description", "requirements", "benefits")]
    return _job(d.get("title"), m.group(1).replace("-", " ").title(),
                ", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x) or ("Remote" if d.get("remote") else ""),
                "\n\n".join(p for p in parts if p), employment_type=d.get("type"))


def _from_workday(u) -> dict | None:
    # https://{tenant}.wdN.myworkdayjobs.com/[en-US/]{site}/job/{location}/{title_id} → the board's JSON (cxs) API
    m = re.match(r"^(?:/[a-z]{2}-[A-Z]{2})?/([^/]+)/job/(.+?)/?$", u.path)
    if not m or "myworkdayjobs.com" not in u.netloc:
        return None
    tenant = u.netloc.split(".")[0]
    r = _get(f"https://{u.netloc}/wday/cxs/{tenant}/{m.group(1)}/job/{m.group(2)}", headers={**HEADERS, "Accept": "application/json"})
    if r.status_code != 200:
        return None
    d = (r.json() or {}).get("jobPostingInfo") or {}
    org = re.sub(r"^\d+\s+", "", ((r.json() or {}).get("hiringOrganization") or {}).get("name") or "")   # "247512 PPD Mexico"
    return _job(d.get("title"), org or tenant.replace("-", " ").title(),
                ", ".join(x for x in [d.get("location"), *(d.get("additionalLocations") or [])] if x),
                html_to_text(d.get("jobDescription") or ""), employment_type=d.get("timeType"), posted=d.get("startDate"))


# ── Pages that only show the job with JavaScript: Gotenberg's Chromium opens them like a browser ──────────────
def _rendered_text(url: str) -> str:
    try:
        r = requests.post(f"{settings.GOTENBERG_URL}/forms/chromium/convert/url", timeout=60,
                          files={k: (None, v) for k, v in {"url": url, "waitDelay": "4s", "emulatedMediaType": "screen"}.items()})
        if r.status_code != 200:
            return ""
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages[:12]).strip()
    except Exception:
        return ""


# ── schema.org JobPosting (Google Jobs markup) ────────────────────────────────────────────────────────────────
def _postings(node):
    if isinstance(node, list):
        for n in node:
            yield from _postings(n)
    elif isinstance(node, dict):
        kind = node.get("@type")
        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
            yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _postings(node[key])


def _place(loc) -> str:
    out = []
    for l in loc if isinstance(loc, list) else [loc]:
        if isinstance(l, dict):
            a = l.get("address") or {}
            if isinstance(a, str):
                out.append(a)
            elif isinstance(a, dict):
                country = a.get("addressCountry")
                country = country.get("name") if isinstance(country, dict) else country
                out.append(", ".join(x for x in (a.get("addressLocality"), a.get("addressRegion"), country) if x))
    return " · ".join(x for x in dict.fromkeys(out) if x)


def _salary(s) -> str:
    if not isinstance(s, dict):
        return ""
    v = s.get("value") or {}
    cur = s.get("currency") or ""
    if isinstance(v, dict):
        lo, hi, unit = v.get("minValue"), v.get("maxValue"), (v.get("unitText") or "").lower()
        amount = f"{lo:,} – {hi:,}" if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) else str(v.get("value") or lo or hi or "")
        return f"{cur} {amount}{f' / {unit}' if unit else ''}".strip() if amount else ""
    return f"{cur} {v}".strip() if v else ""


def _from_jsonld(page: str) -> dict | None:
    for raw in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(html.unescape(raw.strip()) if raw.strip().startswith("&") else raw.strip())
        except ValueError:
            continue
        for p in _postings(data):
            org = p.get("hiringOrganization") or {}
            remote = p.get("jobLocationType") == "TELECOMMUTE"
            loc = _place(p.get("jobLocation"))
            if remote:
                req = p.get("applicantLocationRequirements")
                where = ", ".join(r.get("name", "") for r in (req if isinstance(req, list) else [req]) if isinstance(r, dict) and r.get("name"))
                loc = f"Remote{f' ({where})' if where else ''}{f' · {loc}' if loc else ''}"
            etype = p.get("employmentType")
            job = _job(html_to_text(p.get("title") or ""), org.get("name") if isinstance(org, dict) else str(org), loc,
                       html_to_text(html.unescape(p.get("description") or "")),
                       employment_type=", ".join(etype) if isinstance(etype, list) else etype, salary=_salary(p.get("baseSalary")),
                       posted=p.get("datePosted"))
            if job["title"] and job["description"]:
                return job
    return None


def _page_text(page: str) -> str:
    body = re.search(r"<body[^>]*>(.*)</body>", page, re.S | re.I)
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    text = html_to_text(body.group(1) if body else page)
    return (f"Page title: {html_to_text(title.group(1))}\n\n" if title else "") + text


async def _from_ai(text: str) -> dict:
    result = await SkillService.run_skill("jobs/extract.md", {"raw_text": text[:15000]})
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            result = {}
    if not isinstance(result, dict) or result.get("error"):
        raise LinkError("a IA não conseguiu ler a vaga")
    return _job(result.get("title"), result.get("company"), result.get("location"), result.get("description"),
                employment_type=result.get("type"))


def _existing(url: str, linkedin_id: str | None) -> dict | None:
    conn = get_db_connection()
    try:
        with get_db_cursor(conn) as cur:
            cur.execute("SELECT id, job_title, company, status FROM public.job_listings WHERE url = %s OR (%s::text IS NOT NULL AND linkedin_job_id = %s) "
                        "ORDER BY id LIMIT 1", (url, linkedin_id, linkedin_id))
            r = cur.fetchone()
            return dict(r) if r else None
    finally:
        conn.close()


class JobLinkService:
    @staticmethod
    async def from_url(url: str) -> dict:
        url = (url or "").strip()
        if url and not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        u = urlparse(url)
        if not u.netloc or "." not in u.netloc:
            raise LinkError("link inválido")

        job, source = None, ""
        linkedin_id = _linkedin_id(u) if "linkedin.com" in u.netloc else None
        if linkedin_id:
            url = f"https://www.linkedin.com/jobs/view/{linkedin_id}/"
            job, source = _from_linkedin(linkedin_id), "LinkedIn"
        if "breezy.hr" in u.netloc and u.path.endswith("/apply"):   # the apply form; the ad is the page above it
            url = url.split("?")[0][: -len("/apply")]
            u = urlparse(url)
        for name, reader in (("Greenhouse", _from_greenhouse), ("Lever", _from_lever), ("Workable", _from_workable), ("Workday", _from_workday)):
            if not job:
                job, source = reader(u), name
        if not job:
            r = _get(url)
            if r.status_code in (404, 410):
                raise LinkError(f"a página da vaga não existe mais (HTTP {r.status_code})")
            # a site that turns scripts away (403, 429...) often still opens in the browser below
            page = r.text if r.status_code == 200 else ""
            ld = _from_jsonld(page)
            if ld and ld["company"] and ld["location"]:
                job, source = ld, "dados da página (schema.org)"
            else:
                text, rendered = _page_text(page), False
                if len(text) < 400 or "#" in url:   # little text without JavaScript (or a #/route): open it in Chromium
                    text, rendered = _rendered_text(url) or text, True
                if len(text) < 200:
                    if not ld:
                        raise LinkError(f"não consegui ler esta página{f' (HTTP {r.status_code})' if r.status_code != 200 else ''}: abra a vaga e cole o texto dela")
                    job, source = ld, "dados da página (schema.org)"
                else:
                    ai = await _from_ai(text)
                    if (not ai["title"] or not ai["description"]) and not rendered:   # page shell only: try the rendered page
                        text = _rendered_text(url)
                        if len(text) >= 200:
                            ai, rendered = await _from_ai(text), True
                    # what the page states wins; the AI fills the gaps
                    job = {**ai, **{k: v for k, v in (ld or {}).items() if v}}
                    source = "dados da página + IA" if ld else ("página aberta no navegador e lida pela IA" if rendered else "texto da página lido pela IA")
        if not job or not job.get("title") or not job.get("description"):
            raise LinkError("não encontrei a vaga nesta página: abra a vaga e cole o texto dela")
        return {**job, "url": url, "source": source, "existing": _existing(url, linkedin_id)}

    @staticmethod
    async def from_text(text: str, url: str = "") -> dict:
        if len((text or "").strip()) < 80:
            raise LinkError("cole o texto completo da vaga")
        job = await _from_ai(text)
        if not job["title"] or not job["description"]:
            raise LinkError("a IA não encontrou cargo e descrição neste texto")
        return {**job, "url": url.strip(), "source": "texto colado lido pela IA"}
