"""The readers of each place jobs come from, besides LinkedIn: official public endpoints (JSON, RSS, XML), never a scraped page.

Every reader returns the same shape (see `Job`) or raises SourceError with an error_code:
- not_found: the company is not (or no longer) on that ATS;
- unexpected_layout: the answer came, but not in the shape this reader knows (it never returns half a job);
- http_error: the site did not answer (timeout, 5xx, refused).

Where a source has a second official way in (another host, an RSS beside the API), the reader tries the newer one first and
falls back to the other when it finds nothing: the CLAUDE.md rule for LinkedIn layouts, applied to every source.
"""
import html
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger("discovery")

# A generic client name: the repo is public and no personal detail goes to the sites
UA = "CareerOps-JobDiscovery/1.0 (+job search for one person; 1 request per second)"
TIMEOUT = 25
PER_HOST_GAP = 1.0   # seconds between two requests to the same host


class SourceError(Exception):
    def __init__(self, code: str, text: str, raw: Optional[str] = None):
        super().__init__(f"{code}: {text}")
        self.code, self.text, self.raw = code, text, raw


@dataclass
class Job:
    source: str
    source_job_id: str
    title: str
    company: str
    location: str = ""
    description: str = ""
    url: str = ""                       # the ad
    apply_url: str = ""                 # the form (the ad itself when the form is on the same page)
    posted_at: Optional[datetime] = None
    remote: Optional[bool] = None
    countries: List[str] = field(default_factory=list)   # where the job may be done, when the source says (names or ISO codes)
    salary: str = ""
    visa_hint: bool = False             # found by a search for visa sponsorship
    needs_detail: bool = False          # the list has no description: read the ad only if the cheap filter keeps it
    detail_ref: str = ""


# ── HTTP ─────────────────────────────────────────────────────────────────
_last_call: Dict[str, float] = {}
_lock = threading.Lock()


def _wait_turn(host: str) -> None:
    with _lock:
        gap = PER_HOST_GAP - (time.monotonic() - _last_call.get(host, 0.0))
        if gap > 0:
            time.sleep(gap)
        _last_call[host] = time.monotonic()


