"""Your saved jobs on LinkedIn, read by the server browser: when (Configurações), outside the window of the rest, on demand
(Lolo or the button), and what they become."""
from datetime import datetime

from app.services import automation_service
from app.services.automation_service import AutomationService as Auto, _one
from app.services.bot_service import BotService
from app.services.job_search_service import JobSearchService as Search
from tests.conftest import APPROVER, BOT, WORKER

DEFAULT = {"enabled": True, "day_start": 8, "day_end": 24, "day_every": 1, "night_every": 2}


def at(hour):
    return datetime(2026, 11, 3, hour, 5)


def only_saved_reads(db, monkeypatch, **automation):
    """The other reads of the day out of the way."""
    cfg = {**db, "automation": {**db["automation"], "search_hours": [], "check_hours": [], "feed_scan_hours": [], "follow_scan_hours": [], **automation}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)


def slots(settings):
    return [h for h in range(24) if Auto.saved_import_due(at(h), settings)]


def test_hourly_by_day_and_every_two_hours_at_night():
    assert slots(DEFAULT) == [0, 2, 4, 6] + list(range(8, 24))


def test_other_hours_and_a_night_without_reads():
    assert slots({**DEFAULT, "day_start": 9, "day_end": 18, "day_every": 3, "night_every": 0}) == [9, 12, 15]
    assert slots({**DEFAULT, "day_start": 22, "day_end": 6, "day_every": 2, "night_every": 4}) == [0, 2, 4, 6, 10, 14, 18, 22]
    assert slots({**DEFAULT, "enabled": False}) == []


def test_a_slot_puts_one_read_in_the_queue(db, sql, monkeypatch):
    only_saved_reads(db, monkeypatch)
    Auto.set_saved_import(**DEFAULT)
    monkeypatch.setattr(automation_service, "_local", lambda: at(10))
    assert Auto.schedule_reads() == 1 and Auto.schedule_reads() == 0
    row = sql("SELECT * FROM public.automation_actions WHERE kind = 'saved_import'")[0]
    assert row["lane"] == "linkedin_read" and row["target_url"] == automation_service.SAVED_JOBS_URL and not row["run_now"]
    # the next slot does not pile up on one still waiting
    monkeypatch.setattr(automation_service, "_local", lambda: at(11))
    assert Auto.schedule_reads() == 0


def test_it_runs_outside_the_window_and_the_other_reads_wait(db, sql, monkeypatch):
    only_saved_reads(db, monkeypatch, window={"start_hour": 8, "end_hour": 20})
    monkeypatch.setattr(automation_service, "_local", lambda: at(2))
    Auto.set_saved_import(**DEFAULT)
    search = Auto.create_action("search", "s1", "Busca", "https://www.linkedin.com/jobs/search-results/?keywords=x", {}, status="queued", rank=1)
    Auto.schedule_reads()
    got = Auto.claim("linkedin_read", "test")["action"]
    assert got["kind"] == "saved_import"
    assert _one("SELECT status FROM public.automation_actions WHERE id = %s", (search["id"],))["status"] == "queued"


def test_on_demand_runs_now_once_and_replaces_a_failed_one(db, sql):
    failed = Auto.create_action("saved_import", "saved_import:old", "Vagas salvas", automation_service.SAVED_JOBS_URL, {}, status="queued")
    sql("UPDATE public.automation_actions SET status = 'needs_user' WHERE id = %s", (failed["id"],))
    first = Auto.run_saved_import()
    assert first["run_now"] and first["status"] == "queued"
    assert _one("SELECT status FROM public.automation_actions WHERE id = %s", (failed["id"],))["status"] == "cancelled"
    again = Auto.run_saved_import()
    assert again["id"] == first["id"] and again["already"]


def test_what_it_finds_goes_in_as_new_and_what_you_decided_stays(db, sql, add_job, monkeypatch):
    from app.services.job_pipeline_service import JobPipelineService
    monkeypatch.setattr(JobPipelineService, "kick", classmethod(lambda cls: None))
    add_job("201", status="discovered")
    add_job("202", status="archived")
    add_job("203", status="applied")
    out = Search.add_saved([{"linkedin_job_id": "204", "title": "FP&A Lead", "company": "ElevenLabs", "location": "Remote",
                             "description": "Texto do anúncio", "easy_apply": True},
                            {"linkedin_job_id": "205", "title": "Sem texto", "description": ""}],
                           ["201", "202", "203", "204", "205"])
    assert out == {"added": 1, "promoted": 1}
    status = {r["linkedin_job_id"]: r["status"] for r in sql("SELECT linkedin_job_id, status FROM public.job_listings")}
    assert status == {"201": "new", "202": "archived", "203": "applied", "204": "new"}
    # the new ones reach the approval list like a job you imported by hand
    Auto.sync_proposals()
    assert {r["target_id"] for r in sql("SELECT target_id FROM public.automation_actions WHERE kind = 'apply'")} == \
        {r["id"] for r in sql("SELECT id FROM public.job_listings WHERE linkedin_job_id IN ('201', '204')")}


def test_lolo_is_told_what_came_in_only_when_he_asked(db, sql, monkeypatch):
    monkeypatch.setattr(BotService, "quiet", staticmethod(lambda: False))
    scheduled = Auto.create_action("saved_import", "saved_import:x", "Vagas salvas", automation_service.SAVED_JOBS_URL, {}, status="queued")
    asked = Auto.run_saved_import()
    for a, result in ((scheduled, {"cards": 15, "known": 15}), (asked, {"cards": 15, "known": 12, "added": 3, "promoted": 0})):
        sql("UPDATE public.automation_actions SET status = 'done', result = %s, finished_at = NOW() WHERE id = %s",
            (automation_service.Json(result), a["id"]))
    BotService.collect()
    texts = [r["text"] for r in sql("SELECT text FROM public.bot_notifications")]
    assert texts == [f"📥 *Vagas salvas* #{asked['id']}: 3 nova(s) no CareerOps, a caminho da lista para aprovar; 12 já estava(m) lá."]


def test_settings_and_run_through_the_api(db, client):
    assert client.get("/api/automation/saved-import", headers=WORKER).status_code == 401
    r = client.put("/api/automation/saved-import", headers=APPROVER, json={**DEFAULT, "day_every": 2, "night_every": 0})
    assert r.status_code == 200 and r.json()["day_every"] == 2
    assert client.put("/api/automation/saved-import", headers=BOT, json=DEFAULT).status_code == 401
    assert client.put("/api/automation/saved-import", headers=APPROVER, json={**DEFAULT, "day_every": 0}).status_code == 422
    assert client.get("/api/automation/saved-import", headers=APPROVER).json()["settings"]["night_every"] == 0
    run = client.post("/api/automation/saved-import/run", headers=BOT)
    assert run.status_code == 200 and run.json()["run_now"] and run.json()["mode"] == "live"
    saved = client.post("/api/automation/saved-jobs", headers=WORKER, json={"jobs": [], "ids": ["1"]})
    assert saved.status_code == 200 and saved.json() == {"added": 0, "promoted": 0}
