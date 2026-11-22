"""Jobs from more places than LinkedIn (discovery_service, discovery/sources, discovery/filters). The sources are never called:
each test answers the addresses from recorded shapes, the current one and the fallback one (the CLAUDE.md rule)."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.services import discovery_service
from app.services.automation_service import AutomationService as Auto
from app.services.discovery import filters, sources
from app.services.discovery.sources import Job, SourceError, ats_of, norm_url, text_of
from app.services.discovery_service import DiscoveryService as D, dedupe_key
from app.services.job_search_service import JobSearchService as Search

NOW = datetime.now(timezone.utc)
LONG = ("You will build financial models for infrastructure projects with our team. We are a remote-first company and "
        "this role is open to candidates in Latin America. The work includes forecasting, valuation and reporting for the "
        "board, with Python and SQL. You have experience with project finance and our investors.")


class Web:
    """Answers fetch() from a dict: url prefix → text, dict/list (JSON) or a SourceError."""
    def __init__(self, monkeypatch, routes):
        self.routes, self.calls = routes, []
        monkeypatch.setattr(sources, "fetch", self.fetch)
        monkeypatch.setattr(sources, "PER_HOST_GAP", 0)

    def fetch(self, url, data=None, accept="application/json", tries=2):
        self.calls.append(url)
        for prefix, answer in self.routes.items():
            if url.startswith(prefix):
                if isinstance(answer, Exception):
                    raise answer
                return answer if isinstance(answer, str) else json.dumps(answer)
        raise SourceError("not_found", f"404 {url}")


def gh_job(i, title="Senior Financial Modeling Analyst", loc="Remote - LATAM", content=None, days=1):
    return {"id": i, "title": title, "absolute_url": f"https://job-boards.greenhouse.io/acme/jobs/{i}", "location": {"name": loc},
            "company_name": "Acme", "first_published": (NOW - timedelta(days=days)).isoformat(),
            "content": content if content is not None else "&lt;p&gt;" + LONG + "&lt;/p&gt;", "offices": []}


# ── Readers ──────────────────────────────────────────────────────────────
def test_greenhouse_reads_its_board_and_falls_back_to_the_older_host(monkeypatch):
    Web(monkeypatch, {"https://boards-api.greenhouse.io/": SourceError("http_error", "503"),
                      "https://api.greenhouse.io/v1/boards/acme/jobs": {"jobs": [gh_job(1)], "meta": {"total": 1}}})
    jobs = sources._greenhouse("acme", "Acme")
    assert len(jobs) == 1 and jobs[0].source_job_id == "1" and "financial models" in jobs[0].description
    assert "<p>" not in jobs[0].description and jobs[0].apply_url.endswith("/jobs/1")


def test_a_changed_answer_fails_clearly_and_never_returns_half_a_job(monkeypatch):
    Web(monkeypatch, {"https://boards-api.greenhouse.io/": {"positions": []}})
    with pytest.raises(SourceError) as e:
        sources._greenhouse("acme", "Acme")
    assert e.value.code == "unexpected_layout" and "positions" in e.value.raw


def test_lever_us_then_eu(monkeypatch):
    item = {"id": "a1", "text": "AI Engineer", "hostedUrl": "https://jobs.eu.lever.co/acme/a1", "applyUrl": "https://jobs.eu.lever.co/acme/a1/apply",
            "categories": {"location": "Remote - Brazil", "allLocations": ["Remote - Brazil"]}, "createdAt": 1795000000000,
            "descriptionPlain": LONG, "lists": [{"text": "Requirements", "content": "<li>Python</li>"}], "workplaceType": "remote", "country": "BR"}
    web = Web(monkeypatch, {"https://api.lever.co/": SourceError("not_found", "404"), "https://api.eu.lever.co/v0/postings/acme": [item]})
    jobs = sources._lever("acme", "Acme")
    assert jobs[0].remote is True and jobs[0].countries == ["BR"] and "• Python" in jobs[0].description
    assert web.calls[0].startswith("https://api.lever.co/")


def test_ashby_skips_unlisted_and_keeps_the_pay(monkeypatch):
    base = {"title": "Applied AI Engineer", "jobUrl": "https://jobs.ashbyhq.com/acme/x", "applyUrl": "https://jobs.ashbyhq.com/acme/x/application",
            "location": "Remote", "isRemote": True, "descriptionPlain": LONG, "publishedAt": NOW.isoformat(),
            "address": {"postalAddress": {"addressCountry": "Brazil"}}, "compensation": {"compensationTierSummary": "$150K – $180K"}}
    Web(monkeypatch, {"https://api.ashbyhq.com/": {"jobs": [{**base, "id": "x"}, {**base, "id": "y", "isListed": False}], "apiVersion": "1"}})
    jobs = sources._ashby("acme", "Acme")
    assert [j.source_job_id for j in jobs] == ["x"] and jobs[0].salary == "$150K – $180K" and jobs[0].countries == ["Brazil"]


def test_smartrecruiters_reads_the_ad_only_when_asked(monkeypatch):
    Web(monkeypatch, {
        "https://api.smartrecruiters.com/v1/companies/Acme/postings?": {"totalFound": 1, "content": [
            {"id": "77", "name": "FP&A Manager", "releasedDate": NOW.isoformat(), "company": {"name": "Acme"},
             "location": {"city": "Lisbon", "country": "pt", "remote": False, "fullLocation": "Lisbon, Portugal"},
             "ref": "https://api.smartrecruiters.com/v1/companies/Acme/postings/77"}]},
        "https://api.smartrecruiters.com/v1/companies/Acme/postings/77": {
            "postingUrl": "https://jobs.smartrecruiters.com/Acme/77-fpa", "applyUrl": "https://jobs.smartrecruiters.com/Acme/77-fpa?oga=true",
            "jobAd": {"sections": {"jobDescription": {"text": "<p>" + LONG + " We offer visa sponsorship and relocation support.</p>"}}}}})
    jobs = sources._smartrecruiters("Acme", "Acme")
    assert jobs[0].needs_detail and not jobs[0].description
    sources._smartrecruiters_detail(jobs[0])
    assert "visa sponsorship" in jobs[0].description and jobs[0].apply_url.endswith("oga=true")


def test_personio_html_page_means_no_board(monkeypatch):
    Web(monkeypatch, {"https://acme.jobs.personio.de/": SourceError("not_found", "404"),
                      "https://acme.jobs.personio.com/": SourceError("unexpected_layout", "not XML", "<title>Page Not Found</title>")})
    with pytest.raises(SourceError) as e:
        sources._personio("acme", "Acme")
    assert e.value.code == "not_found"


def test_personio_xml(monkeypatch):
    xml = ("<?xml version='1.0'?><workzag-jobs><position><id>5</id><office>Remote</office><name>Senior FP&amp;A Manager</name>"
           "<createdAt>2026-11-20T10:00:00+00:00</createdAt><jobDescriptions><jobDescription><name>Role</name><value><![CDATA[<p>"
           + LONG + "</p>]]></value></jobDescription></jobDescriptions></position></workzag-jobs>")
    monkeypatch.setattr(sources, "fetch_xml", lambda url: __import__("xml.etree.ElementTree", fromlist=["x"]).fromstring(xml))
    jobs = sources._personio("acme", "Acme")
    assert jobs[0].title == "Senior FP&A Manager" and jobs[0].remote and "Role" in jobs[0].description


def test_workday_lists_by_search_and_reads_the_ad(monkeypatch):
    path = "/job/Remote-Brazil/Finance-Transformation-Manager_JR1"
    Web(monkeypatch, {
        "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/Careers/jobs": {"total": 1, "jobPostings": [
            {"title": "Finance Transformation Manager", "externalPath": path, "locationsText": "Remote - Brazil", "postedOn": "Posted 2 Days Ago"}]},
        f"https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/Careers{path}": {"jobPostingInfo": {
            "jobDescription": "<p>" + LONG + "</p>", "location": "Remote - Brazil", "country": {"descriptor": "Brazil"}, "remoteType": "Remote",
            "startDate": NOW.date().isoformat(), "externalUrl": f"https://acme.wd5.myworkdayjobs.com/Careers{path}"}}})
    jobs = sources._workday("acme|wd5|Careers", "Acme")
    assert len(jobs) == 1 and jobs[0].source_job_id == "acme:JR1" and jobs[0].posted_at
    sources._workday_detail(jobs[0])
    assert jobs[0].remote and jobs[0].countries == ["Brazil"] and "financial models" in jobs[0].description


def test_himalayas_falls_back_to_the_newest_list(monkeypatch):
    job = {"title": "AI Engineer", "companyName": "Acme", "guid": "https://himalayas.app/companies/acme/jobs/ai", "description": "<p>" + LONG + "</p>",
           "pubDate": 1795000000, "locationRestrictions": ["Brazil", "Mexico"], "applicationLink": "https://job-boards.greenhouse.io/acme/jobs/9"}
    Web(monkeypatch, {"https://himalayas.app/jobs/api/search": {"error": "gone"}, "https://himalayas.app/jobs/api?": {"jobs": [job], "totalCount": 1}})
    jobs = sources._himalayas("all", "")
    assert len(jobs) == 1 and jobs[0].countries == ["Brazil", "Mexico"]


def test_remoteok_skips_its_terms_item(monkeypatch):
    Web(monkeypatch, {"https://remoteok.com/api": [{"legal": "terms"}, {"id": "9", "position": "LLM Engineer", "company": "Acme", "url": "https://remoteok.com/remote-jobs/9",
                                                    "apply_url": "https://acme.com/apply", "location": "Worldwide", "description": LONG, "date": NOW.isoformat()}]})
    jobs = sources._remoteok("all", "")
    assert [j.title for j in jobs] == ["LLM Engineer"] and jobs[0].url.startswith("https://remoteok.com")


def test_wwr_reads_the_category_feeds_when_the_main_one_fails(monkeypatch):
    import xml.etree.ElementTree as ET
    rss = ("<rss><channel><item><title>Acme: Senior Data Scientist</title><region>Anywhere in the World</region>"
           "<link>https://weworkremotely.com/remote-jobs/acme-ds</link><pubDate>Sat, 21 Nov 2026 10:00:00 +0000</pubDate>"
           "<description>&lt;p&gt;" + LONG + "&lt;/p&gt;</description></item></channel></rss>")
    calls = []

    def fake(url):
        calls.append(url)
        if url.endswith("remote-jobs.rss"):
            raise SourceError("http_error", "timeout")
        return ET.fromstring(rss)
    monkeypatch.setattr(sources, "fetch_xml", fake)
    jobs = sources._weworkremotely("all", "")
    assert len(calls) == 3 and jobs[0].company == "Acme" and jobs[0].title == "Senior Data Scientist"


@pytest.mark.parametrize("url,expected", [
    ("https://job-boards.greenhouse.io/affirm/jobs/7804953003", ("greenhouse", "affirm")),
    ("https://job-boards.eu.greenhouse.io/decathlontechnology/jobs/5011607101", ("greenhouse", "eu:decathlontechnology")),
    ("https://job-boards.greenhouse.io/embed/job_app?for=x", None),
    ("https://jobs.lever.co/megaport/7658c6d8", ("lever", "megaport")),
    ("https://jobs.eu.lever.co/symphony/5d4ed3a5/apply", ("lever", "eu:symphony")),
    ("https://jobs.ashbyhq.com/Citizen%20Health/eaa76517", ("ashby", "Citizen Health")),
    ("https://jobs.smartrecruiters.com/Sportradar/744000160916289-staff", ("smartrecruiters", "Sportradar")),
    ("https://adesso1.recruitee.com/o/senior-ai-engineer", ("recruitee", "adesso1")),
    ("https://apply.workable.com/huggingface/j/ABC/", ("workable", "huggingface")),
    ("https://stoff2.jobs.personio.com/job/2888084/apply", ("personio", "stoff2")),
    ("https://hp.wd5.myworkdayjobs.com/pt-BR/ExternalCareerSite/job/x_1", ("workday", "hp|wd5|ExternalCareerSite")),
    ("https://www.linkedin.com/jobs/view/1/", None),
])
def test_which_ats_a_link_belongs_to(url, expected):
    assert ats_of(url) == expected


def test_addresses_and_keys_compare_written_two_ways():
    assert norm_url("https://Jobs.Lever.co/acme/1/apply?src=x") == norm_url("https://jobs.lever.co/acme/1/")
    assert dedupe_key("Acme, Inc.", "AI Engineer - Remote LATAM") == dedupe_key("ACME", "AI Engineer")
    assert text_of("&lt;p&gt;Oi&lt;/p&gt;&lt;ul&gt;&lt;li&gt;um&lt;/li&gt;&lt;/ul&gt;") == "Oi\n\n• um"


# ── The cheap filter ─────────────────────────────────────────────────────
def mk(title="Senior Financial Modeling Analyst", location="Remote - LATAM", description=LONG, **kw):
    return Job(kw.pop("source", "greenhouse"), kw.pop("sid", "1"), title, kw.pop("company", "Acme"), location, description,
               kw.pop("url", "https://job-boards.greenhouse.io/acme/jobs/1"), kw.pop("apply_url", "https://job-boards.greenhouse.io/acme/jobs/1"),
               kw.pop("posted_at", NOW), **kw)


@pytest.mark.parametrize("job,keep,mode,reason", [
    (mk(), True, "remoto-latam", ""),
    (mk(location="São Paulo, Brazil"), True, "brasil-local", ""),
    (mk(location="Remote", remote=True, countries=["Brazil"]), True, "remoto-br", ""),
    (mk(location="Worldwide"), True, "remoto-br", ""),
    (mk(location="Remote - US"), False, None, "us_no_visa"),
    (mk(location="Austin, TX"), False, None, "us_no_visa"),
    (mk(location="Berlin, Germany"), False, None, "europe_no_visa"),
    (mk(location="Lisbon, Portugal", description=LONG + " We provide visa sponsorship and relocation support."), True, "visto-eu", ""),
    (mk(location="Lisbon, Portugal", description=LONG + " Visa sponsorship: we are unable to provide visa sponsorship."), False, None, "europe_no_visa"),
    (mk(location="Remote - EMEA", remote=True, description=LONG + " Hired as an independent contractor through Deel."), True, "remoto-latam", ""),
    (mk(location="Bangalore, India"), False, None, "place"),
    (mk(location="Albuquerque, New Mexico"), False, None, "place"),   # not LATAM, whatever the word
    (mk(location="Remote", description=LONG.replace("Latin America", "the region") + " Candidates must be based in the United States."), False, None, "residency"),
    (mk(title="Junior Financial Analyst"), False, None, "title_other"),
    (mk(title="Account Executive"), False, None, "title_other"),
    (mk(title="Office Manager"), False, None, "title"),
    (mk(description="Wir suchen eine erfahrene Person für unser Team. Sie arbeiten mit der Finanzabteilung und die Modelle für "
                    "das Unternehmen. Wir bieten ein Team mit Erfahrung und ein gutes Gehalt. Die Stelle ist bei uns in der Firma "
                    "und für die Zukunft auf Dauer. Wir freuen uns auf die Bewerbung und das Gespräch mit Ihnen."), False, None, "language_de"),
])
def test_the_filter_keeps_what_can_be_done_from_brazil(job, keep, mode, reason):
    v = filters.judge(job)
    assert (v.keep, v.mode, v.reason) == (keep, mode, reason)


def test_families_follow_the_search_groups():
    assert filters.family("Senior FP&A Manager") == "financas"
    assert filters.family("Forward Deployed Engineer") == "ia"
    assert filters.family("Demand Forecasting Data Scientist") == "dados"
    assert filters.family("PPP Financial Advisor") == "nicho"


# ── Into the funnel ──────────────────────────────────────────────────────
def test_new_jobs_enter_once_with_their_form_and_family(db, sql):
    out = D.ingest([mk(sid="1"), mk(sid="2", title="Senior Data Scientist Forecasting", url="https://job-boards.greenhouse.io/acme/jobs/2",
                                    apply_url="https://job-boards.greenhouse.io/acme/jobs/2")])
    assert out["added"] == 2
    rows = sql("SELECT source, source_job_id, apply_url, status, search_slug, linkedin_job_id FROM public.job_listings ORDER BY id")
    assert rows[0] == {"source": "greenhouse", "source_job_id": "1", "apply_url": "https://job-boards.greenhouse.io/acme/jobs/1",
                       "status": "discovered", "search_slug": "financas:remoto-latam", "linkedin_job_id": None}
    again = D.ingest([mk(sid="1"), mk(sid="2", title="Senior Data Scientist Forecasting")])
    assert again["added"] == 0 and again["by_kind"]["greenhouse"]["known"] == 2


def test_the_same_job_on_another_board_or_on_linkedin_is_left_out(db, sql, add_job):
    add_job(job_id="555", company="Acme Inc.", title="Senior Financial Modeling Analyst")
    out = D.ingest([mk(source="remotive", sid="r1", url="https://remotive.com/x", apply_url="https://acme.com/apply")])
    assert out["added"] == 0 and out["by_kind"]["remotive"]["duplicates"] == 1
    # a LinkedIn job sent to its company form: the same form found on the board is the same job
    job = add_job(job_id="556", company="Beta", title="AI Engineer")
    sql("""INSERT INTO public.automation_actions (kind, lane, status, target_type, target_id, target_url, title, payload, payload_hash, idempotency_key)
           VALUES ('apply', 'ats', 'done', 'job', %s, 'https://jobs.lever.co/beta/abc/apply', 'x', '{}', '', 'apply:x')""", (job["id"],))
    out = D.ingest([mk(source="lever", sid="abc", title="Applied AI Engineer", company="Beta Labs", url="https://jobs.lever.co/beta/abc",
                       apply_url="https://jobs.lever.co/beta/abc/apply")])
    assert out["added"] == 0 and out["by_kind"]["lever"]["duplicates"] == 1


def test_old_ads_and_the_days_limit(db, sql):
    sql("UPDATE public.automation_limits SET step2 = 1 WHERE kind = 'source_read'")
    out = D.ingest([mk(sid="old", posted_at=NOW - timedelta(days=30)),
                    mk(sid="a", title="Senior FP&A Manager", url="https://x/a", apply_url="https://x/a", location="Worldwide"),
                    mk(sid="b", title="Lead AI Engineer", url="https://x/b", apply_url="https://x/b", location="Lisbon, Portugal",
                       description=LONG + " Visa sponsorship available.")])
    k = out["by_kind"]["greenhouse"]
    assert out["added"] == 1 and out["deferred"] == 1 and k["reasons"] == {"old": 1}
    assert sql("SELECT source_job_id FROM public.job_listings")[0]["source_job_id"] == "a"   # remote open to Brazil first


def test_linkedin_reads_keep_their_own_limit(db, sql):
    D.ingest([mk()])
    limits = {l["kind"]: l for l in Auto.limits()}
    assert limits["job_read"]["used"] == 0 and limits["source_read"]["used"] == 1


def test_a_job_board_pointing_to_a_company_board_adds_it(db, sql):
    D.ingest([mk(source="himalayas", sid="h1", url="https://himalayas.app/x", apply_url="https://jobs.ashbyhq.com/gamma/123")])
    assert sql("SELECT kind, slug, origin FROM public.job_sources") == [{"kind": "ashby", "slug": "gamma", "origin": "board"}]


# ── A round, failures and the watchlist ──────────────────────────────────
def test_a_round_reads_each_board_and_marks_a_company_that_left(db, sql, monkeypatch):
    monkeypatch.setattr(D, "probe_companies", staticmethod(lambda limit=None: 0))
    monkeypatch.setattr(D, "catalog", staticmethod(lambda: [{"kind": "greenhouse", "slug": "acme", "company": "Acme"},
                                                            {"url": "https://jobs.lever.co/gone/1", "company": "Gone"}]))
    Web(monkeypatch, {"https://boards-api.greenhouse.io/v1/boards/acme/jobs": {"jobs": [gh_job(1)], "meta": {}}})
    result = D.run_round("ats", ["greenhouse", "lever"])
    assert result["added"] == 1
    srcs = {r["slug"]: r for r in sql("SELECT slug, status, last_error_code, jobs_added FROM public.job_sources")}
    assert srcs["acme"]["status"] == "ok" and srcs["acme"]["jobs_added"] == 1
    assert srcs["gone"]["status"] == "gone" and srcs["gone"]["last_error_code"] == "not_found"
    runs = {r["kind"]: r for r in sql("SELECT kind, fetched, added, errors FROM public.discovery_runs")}
    assert runs["greenhouse"]["added"] == 1 and runs["lever"]["errors"] == 1


def test_a_changed_answer_is_saved_and_told(db, sql, monkeypatch):
    monkeypatch.setattr(D, "probe_companies", staticmethod(lambda limit=None: 0))
    monkeypatch.setattr(D, "catalog", staticmethod(lambda: []))
    D.add_source("remotive", "all", "Remotive", "catalog")
    Web(monkeypatch, {"https://remotive.com/api/remote-jobs": {"results": []}})
    D.run_round("board", ["remotive"])
    src = sql("SELECT status, last_error_code, last_error FROM public.job_sources WHERE kind = 'remotive'")[0]
    assert src["status"] == "failing" and src["last_error_code"] == "unexpected_layout" and "resposta guardada em" in src["last_error"]
    note = sql("SELECT kind, text FROM public.bot_notifications")[0]
    assert note["kind"] == "discovery" and "Remotive" in note["text"]


def test_the_probe_only_takes_a_board_that_is_that_company(db, sql, add_job, monkeypatch):
    job = add_job(job_id="1", company="Acme Analytics")
    sql("UPDATE public.job_listings SET triage_score = 90, employer_market = 'intl' WHERE id = %s", (job["id"],))
    job2 = add_job(job_id="2", company="Zeta")
    sql("UPDATE public.job_listings SET triage_score = 80, employer_market = 'intl' WHERE id = %s", (job2["id"],))
    Web(monkeypatch, {"https://boards-api.greenhouse.io/v1/boards/acmeanalytics": {"name": "Acme Analytics"},
                      "https://boards-api.greenhouse.io/v1/boards/zeta": {"name": "Zeta Global Holdings Other"}})
    assert D.probe_companies(10) == 1
    assert sql("SELECT kind, slug, origin FROM public.job_sources") == [{"kind": "greenhouse", "slug": "acmeanalytics", "origin": "probe"}]
    assert D.probe_companies(10) == 0   # tried once


def test_rounds_come_at_their_hours_once(db, monkeypatch):
    from zoneinfo import ZoneInfo
    at = lambda h: datetime(2026, 11, 23, h, 10, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert not D.due("ats", at(5)) and D.due("ats", at(6))
    Auto_rows = __import__("app.services.automation_service", fromlist=["_rows"])._rows
    Auto_rows("INSERT INTO public.discovery_runs (kind, started_at) VALUES ('round:board', %s)", (at(6),))
    assert not D.due("board", at(7)) and D.due("board", at(14))


def test_a_kind_switched_off_is_not_read(db, monkeypatch):
    monkeypatch.setattr(D, "probe_companies", staticmethod(lambda limit=None: 0))
    monkeypatch.setattr(D, "catalog", staticmethod(lambda: [{"kind": "greenhouse", "slug": "acme"}]))
    web = Web(monkeypatch, {})
    D.set_kind("greenhouse", False)
    D.run_round("ats", ["greenhouse"])
    assert web.calls == []


# ── Triage, the day's list and expiry ────────────────────────────────────
def fake_ai(monkeypatch, triage, eligibility=None, calls=None):
    from app.services import job_search_service

    async def run_skill(path, context, response_format="json"):
        if calls is not None:
            calls.append(path)
        return (eligibility or {"status": "ok", "issues": []}) if path == "jobs/eligibility.md" else triage
    monkeypatch.setattr(job_search_service.SkillService, "run_skill", staticmethod(run_skill))
    monkeypatch.setattr("app.services.job_pipeline_service.SkillService.run_skill", staticmethod(run_skill))


def test_the_eligibility_is_read_only_for_a_job_the_score_keeps(db, sql, monkeypatch):
    calls = []
    fake_ai(monkeypatch, {"score": 40, "reason": "Outra área", "employer_market": "intl"}, calls=calls)
    D.ingest([mk()])
    Search.triage_pending()
    assert calls == ["jobs/triage.md"]
    assert sql("SELECT triage_outcome, eligibility_status FROM public.job_listings")[0] == {"triage_outcome": "discarded", "eligibility_status": None}


def test_a_company_site_job_goes_straight_to_its_form(db, sql, monkeypatch):
    cfg = {**db, "jobs": {**db["jobs"], "external_apply": True}}
    monkeypatch.setattr("app.services.job_search_service.config", lambda: cfg)
    monkeypatch.setattr("app.services.automation_service.config", lambda: cfg)
    fake_ai(monkeypatch, {"score": 88, "reason": "Modelagem", "employer_market": "intl"})
    D.ingest([mk()])
    Search.triage_pending()
    action = sql("SELECT lane, target_url, payload FROM public.automation_actions WHERE kind = 'apply'")[0]
    assert action["lane"] == "ats" and action["target_url"] == "https://job-boards.greenhouse.io/acme/jobs/1"
    assert action["payload"]["source"] == "greenhouse"


def test_the_day_list_takes_the_best_first_and_keeps_the_rest(db, sql, monkeypatch):
    cfg = {**db, "jobs": {**db["jobs"], "external_apply": True}}
    monkeypatch.setattr("app.services.job_search_service.config", lambda: cfg)
    monkeypatch.setattr("app.services.automation_service.config", lambda: cfg)
    sql("UPDATE public.automation_limits SET step2 = 1 WHERE kind = 'job_propose'")
    scores = iter([75, 92])
    from app.services import job_search_service

    async def run_skill(path, context, response_format="json"):
        return {"status": "ok", "issues": []} if path == "jobs/eligibility.md" else {"score": next(scores), "reason": "r", "employer_market": "intl"}
    monkeypatch.setattr(job_search_service.SkillService, "run_skill", staticmethod(run_skill))
    monkeypatch.setattr("app.services.job_pipeline_service.SkillService.run_skill", staticmethod(run_skill))
    D.ingest([mk(sid="1"), mk(sid="2", title="Lead AI Engineer", url="https://x/2", apply_url="https://x/2")])
    Search.triage_pending()
    proposed = sql("""SELECT j.triage_score FROM public.automation_actions a JOIN public.job_listings j ON j.id = a.target_id""")
    assert proposed == [{"triage_score": 92}]
    held = sql("SELECT COUNT(*) AS n FROM public.job_listings WHERE triage_outcome = 'propose'")[0]["n"]
    assert held == 2   # the 75 waits for tomorrow's room


def test_a_proposal_left_for_10_days_expires_and_can_come_back(db, sql, add_job):
    job = add_job(status="discovered")
    sql("UPDATE public.job_listings SET triage_score = 72, triage_outcome = 'propose' WHERE id = %s", (job["id"],))
    action = Auto.propose_job(job)
    keep = add_job(job_id="101", status="discovered", company="Beta")
    sql("UPDATE public.job_listings SET triage_score = 85 WHERE id = %s", (keep["id"],))
    kept = Auto.propose_job(keep)
    sql("UPDATE public.automation_actions SET created_at = NOW() - INTERVAL '11 days'")
    Auto.expire_stale_proposals()
    status = {r["id"]: r["status"] for r in sql("SELECT id, status FROM public.automation_actions")}
    assert status == {action["id"]: "expired", kept["id"]: "proposed"}
    discarded = Auto.inbox()["discarded"]
    assert discarded[0]["id"] == job["id"] and discarded[0]["triage_reason"].startswith("Expirou: 10 dias")
    assert Auto.recover_job(job["id"])["status"] == "proposed"
    Auto.expire_stale_proposals()
    assert sql("SELECT status FROM public.automation_actions WHERE id = %s", (action["id"],))[0]["status"] == "proposed"


def test_stats_count_per_source(db, sql):
    D.ingest([mk()])
    rows = {r["kind"]: r for r in D.stats()["sources"]}
    assert rows["greenhouse"]["added"] == 1 and rows["remotive"]["added"] == 0 and rows["adzuna"]["last_error"] == "sem chave da API"


def test_one_incomplete_job_is_skipped_not_the_whole_board(monkeypatch):
    base = {"title": "AI Engineer", "jobUrl": "https://jobs.ashbyhq.com/acme/x", "descriptionPlain": LONG, "location": "Remote"}
    Web(monkeypatch, {"https://api.ashbyhq.com/": {"jobs": [{**base, "id": "x"}, {**base, "id": "y", "title": ""}]}})
    assert [j.source_job_id for j in sources._ashby("acme", "Acme")] == ["x"]
    Web(monkeypatch, {"https://api.ashbyhq.com/": {"jobs": [{"id": "z", "name": "AI Engineer"}]}})   # a key gone: the shape changed
    with pytest.raises(SourceError) as e:
        sources._ashby("acme", "Acme")
    assert e.value.code == "unexpected_layout"
