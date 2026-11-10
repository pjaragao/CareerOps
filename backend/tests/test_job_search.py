import asyncio
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from app.services import job_search_service
from app.services.automation_service import AutomationService as Auto
from app.services.job_search_service import GROUPS, MODES, JobSearchService as Search, parse_posted, place_ok, recent

NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("text,delta", [("2 hours ago", timedelta(hours=2)), ("há 3 horas", timedelta(hours=3)), ("Reposted 1 day ago", timedelta(days=1)),
                                        ("há 2 dias", timedelta(days=2)), ("30 minutes ago", timedelta(minutes=30)), ("1 week ago", timedelta(weeks=1)),
                                        ("just now", timedelta(0)), ("Posted 2h ago", timedelta(hours=2)), ("3d", timedelta(days=3))])
def test_parse_posted(text, delta):
    assert parse_posted(text, NOW) == NOW - delta


def test_parse_posted_unknown():
    assert parse_posted("", NOW) is None and parse_posted("Be an early applicant", NOW) is None


def test_catalog_has_the_tabs_groups_and_modes():
    assert len(GROUPS) == 4 and len(MODES) == 4


def test_linkedin_url_is_newest_first_and_last_48_hours(db):
    Search.ensure_seeds()
    search = next(s for s in Search.list_searches() if s["slug"] == "financas:remoto-br")
    q = parse_qs(urlparse(Search.linkedin_url(search)).query)
    assert q["sortBy"] == ["DD"] and q["f_TPR"] == ["r172800"] and q["f_WT"] == ["2"] and q["location"] == ["Brazil"] and q["geoId"] == ["106057199"]
    assert "f_AL" not in q   # both kinds come; each job is marked


def test_visa_search_has_no_remote_filter(db):
    Search.ensure_seeds()
    search = next(s for s in Search.list_searches() if s["slug"] == "financas:visto-eu")
    q = parse_qs(urlparse(Search.linkedin_url(search)).query)
    assert "f_WT" not in q and "visa sponsorship" in q["keywords"][0]


def test_rounds_cover_every_group_remote_and_rotate_visas(db):
    Search.ensure_seeds()
    days = [date(2026, 11, 1) + timedelta(days=i) for i in range(4)]
    rounds = [[s["slug"] for s in Search.round_for(d)] for d in days]
    assert all(len(r) == 10 for r in rounds)
    assert all({f"{g['id']}:{m}" for g in GROUPS for m in ("remoto-br", "remoto-latam")} <= set(r) for r in rounds)
    flat = {s for r in rounds for s in r}
    assert {"financas:visto-eu", "nicho:visto-eu", "financas:visto-us", "ia:visto-eu", "ia:visto-us"} <= flat


def test_forward_deployed_engineer_is_searched_with_ai_engineer(db, sql):
    Search.ensure_seeds()
    ia = next(s for s in Search.list_searches() if s["slug"] == "ia:remoto-br")
    assert '"forward deployed engineer"' in ia["keywords"] and '"AI engineer"' in ia["keywords"]


def test_seeds_update_the_keywords_but_keep_enabled(db, sql):
    Search.ensure_seeds()
    sql("UPDATE public.job_searches SET keywords = 'old', enabled = FALSE WHERE slug = 'ia:remoto-br'")
    Search.ensure_seeds()
    row = sql("SELECT keywords, enabled FROM public.job_searches WHERE slug = 'ia:remoto-br'")[0]
    assert "forward deployed" in row["keywords"] and row["enabled"] is False


