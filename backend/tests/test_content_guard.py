import subprocess
from pathlib import Path

import pytest

from app.services import content_guard
from app.services.skill_service import SkillService

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("text", ["water, drainage and solid waste", "Solid-waste infrastructure", "resíduos sólidos urbanos", "RESIDUOS SOLIDOS",
                                  "um aterro sanitário", "sanitary landfill", "gestão de resíduos", "waste management"])
def test_finds_the_subject_in_any_form(text):
    assert content_guard.forbidden_in(text)


@pytest.mark.parametrize("text", ["water, wastewater and drainage", "corte e aterro da obra", "wastewater treatment", "resíduo de cálculo"])
def test_leaves_other_things_alone(text):
    assert content_guard.forbidden_in(text) == []


def test_looks_inside_a_json_answer():
    assert content_guard.forbidden_in({"a": [{"b": "solid waste"}], "c": 1})


def test_no_versioned_text_cites_it():
    """Only the guard's own rules and these tests may contain the terms."""
    out = subprocess.run(["git", "grep", "-lIiE", r"res[ií]duos? s[oó]lidos?|solid[ -]waste|aterros? sanit|landfill", "--", ".",
                          ":!config/automation.yml", ":!backend/tests", ":!automation/tests"], cwd=ROOT, capture_output=True, text=True)
    untracked = subprocess.run(["grep", "-rlIiE", r"res[ií]duos? s[oó]lidos?|solid[ -]waste|aterros? sanit|landfill", "config", "backend/app/skills", "international", "docs"],
                               cwd=ROOT, capture_output=True, text=True)
    assert out.stdout.strip() == ""
    assert [f for f in untracked.stdout.split() if f != "config/automation.yml"] == []


def test_outgoing_text_is_rewritten_once_and_only_once():
    prompts = []

    def generate(prompt):
        prompts.append(prompt)
        return "clean text" if len(prompts) == 2 else "solid waste plans"

    assert SkillService.generate_checked("jobs/cover_letter.md", "prompt", generate) == "clean text"
    assert len(prompts) == 2 and "forbidden" in prompts[1]


def test_outgoing_text_that_keeps_it_is_refused():
    with pytest.raises(content_guard.BlockedContent):
        SkillService.generate_checked("jobs/resume.md", "prompt", lambda p: {"resume_markdown": "sanitary landfill"})


def test_reading_someone_elses_text_is_not_blocked():
    assert SkillService.generate_checked("jobs/eligibility.md", "p", lambda p: {"quote": "solid waste"}) == {"quote": "solid waste"}


def test_prompt_of_an_outgoing_skill_carries_the_rule():
    import asyncio
    prompt = asyncio.run(SkillService.render_prompt("linkedin/prospect_note.md", {"name": "x", "headline": "y", "company": "z", "profile_text": "t", "fit": 1, "segment": "s", "market": "intl", "topic": ""}))
    assert "CONFIDENTIALITY" in prompt


def test_job_document_with_the_term_is_not_served(client, db, add_job):
    job = add_job(resume="Water and solid waste")
    res = client.get(f"/api/jobs/{job['id']}/document.pdf?kind=resume")
    assert res.status_code == 422
