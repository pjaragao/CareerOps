"""Deterministic CV fixes (2026-11-16): what the reviewer kept rejecting, fixed by rule before every round."""
from app.services.cv_autofix import autofix, impersonal_pt, numeric_months, year_ranges

BASE = """# Paulo
## PROFESSIONAL EXPERIENCE
**Finance Director (CFO)** | Feb 2023 - Jan 2026
**Senior Engineer** | Aug 2011 - Jan 2023
"""


def test_numeric_months_become_names():
    assert numeric_months("Role | 03/2019 - 12/2021", "en") == "Role | Mar 2019 - Dec 2021"
    assert numeric_months("Cargo | 03/2019", "pt") == "Cargo | mar 2019"


def test_year_ranges_take_the_months_of_the_base_resume():
    cv = "**CFO** | 2023 - 2026\n**Senior Engineer** | 2011 - 2023\n**Data** | Feb 2026 - Present"
    out = year_ranges(cv, BASE)
    assert "Feb 2023 - Jan 2026" in out and "Aug 2011 - Jan 2023" in out
    assert year_ranges("**X** | 2001 - 2003\nFeb 2026 - Present", BASE).startswith("**X** | 2001 - 2003")   # unknown: kept


def test_first_person_portuguese_bullets():
    out = impersonal_pt("- Opero 11 sistemas em produção\n- Desenvolvo modelos\n- Sistema próprio")
    assert out == "- Opera 11 sistemas em produção\n- Desenvolve modelos\n- Sistema próprio"


def test_autofix_runs_everything_and_fits(monkeypatch):
    cv = "# Paulo\npaulo@x.com | +55 48 90000-0000\n## Experiência Profissional\n- Lidero a equipe | 03/2019 - 12/2021\n"
    calls = []
    out = autofix(cv, base=BASE, personal={"email": "paulo@x.com", "phone": "+55 48 90000-0000"}, fit=lambda md: calls.append(1) or md + "<!--fit-->")
    assert "- Lidera a equipe | mar 2019 - dez 2021" in out and out.endswith("<!--fit-->") and calls


def test_a_cv_still_rejected_after_every_round_falls_back_to_a_known_good_one(db, add_job, monkeypatch):
    import asyncio
    from app.api import actions
    from app.services import cv_review_service as crs
    from app.services.cv_review_service import CvReviewService
    from app.services.site_service import TextCache, text_key
    job = add_job(resume="# Bad CV\n- stuff", cover="Carta", title="Senior AI Engineer")
    TextCache.put(text_key("cv", "ai_engineering", "en"), "cv", "# Approved family CV\n- good")
    monkeypatch.setattr(crs, "pdf_pages", lambda md, *a, **k: None)

    async def review(job_id, asked=""):
        resume = crs._job(job_id).get("resume_markdown") or ""
        ok = "Approved family CV" in resume
        return {"approved": ok, "issues": [] if ok else [{"doc": "resume", "severity": "major", "problem": "x", "fix": "y"}],
                "pages": 2, "summary": "", "resume_instructions": "" if ok else "- y", "cover_instructions": ""}

    async def regen(job_id, options):
        return {"content": ""}
    monkeypatch.setattr(CvReviewService, "review", staticmethod(review))
    monkeypatch.setattr(actions, "generate_resume", regen)
    monkeypatch.setattr(actions, "generate_cover_letter", regen)
    verdict = asyncio.run(CvReviewService.run(job["id"], rounds=1))
    assert verdict["approved"] and verdict["fallback"] == "archetype"
    assert "Approved family CV" in crs._job(job["id"])["resume_markdown"]



def test_a_month_range_is_never_doubled_and_dashes_are_plain():
    cv = "# Paulo\n## Experience\n**Data & AI Engineer** | Feb 2026 - Present\n**Old** | Feb Feb 2026 – Present\n[Portfolio: x](https://x)"
    out = autofix(cv, base="**Data** | Feb 2026 – Present")
    assert "Feb Feb" not in out and "–" not in out and out.count("Feb 2026 - Present") == 2