@pytest.mark.parametrize("loc,mode,ok", [("Brazil (Remote)", "remoto-br", True), ("São Paulo, Brasil", "remoto-br", True),
                                         ("Latin America", "remoto-latam", True), ("Remote", "remoto-br", True), ("", "remoto-br", True),
                                         ("United States (Remote)", "remoto-br", False), ("London, England, United Kingdom", "remoto-latam", False),
                                         ("EMEA", "remoto-br", False), ("Lisbon, Portugal", "visto-eu", True), ("New York, NY", "visto-eu", False),
                                         ("Austin, TX", "visto-us", True), ("Brazil", "visto-us", False), ("Anywhere", None, True),
                                         ("Greater São Paulo Area (Remote)", "remoto-br", True), ("São Paulo, SP (Hybrid)", "remoto-br", False),
                                         ("Florianópolis, SC (On-site)", "remoto-latam", False), ("Amsterdam (Hybrid)", "visto-eu", True)])
def test_place_ok(loc, mode, ok):
    assert place_ok(loc, mode) is ok


def test_recent_is_48_hours():
    assert recent("47 hours ago", NOW) and recent("1 day ago", NOW) and recent("", NOW)
    assert not recent("3 days ago", NOW) and not recent("1 week ago", NOW)


def test_unseen_leaves_out_old_and_off_place_cards(db):
    cards = [{"id": "1", "location": "Brazil (Remote)", "posted": "2 hours ago"}, {"id": "2", "location": "Brazil (Remote)", "posted": "5 days ago"},
             {"id": "3", "location": "United States (Remote)", "posted": "1 hour ago"}, {"id": "4"}]
    out = Search.unseen(["1", "2", "3", "4"], cards, "ia:remoto-br")
    assert out["unseen"] == ["1", "4"] and out["skipped"] == {"old": 1, "place": 1}
    assert Search.unseen(["1", "2", "3"])["unseen"] == ["1", "2", "3"]   # without cards (saved jobs): only what is known


def test_an_ad_off_the_place_enters_discarded(db, sql):
    Search.ensure_seeds()
    Search.add_discovered([job(linkedin_job_id="9", location="Toronto, Canada")], "ia:remoto-br")
    row = sql("SELECT triage_score, triage_outcome, triage_reason FROM public.job_listings WHERE linkedin_job_id = '9'")[0]
    assert row["triage_score"] == 0 and row["triage_outcome"] == "discarded" and "Toronto" in row["triage_reason"]


def test_a_disabled_search_is_left_out(db, sql):
    Search.ensure_seeds()
    sql("UPDATE public.job_searches SET enabled = FALSE WHERE slug = 'financas:remoto-br'")
    assert "financas:remoto-br" not in [s["slug"] for s in Search.round_for(date(2026, 11, 2))]


def job(**kw):
    return {"linkedin_job_id": "1", "title": "t", "company": "c", "location": "l", "description": "d", "posted": "1 hour ago", "easy_apply": True, **kw}


def test_discovered_jobs_get_no_documents_and_stay_out_of_the_board(db, sql):
    from app.services.job_pipeline_service import JobPipelineService
    from app.services.job_service import JobService
    assert Search.add_discovered([job()], None) == 1
    row = sql("SELECT status, posted_at, resume_markdown FROM public.job_listings")[0]
    assert row["status"] == "discovered" and row["posted_at"] and row["resume_markdown"] is None
    assert JobPipelineService.pending_ids() == []
    assert JobService.get_jobs("all") == []


@pytest.mark.parametrize("status", ["discovered", "archived", "rejected", "applied"])
def test_a_known_job_is_never_touched_again(db, sql, add_job, status):
    add_job("1", status=status)
    assert Search.add_discovered([job(title="outro título")], None) == 0
    assert sql("SELECT status, job_title FROM public.job_listings")[0]["status"] == status
    assert Search.unseen(["1"])["unseen"] == []


def test_a_job_without_description_is_skipped(db):
    assert Search.add_discovered([job(description="  ")], None) == 0


def test_reading_budget_counts_todays_jobs(db, sql):
    Search.ensure_seeds()
    Search.add_discovered([job(linkedin_job_id=str(i)) for i in range(3)], "financas:remoto-br")
    assert Search.unseen(["x"])["budget"] == 97   # 100 a day since migrations_v18
    assert sql("SELECT jobs_found FROM public.job_searches WHERE slug = 'financas:remoto-br'")[0]["jobs_found"] == 3


