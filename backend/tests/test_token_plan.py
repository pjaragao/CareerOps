"""Token plan, phase 3: documents on demand, one CV per job family, one cover letter per company, model hint per host."""
import asyncio

from app.services.automation_service import AutomationService as Auto, _one, _rows
from app.services.site_service import TextCache, archetype_of, text_key


def test_archetypes_and_keys():
    assert archetype_of("Senior AI Engineer (GenAI & LLMs)") == "ai_engineering"
    assert archetype_of("Senior Strategic Planning & Controlling Manager") == "finance"
    assert archetype_of("Associate Water Sector Specialist") == "infrastructure"
    assert archetype_of("Head Chef") is None
    assert text_key("cover", "Acme Corp.", "en") == "cover:acme-corp:en"


def test_documents_are_not_written_for_every_import(db, add_job, monkeypatch):
    from app.services import job_pipeline_service as jp
    called = []
    monkeypatch.setattr(jp.JobPipelineService, "check_eligibility", staticmethod(lambda job_id: asyncio.sleep(0, {"status": "ok", "issues": []})))

    async def fake(job_id):
        called.append(job_id)
        return ["resume"]
    monkeypatch.setattr(jp.JobPipelineService, "generate_docs", staticmethod(fake))
    job = add_job(resume=None, cover=None)
    asyncio.run(jp.JobPipelineService.process(job["id"]))
    assert called == []


def test_a_family_cv_and_a_company_letter_are_reused(db, add_job, monkeypatch):
    from app.api import actions
    from app.services.job_pipeline_service import JobPipelineService
    made = []

    async def resume(job_id, options):
        made.append("resume")
        return {"content": ""}

    async def cover(job_id, options):
        made.append("cover")
        return {"content": ""}
    monkeypatch.setattr(actions, "generate_resume", resume)
    monkeypatch.setattr(actions, "generate_cover_letter", cover)
    from app.services.portfolio_service import PortfolioService
    monkeypatch.setattr(PortfolioService, "attach", staticmethod(lambda job_id, content: content))   # migrations_v16 is not in the test schema
    job_id = add_job(resume=None, cover=None)["id"]
    row = _one("SELECT job_title, company FROM public.job_listings WHERE id = %s", (job_id,))
    arch = archetype_of(row["job_title"] or "")
    if arch:
        TextCache.put(text_key("cv", arch, "en"), "cv", "# Paulo\ncached cv")
    TextCache.put(text_key("cover", row["company"], "en"), "cover", "Dear team, cached letter")
    out = asyncio.run(JobPipelineService.generate_docs(job_id))
    got = _one("SELECT resume_markdown, cover_letter FROM public.job_listings WHERE id = %s", (job_id,))
    assert got["cover_letter"] == "Dear team, cached letter" and "cover_cached" in out and "cover" not in made
    if arch:
        assert got["resume_markdown"].endswith("cached cv") and "resume_archetype" in out and "resume" not in made


def test_haiku_is_skipped_where_it_never_finished(db):
    a = Auto.create_action("apply", "apply:5", "Vaga", "https://jobs.hard.example/1", {}, status="escalated", target_type="job", target_id=5)
    for _ in range(3):
        _rows("INSERT INTO public.automation_runs (kind, action_id, ok, model, host) VALUES ('claude', %s, FALSE, 'claude-haiku-5-5', 'jobs.hard.example')", (a["id"],))
    assert Auto.model_hint(a) == {"skip_haiku": True}
    _rows("INSERT INTO public.automation_runs (kind, action_id, ok, model, host) VALUES ('claude', %s, TRUE, 'claude-haiku-5-5', 'jobs.hard.example')", (a["id"],))
    assert Auto.model_hint(a) == {"skip_haiku": False}
