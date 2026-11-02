"""The reviewer agent: it reads the CV and the cover letter in your place and sends them back to be redone."""
import asyncio

import pytest

from app.services import cv_review_service as cr
from app.services.automation_service import AutomationService as Auto, _one
from app.services.bot_service import BotService
from app.services.cv_review_service import CvReviewService, quick_issues

CLEAN = {"issues": [{"doc": "resume", "severity": "minor", "problem": "verbo fraco", "fix": "Use stronger verbs"}],
         "resume_instructions": "", "cover_instructions": "", "summary": "Bom"}
INVENTED = {"issues": [{"doc": "resume", "severity": "critical", "problem": "certificação AWS inventada", "fix": "Remove the AWS certification"}],
            "resume_instructions": "Remove the AWS certification", "cover_instructions": "", "summary": "Inventou certificação"}


@pytest.fixture
def reviewer(monkeypatch):
    """The AIs replaced: the reviewer answers from a list, the writer records what it was told."""
    state = {"readings": [], "redone": []}

    async def run_skill(path, context, response_format="json"):
        assert path == "jobs/cv_review.md" and context["resume_base"] == "BASE"
        return state["readings"].pop(0) if len(state["readings"]) > 1 else state["readings"][0]

    async def generate_resume(job_id, options):
        state["redone"].append(("resume", options.orientation))
        return {"content": "CV"}

    async def generate_cover_letter(job_id, options):
        state["redone"].append(("cover", options.orientation))
        return {"content": "Carta"}

    from app.api import actions
    from app.services.profile_service import ProfileService
    monkeypatch.setattr(cr.SkillService, "run_skill", staticmethod(run_skill))
    monkeypatch.setattr(actions, "generate_resume", generate_resume)
    monkeypatch.setattr(actions, "generate_cover_letter", generate_cover_letter)
    monkeypatch.setattr(ProfileService, "get_resume_base", staticmethod(lambda lang: "BASE"))
    monkeypatch.setattr(cr, "pdf_pages", lambda md, name="resume.pdf": 2)
    return state


def test_what_needs_no_ai_is_caught_first():
    kinds = lambda issues: [(i["doc"], i["severity"], i["problem"].split(":")[0]) for i in issues]
    assert kinds(quick_issues("Dear [Company Name], ...", "Carta", 2)) == [("resume", "critical", "sobra de modelo")]
    assert kinds(quick_issues("CV", "", 3)) == [("cover", "critical", "documento vazio"), ("resume", "major", "o PDF tem 3 páginas")]
    assert "write at most" in quick_issues("CV", "Carta", 3)[0]["fix"]
    assert kinds(quick_issues("Trabalhei com aterro sanitário", "Carta", 1))[0][2] == "termo proibido (NDA)"
    assert quick_issues("CV limpo", "Carta limpa", 2) == []
    assert kinds(quick_issues("CV", "Sincerely,\n[Candidate Name]", 2)) == [("cover", "critical", "sobra de modelo")]
    assert quick_issues("CV [LinkedIn profile name](https://linkedin.com/in/x)", "Carta", 2) == []   # a link is not a leftover
    long = quick_issues("ab " * 3000, "Carta", 3)[0]["fix"]
    assert "at most 5400 characters" in long


def test_a_clean_cv_goes_with_minor_notes(db, add_job, reviewer):
    job = add_job(status="new")
    reviewer["readings"] = [CLEAN]
    verdict = asyncio.run(CvReviewService.run(job["id"]))
    assert verdict["approved"] and verdict["rounds"] == 0 and reviewer["redone"] == []


def test_an_invented_fact_is_sent_back_and_redone(db, add_job, reviewer):
    job = add_job(status="new")
    reviewer["readings"] = [INVENTED, CLEAN]
    verdict = asyncio.run(CvReviewService.run(job["id"]))
    assert verdict["approved"] and verdict["rounds"] == 1
    assert reviewer["redone"] == [("resume", cr.REDO + "- Remove the AWS certification\nRemove the AWS certification")]


def test_it_gives_up_after_the_rounds(db, add_job, reviewer):
    job = add_job(status="new")
    reviewer["readings"] = [INVENTED]
    verdict = asyncio.run(CvReviewService.run(job["id"], rounds=2))
    assert not verdict["approved"] and verdict["rounds"] == 2 and len(reviewer["redone"]) == 2 and len(verdict["history"]) == 3


@pytest.fixture
def approved_job(db, add_job, sql, monkeypatch):
    from app.services.job_pipeline_service import JobPipelineService

    async def generate_docs(job_id):
        return []
    monkeypatch.setattr(JobPipelineService, "generate_docs", staticmethod(generate_docs))
    db["jobs"]["cv_review"] = "agent"
    job = add_job(status="new")
    action = Auto.propose_job(job)
    Auto.approve(action["id"])
    return action


def test_approved_by_the_reviewer_goes_to_the_queue_without_you(approved_job, reviewer, sql):
    sql("UPDATE public.automation_state SET review_cv_left = 20")   # the old "you read the first 20" no longer applies
    reviewer["readings"] = [CLEAN]
    Auto.prepare_documents()
    assert _one("SELECT status FROM public.automation_actions WHERE id = %s", (approved_job["id"],))["status"] == "queued"
    event = _one("SELECT * FROM public.automation_events WHERE action_id = %s AND event = 'cv_review'", (approved_job["id"],))
    assert event["data"]["approved"] is True


def test_still_wrong_after_the_rounds_it_waits_for_you_with_the_reasons(approved_job, reviewer, sql, monkeypatch):
    monkeypatch.setattr(BotService, "quiet", staticmethod(lambda: False))
    reviewer["readings"] = [INVENTED]
    Auto.prepare_documents()
    action = _one("SELECT * FROM public.automation_actions WHERE id = %s", (approved_job["id"],))
    assert action["status"] == "review_docs" and action["error_code"] == "cv_review_failed"
    assert "certificação AWS inventada" in action["error_text"]
    BotService.collect()
    told = sql("SELECT text FROM public.bot_notifications WHERE kind = 'action_review_docs'")[0]["text"]
    assert "O revisor não aprovou" in told and "certificação AWS inventada" in told


def test_only_the_document_with_a_problem_is_redone(db, add_job, reviewer):
    job = add_job(status="new")
    reviewer["readings"] = [{**INVENTED, "cover_instructions": "Mention the company culture"}, CLEAN]
    asyncio.run(CvReviewService.run(job["id"]))
    assert [doc for doc, _ in reviewer["redone"]] == ["resume"]