@pytest.mark.parametrize("job_row,triage,eligibility,expected", [
    ({"easy_apply": True}, {"score": 85, "employer_market": "intl"}, {"status": "ok"}, "propose"),
    ({"easy_apply": True}, {"score": 70, "employer_market": "unknown"}, {"status": "warning"}, "propose"),
    ({"easy_apply": True}, {"score": 69, "employer_market": "intl"}, {"status": "ok"}, "discarded"),
    ({"easy_apply": True}, {"score": 95, "employer_market": "br"}, {"status": "ok"}, "discarded"),
    ({"easy_apply": True}, {"score": 95, "employer_market": "intl"}, {"status": "blocked"}, "discarded"),
    ({"easy_apply": False}, {"score": 85, "employer_market": "intl"}, {"status": "ok"}, "external_manual"),
])
def test_triage_decision(db, job_row, triage, eligibility, expected):
    assert Search.decide(job_row, triage, eligibility) == expected


def test_a_foreign_company_hiring_in_brazil_passes_and_markets_can_change(db, monkeypatch):
    t = {"score": 90, "employer_market": "br"}
    cfg = {**db, "jobs": {**db["jobs"], "markets": ["intl", "br"]}}
    monkeypatch.setattr(job_search_service, "config", lambda: cfg)
    assert Search.decide({"easy_apply": True}, t, {"status": "ok"}) == "propose"


def test_external_goes_to_the_queue_when_switched_on(db, monkeypatch):
    cfg = {**db, "jobs": {**db["jobs"], "external_apply": True}}
    monkeypatch.setattr(job_search_service, "config", lambda: cfg)
    assert Search.decide({"easy_apply": False}, {"score": 90, "employer_market": "intl"}, {"status": "ok"}) == "propose"


def fake_ai(monkeypatch, eligibility, triage):
    async def run_skill(path, context, response_format="json"):
        return eligibility if path == "jobs/eligibility.md" else triage
    monkeypatch.setattr(job_search_service.SkillService, "run_skill", staticmethod(run_skill))
    monkeypatch.setattr("app.services.job_pipeline_service.SkillService.run_skill", staticmethod(run_skill))


def test_triage_end_to_end_proposes_a_good_foreign_job(db, sql, monkeypatch):
    fake_ai(monkeypatch, {"status": "ok", "issues": []}, {"score": 88, "reason": "Modelagem financeira", "employer_market": "intl", "salary_flag": None})
    Search.add_discovered([job()], None)
    assert Search.triage_pending() == 1
    box = Auto.inbox()
    assert len(box["apply"]) == 1 and box["apply"][0]["triage_score"] == 88 and box["discarded"] == []


def test_triage_discards_a_brazilian_employer_with_the_reason_and_it_can_be_recovered(db, sql, monkeypatch):
    fake_ai(monkeypatch, {"status": "ok", "issues": []}, {"score": 90, "reason": "Boa aderência", "employer_market": "br"})
    Search.add_discovered([job()], None)
    Search.triage_pending()
    box = Auto.inbox()
    assert box["apply"] == [] and "brasileiro" in box["discarded"][0]["triage_reason"]
    assert Auto.recover_job(box["discarded"][0]["id"])
    assert len(Auto.inbox()["apply"]) == 1


def test_triage_records_a_salary_below_the_floor_without_discarding(db, sql, monkeypatch):
    fake_ai(monkeypatch, {"status": "ok", "issues": []}, {"score": 80, "reason": "r", "employer_market": "intl", "salary_flag": "Anúncio: até USD 4.000/mês"})
    Search.add_discovered([job()], None)
    Search.triage_pending()
    assert "4.000" in Auto.inbox()["apply"][0]["salary_flag"]


