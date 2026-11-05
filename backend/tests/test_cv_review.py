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
    [(doc, told)] = reviewer["redone"]
    assert doc == "resume" and told.startswith(cr.REDO + "- Remove the AWS certification")
    assert "PREVIOUS VERSION" in told and "stays within" in told   # it edits the version it read, at a size that fits


def test_a_redone_version_is_judged_against_what_was_asked(db, add_job, reviewer, monkeypatch):
    seen = []

    async def run_skill(path, context, response_format="json"):
        seen.append(context["previous_fixes"])
        return INVENTED if len(seen) == 1 else CLEAN
    monkeypatch.setattr(cr.SkillService, "run_skill", staticmethod(run_skill))
    asyncio.run(CvReviewService.run(add_job(status="new")["id"]))
    assert seen[0] == "" and "Remove the AWS certification" in seen[1]


def test_what_the_candidate_lacks_does_not_send_it_back(db, add_job, reviewer):
    reviewer["readings"] = [{"issues": [{"doc": "cover", "severity": "gap", "problem": "the job asks for German"}],
                             "resume_instructions": "", "cover_instructions": "", "summary": "ok"}]
    verdict = asyncio.run(CvReviewService.run(add_job(status="new")["id"]))
    assert verdict["approved"] and reviewer["redone"] == [] and verdict["issues"][0]["gap"]


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
    told = sql("SELECT text FROM public.bot_notifications WHERE kind = 'summary'")[0]["text"]
    assert "1 CV para revisar" in told   # the reasons are on the site, behind the link


def test_only_the_document_with_a_problem_is_redone(db, add_job, reviewer):
    job = add_job(status="new")
    reviewer["readings"] = [{**INVENTED, "cover_instructions": "Mention the company culture"}, CLEAN]
    asyncio.run(CvReviewService.run(job["id"]))
    assert [doc for doc, _ in reviewer["redone"]] == ["resume"]


def test_trying_again_writes_the_documents_from_scratch(approved_job, reviewer, sql):
    reviewer["readings"] = [INVENTED]
    Auto.prepare_documents()
    sql("UPDATE public.job_listings SET resume_markdown = 'old CV', cover_letter = 'old letter' WHERE id = %s", (approved_job["target_id"],))
    assert Auto.retry(approved_job["id"])["status"] == "approved"
    job = _one("SELECT resume_markdown, cover_letter FROM public.job_listings WHERE id = %s", (approved_job["target_id"],))
    assert job == {"resume_markdown": None, "cover_letter": None}


def test_the_first_resume_is_asked_at_a_size_that_fits_two_pages():
    prompt = asyncio.run(cr.SkillService.render_prompt("jobs/resume.md", {"job_title": "x", "company": "y", "lang_name": "English",
                                                                            "job_description": "d", "resume_base": "b", "max_chars": 4800, "orientation": ""}))
    assert "at most 4800" in prompt


LONG = {"issues": [{"doc": "resume", "severity": "major", "problem": "o PDF tem 3 páginas", "fix": "The resume must fit in 2 pages"}],
        "resume_instructions": "", "cover_instructions": "", "summary": "Longo"}
CV3 = "# Name\n\n## EXPERIENCE\n### Role A\n- a1\n- a2\n- a3\n### Role B\n- b1\n- b2\n- b3\n- b4\n"


def test_trimming_cuts_the_longest_section_and_keeps_headings():
    once = cr.trim_once(CV3)
    assert "- b4" not in once and "- a3" in once and "### Role B" in once
    assert cr.trim_once("# N\n### R\n- only\n") is None   # each section keeps its first bullet


def test_fit_pages_cuts_until_two_pages():
    fitted = cr.fit_pages(CV3, pages_of=lambda md: 3 if md.count("\n- ") > 4 else 2)
    assert fitted.count("\n- ") == 4 and "### Role A" in fitted and "### Role B" in fitted
    assert cr.fit_pages("# N\n### R\n- x\n", pages_of=lambda md: 3) is None


def test_too_long_after_the_rounds_the_reviewer_cuts_it_itself(db, add_job, reviewer, sql, monkeypatch):
    job = add_job(status="new")
    sql("UPDATE public.job_listings SET resume_markdown = %s, cover_letter = 'Carta' WHERE id = %s", (CV3, job["id"]))
    monkeypatch.setattr(cr, "pdf_pages", lambda md, name="resume.pdf": 3 if md.count("\n- ") > 5 else 2)
    reviewer["readings"] = [LONG, LONG, LONG, CLEAN]
    verdict = asyncio.run(CvReviewService.run(job["id"], rounds=2))
    assert verdict["approved"] and verdict.get("trimmed")
    assert _one("SELECT resume_markdown FROM public.job_listings WHERE id = %s", (job["id"],))["resume_markdown"].count("\n- ") == 5


def test_a_content_problem_is_never_trimmed_away(db, add_job, reviewer):
    job = add_job(status="new")
    reviewer["readings"] = [INVENTED]
    verdict = asyncio.run(CvReviewService.run(job["id"], rounds=2))
    assert not verdict["approved"] and not verdict.get("trimmed")


def test_the_reviewer_comment_says_what_to_fix_one_line_each():
    text = cr.reasons({"issues": INVENTED["issues"] + CLEAN["issues"], "summary": "Inventou certificação"})
    assert "• CV: certificação AWS inventada → Remove the AWS certification" in text
    assert "◦ CV (observação): verbo fraco" in text and "Resumo do revisor: Inventou certificação" in text
