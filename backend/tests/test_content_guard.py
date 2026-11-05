import re
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


TERMS = r"res[ií]duos? s[oó]lidos?|solid[ -]waste|aterros? sanit|landfill"
SKIP_DIRS = {".git", "node_modules", "output", "__pycache__", ".venv", "venv", "dist", "build", ".pytest_cache"}


def _versioned_hits() -> list:
    """Files that cite the terms, outside the guard's rules and the tests. With git: the tracked files. Without git (the
    test container has none): every file in the repo but generated folders, which is stricter, never looser."""
    excluded = ("config/automation.yml", "backend/tests/", "automation/tests/")
    try:
        out = subprocess.run(["git", "grep", "-lIiE", TERMS, "--", ".", ":!config/automation.yml", ":!backend/tests", ":!automation/tests"],
                             cwd=ROOT, capture_output=True, text=True)
        if out.returncode in (0, 1):
            return out.stdout.split()
    except FileNotFoundError:
        pass
    pattern, hits = re.compile(TERMS, re.I), []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        parts = path.relative_to(ROOT).parts
        hidden = any(x.startswith(".") and x != ".github" for x in parts[:-1])   # other tools' copies (.kilo/worktrees...)
        if not path.is_file() or hidden or SKIP_DIRS & set(parts) or rel.startswith(excluded):
            continue
        try:
            if pattern.search(path.read_text(encoding="utf-8")):
                hits.append(rel)
        except (UnicodeDecodeError, OSError):
            continue
    return hits


def test_no_versioned_text_cites_it():
    """Only the guard's own rules and these tests may contain the terms."""
    assert _versioned_hits() == []


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


def test_a_sentence_that_keeps_it_after_the_retry_is_dropped():
    cv = "\n".join(["# Paulo", "- Built CentralOps, a planning platform.", "- Modeled water and drainage tariffs.",
                    "- Led studies. Planned sanitary landfill sites.", "- Wrote 2,000 pgTAP tests."] + ["- Shipped a thing."] * 6)
    out = SkillService.generate_checked("jobs/resume.md", "prompt", lambda p: {"resume_markdown": cv})["resume_markdown"]
    assert content_guard.forbidden_in(out) == [] and "- Led studies." in out and "pgTAP" in out


def test_the_rule_names_the_subjects_only_when_the_prompt_brings_them():
    assert "landfill" not in content_guard.prompt_rule("A job about data platforms").lower()
    assert "landfill" in content_guard.prompt_rule("A job about landfill gas").lower()


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