def test_triage_failure_is_tried_again_later(db, sql, monkeypatch):
    fake_ai(monkeypatch, {"status": "ok", "issues": []}, {"error": "quota"})
    Search.add_discovered([job()], None)
    assert Search.triage_pending() == 0
    assert sql("SELECT triage_score FROM public.job_listings")[0]["triage_score"] is None


def test_schedule_puts_a_round_in_the_queue_once(db, sql, monkeypatch):
    from app.services import automation_service
    Search.ensure_seeds()
    cfg = {**db, "automation": {**db["automation"], "search_hours": [0], "check_hours": [0], "feed_scan_hours": [], "follow_scan_hours": [],
                                             "reply_scan_hours": [], "inbox_scan_hours": []}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    first = Auto.schedule_reads()
    assert first == 11 and Auto.schedule_reads() == 0
    kinds = {r["kind"]: r["n"] for r in sql("SELECT kind, COUNT(*) AS n FROM public.automation_actions GROUP BY kind")}
    assert kinds == {"search": 10, "check": 1}


def test_follow_scan_walks_the_plan_without_repeating(db, sql):
    from psycopg2.extras import Json
    sql("INSERT INTO public.linkedin_networking_plans (plan) VALUES (%s)", (Json({
        "companies": [{"company": "Acme", "url": "https://www.linkedin.com/search/results/companies/?keywords=Acme", "market": "intl", "similar": False}],
        "follow": [{"role": "CFO", "search": "CFO fintech", "url": "https://www.linkedin.com/search/results/people/?keywords=CFO", "market": "intl"}]}),))
    first = Search.next_follow_scan()
    assert first["mode"] == "company"
    Auto.create_action("follow_scan", f"follow_scan:{first['key']}", "x", first["url"], first, status="queued")
    assert Search.next_follow_scan()["mode"] == "people"


def test_follow_target_is_proposed_once_by_address(db):
    assert Auto.follow_target("https://www.linkedin.com/company/acme/?x=1", "Acme")
    assert Auto.follow_target("https://www.linkedin.com/company/ACME", "Acme") is None
    assert len(Auto.inbox()["follow"]) == 1


def test_a_job_you_added_gets_a_fit_score_and_is_never_discarded(db, sql, add_job, monkeypatch):
    fake_ai(monkeypatch, {"status": "ok", "issues": []}, {"score": 40, "reason": "Outra área", "employer_market": "br"})
    action = Auto.propose_job(add_job(status="new"))
    assert Search.score_proposed() == 1
    item = Auto.inbox()["items"][0]
    assert item["id"] == action["id"] and item["fit"] == 40 and item["triage_reason"] == "Outra área"
    assert Search.score_proposed() == 0   # scored once


def test_a_job_you_already_applied_to_leaves_the_approval_list(db, sql, add_job):
    job = add_job(status="new")
    action = Auto.propose_job(job)
    sql("UPDATE public.job_listings SET status = 'applied' WHERE id = %s", (job["id"],))
    Auto.expire_stale_proposals()
    assert Auto.inbox()["items"] == []
    assert sql("SELECT status, error_text FROM public.automation_actions WHERE id = %s", (action["id"],))[0]["status"] == "discarded"


def test_v15_runs_again_after_v17_rows_exist(db, sql):
    """Every start applies v15 again: its kind check must take the kinds v17 added (it failed there from 2026-11-08 to 11-10)."""
    sql("""INSERT INTO public.automation_actions (kind, lane, status, title, payload, payload_hash, idempotency_key)
           VALUES ('inbox_scan', 'linkedin_read', 'done', 'x', '{}', '', 'k-v17')""")
    Auto_schema = __import__("app.services.automation_service", fromlist=["ensure_schema"]).ensure_schema
    Auto_schema()
    assert sql("SELECT step0 FROM public.automation_limits WHERE kind = 'job_read'")[0]["step0"] == 100