def fetch(url: str, data: Optional[dict] = None, accept: str = "application/json", tries: int = 2) -> str:
    """GET (or POST with JSON when data is given). 404 raises not_found; other failures http_error after a retry."""
    host = urllib.parse.urlparse(url).hostname or ""
    body = json.dumps(data).encode() if data is not None else None
    headers = {"User-Agent": UA, "Accept": accept}
    if body is not None:
        headers["Content-Type"] = "application/json"
    last = ""
    for attempt in range(tries):
        _wait_turn(host)
        req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read(20_000_000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                raise SourceError("not_found", f"{e.code} em {host}")
            last = f"HTTP {e.code} em {host}"
            if e.code < 500 and e.code != 429:
                break
        except Exception as e:   # timeout, DNS, reset
            last = f"{type(e).__name__} em {host}: {e}"
        time.sleep(2 * (attempt + 1))
    raise SourceError("http_error", last)


def fetch_json(url: str, data: Optional[dict] = None):
    text = fetch(url, data)
    try:
        return json.loads(text)
    except ValueError:
        raise SourceError("unexpected_layout", f"a resposta de {urllib.parse.urlparse(url).hostname} não é JSON", text[:20000])


def fetch_xml(url: str) -> ET.Element:
    text = fetch(url, accept="application/xml, application/rss+xml, text/xml")
    try:
        return ET.fromstring(text.encode("utf-8"))
    except ET.ParseError:
        raise SourceError("unexpected_layout", f"a resposta de {urllib.parse.urlparse(url).hostname} não é XML", text[:20000])


def item(j, label: str, *keys: str) -> bool:
    """One job of a list: the keys must exist (else the shape changed: unexpected_layout); an empty one only skips this job
    (seen live 2026-11-22: one OpenAI job on Ashby with an empty title)."""
    need(isinstance(j, dict) and all(k in j for k in keys), f"{label}: vaga sem {'/'.join(keys)}", j)
    return all(j.get(k) for k in keys)


def need(cond: bool, what: str, raw) -> None:
    """The shape this reader knows: anything else stops the reading of this source, clearly."""
    if not cond:
        raise SourceError("unexpected_layout", what, json.dumps(raw)[:20000] if not isinstance(raw, str) else raw[:20000])


# ── Text and dates ───────────────────────────────────────────────────────
_BLOCK = re.compile(r"<\s*(br|/p|/div|/li|/h\d|/tr)\s*/?>", re.I)
_LI = re.compile(r"<\s*li[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")


def text_of(markup: Optional[str]) -> str:
    """HTML (escaped or not) to plain text with line breaks."""
    s = markup or ""
    if "&lt;" in s and "<" not in s:
        s = html.unescape(s)
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = _LI.sub("\n• ", _BLOCK.sub("\n", s))
    s = html.unescape(_TAG.sub(" ", s))
    lines = [" ".join(line.split()) for line in s.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def iso(value) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        secs = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(secs, tz=timezone.utc)
    s = str(value).strip()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None


def workday_posted(text: str, at: Optional[datetime] = None) -> Optional[datetime]:
    """'Posted Today', 'Posted Yesterday', 'Posted 3 Days Ago', 'Posted 30+ Days Ago'."""
    at = at or datetime.now(timezone.utc)
    t = (text or "").lower()
    if "today" in t:
        return at
    if "yesterday" in t:
        return at - timedelta(days=1)
    m = re.search(r"(\d+)\+?\s*day", t)
    return at - timedelta(days=int(m.group(1))) if m else None


# ── Which ATS an address belongs to ──────────────────────────────────────
_ATS_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("greenhouse", re.compile(r"^https?://(?:job-)?boards(?P<eu>\.eu)?\.greenhouse\.io/(?!embed\b)(?P<slug>[\w.-]+)", re.I)),
    ("greenhouse", re.compile(r"^https?://boards-api(?P<eu>\.eu)?\.greenhouse\.io/v1/boards/(?P<slug>[\w.-]+)", re.I)),
    ("lever", re.compile(r"^https?://jobs(?P<eu>\.eu)?\.lever\.co/(?P<slug>[\w.-]+)", re.I)),
    ("ashby", re.compile(r"^https?://jobs\.ashbyhq\.com/(?P<slug>[^/?#]+)", re.I)),
    ("smartrecruiters", re.compile(r"^https?://(?:jobs|careers)\.smartrecruiters\.com/(?P<slug>[\w.-]+)", re.I)),
    ("recruitee", re.compile(r"^https?://(?P<slug>[\w-]+)\.recruitee\.com", re.I)),
    ("workable", re.compile(r"^https?://apply\.workable\.com/(?P<slug>[\w.-]+)", re.I)),
    ("personio", re.compile(r"^https?://(?P<slug>[\w-]+)\.jobs\.personio\.(?:de|com)", re.I)),
    ("workday", re.compile(r"^https?://(?P<tenant>[\w-]+)\.(?P<wd>wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?(?P<site>[\w-]+)", re.I)),
]
_NOT_SLUGS = {"embed", "jobs", "api", "o", "v0", "v1", "careers", "en", "search"}


def ats_of(url: str) -> Optional[Tuple[str, str]]:
    """(kind, slug) of a company board on a known ATS, from any of its addresses; None otherwise."""
    for kind, pattern in _ATS_PATTERNS:
        m = pattern.match((url or "").strip())
        if not m:
            continue
        if kind == "workday":
            if m.group("site").lower() in ("wday", "job"):
                return None
            return kind, f"{m.group('tenant').lower()}|{m.group('wd').lower()}|{m.group('site')}"
        slug = urllib.parse.unquote(m.group("slug"))
        if slug.lower() in _NOT_SLUGS:
            return None
        if kind in ("greenhouse", "lever"):
            slug = slug.lower()
            if m.groupdict().get("eu"):
                slug = f"eu:{slug}"
        return kind, slug
    return None


def norm_url(url: str) -> str:
    """The same address written two ways (tracking, /apply, trailing slash, case of the host) compares equal."""
    p = urllib.parse.urlparse((url or "").strip())
    if not p.scheme:
        return ""
    path = re.sub(r"/(apply|application)/?$", "", p.path.rstrip("/"))
    return f"{p.netloc.lower()}{path}".lower()


# ── Company boards (ATS) ─────────────────────────────────────────────────
def _greenhouse(slug: str, company: str) -> List[Job]:
    eu = slug.startswith("eu:")
    board = slug[3:] if eu else slug
    hosts = ["boards-api.eu.greenhouse.io", "boards-api.greenhouse.io"] if eu else ["boards-api.greenhouse.io", "api.greenhouse.io"]
    data, last = None, None
    for host in hosts:   # the board API, then its older host (the same JSON)
        try:
            data = fetch_json(f"https://{host}/v1/boards/{urllib.parse.quote(board)}/jobs?content=true")
            break
        except SourceError as e:
            last = e
            if e.code == "unexpected_layout":
                raise
    if data is None:
        raise last
    need(isinstance(data, dict) and isinstance(data.get("jobs"), list), "Greenhouse: sem a lista 'jobs'", data)
    out = []
    for j in data["jobs"]:
        if not item(j, "Greenhouse", "id", "title", "absolute_url"):
            continue
        loc = (j.get("location") or {}).get("name") or ""
        offices = [o.get("name") for o in j.get("offices") or [] if isinstance(o, dict) and o.get("name")]
        out.append(Job("greenhouse", str(j["id"]), j["title"].strip(), j.get("company_name") or company or board, loc,
                       text_of(j.get("content")), j["absolute_url"], j["absolute_url"], iso(j.get("first_published") or j.get("updated_at")),
                       remote=bool(re.search(r"remote|anywhere", loc, re.I)) or None, countries=offices))
    return out


def _lever(slug: str, company: str) -> List[Job]:
    eu = slug.startswith("eu:")
    board = slug[3:] if eu else slug
    hosts = ["api.eu.lever.co", "api.lever.co"] if eu else ["api.lever.co", "api.eu.lever.co"]
    data, last = None, None
    for host in hosts:
        try:
            data = fetch_json(f"https://{host}/v0/postings/{urllib.parse.quote(board)}?mode=json")
            break
        except SourceError as e:
            last = e
            if e.code == "unexpected_layout":
                raise
    if data is None:
        raise last
    need(isinstance(data, list), "Lever: a resposta não é uma lista de vagas", data)
    out = []
    for j in data:
        if not item(j, "Lever", "id", "text", "hostedUrl"):
            continue
        cat = j.get("categories") or {}
        parts = [j.get("descriptionPlain") or text_of(j.get("description"))]
        for block in j.get("lists") or []:
            parts.append(f"{block.get('text') or ''}\n{text_of(block.get('content'))}")
        parts.append(j.get("additionalPlain") or "")
        locs = cat.get("allLocations") or ([cat["location"]] if cat.get("location") else [])
        out.append(Job("lever", str(j["id"]), j["text"].strip(), company or board, ", ".join(locs), "\n\n".join(p for p in parts if p),
                       j["hostedUrl"], j.get("applyUrl") or j["hostedUrl"], iso(j.get("createdAt")),
                       remote=(j.get("workplaceType") == "remote") if j.get("workplaceType") else None,
                       countries=[j["country"]] if j.get("country") else []))
    return out


def _ashby(slug: str, company: str) -> List[Job]:
    data = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(slug)}?includeCompensation=true")
    need(isinstance(data, dict) and isinstance(data.get("jobs"), list), "Ashby: sem a lista 'jobs'", data)
    out = []
    for j in data["jobs"]:
        if not item(j, "Ashby", "id", "title", "jobUrl"):
            continue
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [s.get("location") for s in j.get("secondaryLocations") or [] if isinstance(s, dict) and s.get("location")]
        country = (((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry")) or ""
        comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
        out.append(Job("ashby", str(j["id"]), j["title"].strip(), company or slug, ", ".join(l for l in locs if l),
                       j.get("descriptionPlain") or text_of(j.get("descriptionHtml")), j["jobUrl"], j.get("applyUrl") or j["jobUrl"],
                       iso(j.get("publishedAt")), remote=bool(j.get("isRemote")) or (j.get("workplaceType") == "Remote") or None,
                       countries=[country] if country else [], salary=comp))
    return out


def _smartrecruiters(slug: str, company: str) -> List[Job]:
    out, offset = [], 0
    while offset < 500:
        data = fetch_json(f"https://api.smartrecruiters.com/v1/companies/{urllib.parse.quote(slug)}/postings?limit=100&offset={offset}")
        need(isinstance(data, dict) and isinstance(data.get("content"), list), "SmartRecruiters: sem a lista 'content'", data)
        for j in data["content"]:
            if not item(j, "SmartRecruiters", "id", "name"):
                continue
            loc = j.get("location") or {}
            url = f"https://jobs.smartrecruiters.com/{slug}/{j['id']}"
            out.append(Job("smartrecruiters", str(j["id"]), j["name"].strip(), (j.get("company") or {}).get("name") or company or slug,
                           loc.get("fullLocation") or ", ".join(x for x in (loc.get("city"), loc.get("country")) if x), "", url, url,
                           iso(j.get("releasedDate")), remote=bool(loc.get("remote")) or None,
                           countries=[loc["country"]] if loc.get("country") else [], needs_detail=True,
                           detail_ref=j.get("ref") or f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{j['id']}"))
        if len(data["content"]) < 100:
            break
        offset += 100
    return out


def _smartrecruiters_detail(job: Job) -> Job:
    d = fetch_json(job.detail_ref)
    need(isinstance(d, dict) and isinstance((d.get("jobAd") or {}).get("sections"), dict), "SmartRecruiters: anúncio sem jobAd.sections", d)
    sections = d["jobAd"]["sections"]
    job.description = "\n\n".join(text_of((sections.get(k) or {}).get("text")) for k in ("jobDescription", "qualifications", "additionalInformation", "companyDescription"))
    job.url = d.get("postingUrl") or job.url
    job.apply_url = d.get("applyUrl") or job.url
    return job


def _recruitee(slug: str, company: str) -> List[Job]:
    data = fetch_json(f"https://{slug}.recruitee.com/api/offers/")
    need(isinstance(data, dict) and isinstance(data.get("offers"), list), "Recruitee: sem a lista 'offers'", data)
    out = []
    for j in data["offers"]:
        if not item(j, "Recruitee", "id", "title", "careers_url"):
            continue
        if j.get("status") not in (None, "published"):
            continue
        out.append(Job("recruitee", str(j["id"]), j["title"].strip(), j.get("company_name") or company or slug,
                       j.get("location") or ", ".join(x for x in (j.get("city"), j.get("country")) if x),
                       text_of((j.get("description") or "") + "\n" + (j.get("requirements") or "")), j["careers_url"],
                       j.get("careers_apply_url") or j["careers_url"], iso(j.get("published_at") or j.get("created_at")),
                       remote=bool(j.get("remote")) or None, countries=[j["country_code"]] if j.get("country_code") else []))
    return out


def _workable(slug: str, company: str) -> List[Job]:
    data = fetch_json(f"https://apply.workable.com/api/v1/widget/accounts/{urllib.parse.quote(slug)}?details=true")
    need(isinstance(data, dict) and isinstance(data.get("jobs"), list), "Workable: sem a lista 'jobs'", data)
    out = []
    for j in data["jobs"]:
        if not item(j, "Workable", "shortcode", "title", "url"):
            continue
        locs = [", ".join(x for x in (l.get("city"), l.get("country")) if x) for l in j.get("locations") or [] if isinstance(l, dict)]
        loc = "; ".join(l for l in locs if l) or ", ".join(x for x in (j.get("city"), j.get("country")) if x)
        out.append(Job("workable", j["shortcode"], j["title"].strip(), data.get("name") or company or slug, loc, text_of(j.get("description")),
                       j["url"], j.get("application_url") or j["url"], iso(j.get("published_on") or j.get("created_at")),
                       remote=bool(j.get("telecommuting")) or None,
                       countries=[l.get("countryCode") for l in j.get("locations") or [] if isinstance(l, dict) and l.get("countryCode")]))
    return out


def _personio(slug: str, company: str) -> List[Job]:
    root, last = None, None
    for tld in ("de", "com"):
        try:
            root = fetch_xml(f"https://{slug}.jobs.personio.{tld}/xml?language=en")
            break
        except SourceError as e:   # a board it lacks: 404, or an HTML "Page Not Found" with 200
            gone = e.code == "not_found" or (e.code == "unexpected_layout" and "not found" in (e.raw or "").lower())
            last = SourceError("not_found", f"Personio: {slug} sem quadro de vagas") if gone else e
    if root is None:
        raise last
    need(root.tag == "workzag-jobs", "Personio: XML sem <workzag-jobs>", ET.tostring(root, encoding="unicode")[:20000])
    out = []
    for p in root.findall("position"):
        pid, name = (p.findtext("id") or "").strip(), (p.findtext("name") or "").strip()
        if not (pid and name):
            continue
        offices = [p.findtext("office") or ""] + [o.text or "" for o in p.findall("additionalOffices/office")]
        desc = "\n\n".join(f"{d.findtext('name') or ''}\n{text_of(d.findtext('value'))}" for d in p.findall("jobDescriptions/jobDescription"))
        url = f"https://{slug}.jobs.personio.de/job/{pid}"
        loc = ", ".join(o for o in offices if o)
        out.append(Job("personio", pid, name, company or slug, loc, desc, url, url, iso(p.findtext("createdAt")),
                       remote=bool(re.search(r"remote", loc, re.I)) or None))
    return out


WORKDAY_QUERIES = ["AI engineer", "machine learning", "data scientist", "FP&A", "financial model", "project finance", "forecasting"]


def _workday(slug: str, company: str) -> List[Job]:
    tenant, wd, site = slug.split("|")
    base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    seen, out = set(), []
    for q in WORKDAY_QUERIES:
        data = fetch_json(f"{base}/wday/cxs/{tenant}/{site}/jobs", {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q})
        need(isinstance(data, dict) and isinstance(data.get("jobPostings"), list), "Workday: sem a lista 'jobPostings'", data)
        for j in data["jobPostings"]:
            if not item(j, "Workday", "title", "externalPath"):
                continue
            if j["externalPath"] in seen:
                continue
            seen.add(j["externalPath"])
            url = f"{base}/{site}{j['externalPath']}"
            out.append(Job("workday", f"{tenant}:{j['externalPath'].rsplit('_', 1)[-1]}", j["title"].strip(), company or tenant,
                           j.get("locationsText") or "", "", url, url, workday_posted(j.get("postedOn") or ""), needs_detail=True,
                           detail_ref=f"{base}/wday/cxs/{tenant}/{site}{j['externalPath']}"))
    return out


def _workday_detail(job: Job) -> Job:
    d = fetch_json(job.detail_ref)
    info = d.get("jobPostingInfo") if isinstance(d, dict) else None
    need(isinstance(info, dict) and info.get("jobDescription") is not None, "Workday: anúncio sem jobPostingInfo.jobDescription", d)
    job.description = text_of(info.get("jobDescription"))
    job.location = ", ".join(x for x in [info.get("location")] + list(info.get("additionalLocations") or []) if x) or job.location
    country = (info.get("country") or {}).get("descriptor")
    job.countries = [country] if country else job.countries
    job.remote = bool(re.search(r"remote", f"{info.get('remoteType') or ''} {job.location}", re.I)) or None
    job.posted_at = iso(info.get("startDate")) or job.posted_at
    job.url = job.apply_url = info.get("externalUrl") or job.url
    return job


# ── Job boards (remote work) ─────────────────────────────────────────────
def _remotive(slug: str, company: str) -> List[Job]:
    data = fetch_json("https://remotive.com/api/remote-jobs")
    need(isinstance(data, dict) and isinstance(data.get("jobs"), list), "Remotive: sem a lista 'jobs'", data)
    out = []
    for j in data["jobs"]:
        if not item(j, "Remotive", "id", "title", "url"):
            continue
        out.append(Job("remotive", str(j["id"]), j["title"].strip(), j.get("company_name") or "", j.get("candidate_required_location") or "",
                       text_of(j.get("description")), j["url"], j["url"], iso(j.get("publication_date")), remote=True,
                       salary=j.get("salary") or ""))
    return out


def _remoteok(slug: str, company: str) -> List[Job]:
    data = fetch_json("https://remoteok.com/api")
    need(isinstance(data, list), "Remote OK: a resposta não é uma lista", data)
    out = []
    for j in data:
        if not isinstance(j, dict) or "legal" in j:   # the first item is the terms of use
            continue
        need(j.get("id") and j.get("position") and j.get("url"), "Remote OK: vaga sem id/position/url", j)
        pay = f"USD {j['salary_min']:,}–{j['salary_max']:,}/ano" if j.get("salary_min") and j.get("salary_max") else ""
        out.append(Job("remoteok", str(j["id"]), j["position"].strip(), j.get("company") or "", j.get("location") or "",
                       text_of(j.get("description")), j["url"], j.get("apply_url") or j["url"], iso(j.get("date") or j.get("epoch")),
                       remote=True, salary=pay))
    return out


WWR_FEEDS = ["https://weworkremotely.com/remote-jobs.rss",
             "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
             "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss"]


def _rss_items(root: ET.Element) -> List[ET.Element]:
    return root.findall("./channel/item")


def _weworkremotely(slug: str, company: str) -> List[Job]:
    """The feed of all jobs; the category feeds when it does not answer."""
    roots, last = [], None
    try:
        roots = [fetch_xml(WWR_FEEDS[0])]
    except SourceError as e:
        last = e
        for feed in WWR_FEEDS[1:]:
            try:
                roots.append(fetch_xml(feed))
            except SourceError as e2:
                last = e2
    if not roots:
        raise last
    out = []
    for root in roots:
        need(root.tag == "rss" and root.find("channel") is not None, "We Work Remotely: RSS sem <channel>", ET.tostring(root, encoding="unicode")[:20000])
        for it in _rss_items(root):
            title, link = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()
            if not (title and link):
                continue
            comp, _, role = title.partition(": ")
            region = " ".join(x for x in (it.findtext("region"), re.sub(r"[^\w\s,.-]", "", it.findtext("country") or "").strip()) if x)
            out.append(Job("weworkremotely", it.findtext("guid") or link, (role or title).strip(), comp.strip() if role else "", region,
                           text_of(it.findtext("description")), link, link, iso(it.findtext("pubDate")), remote=True))
    return out


HIMALAYAS_QUERIES = ["financial modeling", "FP&A", "project finance", "AI engineer", "LLM", "data scientist", "forecasting",
                     "analytics engineer", "solutions engineer", "automation engineer"]


def _himalayas_job(j: dict) -> Job:
    need(isinstance(j, dict) and "title" in j and ("guid" in j or "applicationLink" in j), "Himalayas: vaga sem title/guid", j)
    pay = f"{j.get('currency') or 'USD'} {j['minSalary']:,}–{j['maxSalary']:,}" if j.get("minSalary") and j.get("maxSalary") else ""
    restrictions = [r if isinstance(r, str) else (r.get("name") or "") for r in j.get("locationRestrictions") or []]
    url = j.get("guid") or j.get("applicationLink")
    return Job("himalayas", url, j["title"].strip(), j.get("companyName") or "", ", ".join(restrictions[:6]) + (" …" if len(restrictions) > 6 else ""),
               text_of(j.get("description")), url, j.get("applicationLink") or url, iso(j.get("pubDate")), remote=True,
               countries=restrictions, salary=pay)


def _himalayas(slug: str, company: str) -> List[Job]:
    """The search (jobs open to someone in Brazil) first; the plain newest list when the search stops answering."""
    out: Dict[str, Job] = {}
    try:
        for q in HIMALAYAS_QUERIES:
            data = fetch_json(f"https://himalayas.app/jobs/api/search?q={urllib.parse.quote(q)}&country=BR&sort=recent&page=1")
            need(isinstance(data, dict) and isinstance(data.get("jobs"), list), "Himalayas: busca sem a lista 'jobs'", data)
            for j in data["jobs"]:
                job = _himalayas_job(j)
                out[job.source_job_id] = job
        return list(out.values())
    except SourceError as e:
        if e.code == "http_error":
            raise
        log.warning("himalayas search failed (%s): falling back to the newest list", e)
    for offset in range(0, 100, 20):
        data = fetch_json(f"https://himalayas.app/jobs/api?limit=20&offset={offset}")
        need(isinstance(data, dict) and isinstance(data.get("jobs"), list), "Himalayas: sem a lista 'jobs'", data)
        for j in data["jobs"]:
            job = _himalayas_job(j)
            out[job.source_job_id] = job
    return list(out.values())


def _jobicy(slug: str, company: str) -> List[Job]:
    out: Dict[str, Job] = {}
    for query in ("count=100", "count=100&geo=latam"):
        data = fetch_json(f"https://jobicy.com/api/v2/remote-jobs?{query}")
        need(isinstance(data, dict) and isinstance(data.get("jobs"), list), "Jobicy: sem a lista 'jobs'", data)
        for j in data["jobs"]:
            if not item(j, "Jobicy", "id", "jobTitle", "url"):
                continue
            pay = (f"{j.get('salaryCurrency') or 'USD'} {j['annualSalaryMin']:,}–{j['annualSalaryMax']:,}/ano"
                   if j.get("annualSalaryMin") and j.get("annualSalaryMax") else "")
            out[str(j["id"])] = Job("jobicy", str(j["id"]), html.unescape(j["jobTitle"]).strip(), html.unescape(j.get("companyName") or ""),
                                    j.get("jobGeo") or "", text_of(j.get("jobDescription")), j["url"], j["url"], iso(j.get("pubDate")),
                                    remote=True, salary=pay)
    return list(out.values())


def _workingnomads(slug: str, company: str) -> List[Job]:
    data = fetch_json("https://www.workingnomads.com/api/exposed_jobs/")
    need(isinstance(data, list), "Working Nomads: a resposta não é uma lista", data)
    out = []
    for j in data:
        if not item(j, "Working Nomads", "url", "title"):
            continue
        out.append(Job("workingnomads", j["url"], j["title"].strip(), j.get("company_name") or "", j.get("location") or "",
                       text_of(j.get("description")), j["url"], j["url"], iso(j.get("pub_date")), remote=True))
    return out


def _arbeitnow(slug: str, company: str) -> List[Job]:
    out = []
    for page in (1, 2, 3):
        data = fetch_json(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        need(isinstance(data, dict) and isinstance(data.get("data"), list), "Arbeitnow: sem a lista 'data'", data)
        for j in data["data"]:
            if not item(j, "Arbeitnow", "slug", "title", "url"):
                continue
            out.append(Job("arbeitnow", j["slug"], j["title"].strip(), j.get("company_name") or "", j.get("location") or "",
                           text_of(j.get("description")), j["url"], j["url"], iso(j.get("created_at")), remote=bool(j.get("remote")) or None,
                           countries=["Germany"]))
        if not data["data"]:
            break
    return out


# ── Aggregators with a free key (off until the key is in the environment) ──
AGGREGATOR_QUERIES = ["financial modeling", "FP&A", "project finance", "AI engineer", "data scientist forecasting"]
ADZUNA_COUNTRIES = ["gb", "de", "nl", "es", "us"]


def _adzuna(slug: str, company: str, app_id: str = "", app_key: str = "") -> List[Job]:
    out: Dict[str, Job] = {}
    for cc in ADZUNA_COUNTRIES:
        for q in AGGREGATOR_QUERIES:
            params = urllib.parse.urlencode({"app_id": app_id, "app_key": app_key, "what_or": q, "what_phrase": "visa sponsorship",
                                             "max_days_old": 3, "results_per_page": 50, "content-type": "application/json"})
            data = fetch_json(f"https://api.adzuna.com/v1/api/jobs/{cc}/search/1?{params}")
            need(isinstance(data, dict) and isinstance(data.get("results"), list), "Adzuna: sem a lista 'results'", data)
            for j in data["results"]:
                if not item(j, "Adzuna", "id", "title", "redirect_url"):
                    continue
                out[str(j["id"])] = Job("adzuna", str(j["id"]), text_of(j["title"]), (j.get("company") or {}).get("display_name") or "",
                                        (j.get("location") or {}).get("display_name") or "", text_of(j.get("description")),
                                        j["redirect_url"], j["redirect_url"], iso(j.get("created")), countries=[cc.upper()], visa_hint=True)
    return list(out.values())


def _jooble(slug: str, company: str, key: str = "") -> List[Job]:
    out: Dict[str, Job] = {}
    for q in AGGREGATOR_QUERIES:
        for body in ({"keywords": f"{q} visa sponsorship", "location": ""}, {"keywords": f"{q} remote LATAM", "location": ""}):
            data = fetch_json(f"https://jooble.org/api/{key}", {**body, "page": 1})
            need(isinstance(data, dict) and isinstance(data.get("jobs"), list), "Jooble: sem a lista 'jobs'", data)
            for j in data["jobs"]:
                if not item(j, "Jooble", "id", "title", "link"):
                    continue
                out[str(j["id"])] = Job("jooble", str(j["id"]), text_of(j["title"]), j.get("company") or "", j.get("location") or "",
                                        text_of(j.get("snippet")), j["link"], j["link"], iso(j.get("updated")),
                                        visa_hint="visa" in body["keywords"], salary=j.get("salary") or "")
    return list(out.values())


# kind → (reader, family, detail reader). family: "ats" (one board per company, read once a day) or "board" (twice a day)
READERS: Dict[str, Tuple[Callable[..., List[Job]], str, Optional[Callable[[Job], Job]]]] = {
    "greenhouse": (_greenhouse, "ats", None),
    "lever": (_lever, "ats", None),
    "ashby": (_ashby, "ats", None),
    "smartrecruiters": (_smartrecruiters, "ats", _smartrecruiters_detail),
    "recruitee": (_recruitee, "ats", None),
    "workable": (_workable, "ats", None),
    "personio": (_personio, "ats", None),
    "workday": (_workday, "ats", _workday_detail),
    "remotive": (_remotive, "board", None),
    "remoteok": (_remoteok, "board", None),
    "weworkremotely": (_weworkremotely, "board", None),
    "himalayas": (_himalayas, "board", None),
    "jobicy": (_jobicy, "board", None),
    "workingnomads": (_workingnomads, "board", None),
    "arbeitnow": (_arbeitnow, "board", None),
    "adzuna": (_adzuna, "board", None),
    "jooble": (_jooble, "board", None),
}
LABELS = {"linkedin": "LinkedIn", "greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby", "smartrecruiters": "SmartRecruiters",
          "recruitee": "Recruitee", "workable": "Workable", "personio": "Personio", "workday": "Workday", "remotive": "Remotive",
          "remoteok": "Remote OK", "weworkremotely": "We Work Remotely", "himalayas": "Himalayas", "jobicy": "Jobicy",
          "workingnomads": "Working Nomads", "arbeitnow": "Arbeitnow", "adzuna": "Adzuna", "jooble": "Jooble"}
# ATS whose board answers for a company name tried as a slug (the probe of companies already seen with good jobs)
PROBE_KINDS = ("greenhouse", "lever", "ashby")


def board_name(kind: str, slug: str) -> Optional[str]:
    """The company's name on the board, to check that a probed slug is really that company (Greenhouse only says it)."""
    if kind != "greenhouse":
        return None
    try:
        data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(slug)}")
        return data.get("name") if isinstance(data, dict) else None
    except SourceError:
        return None
