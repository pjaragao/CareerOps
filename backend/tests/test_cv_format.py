"""The form of the resume for an ATS: the contact line, plain characters, and what the reviewer reports without any AI.
No database and no pytest fixtures: plain asserts, so they also run where only the app code is present."""
from app.services import cv_format as cf
from app.services import cv_review_service as cr

PERSONAL = {"email": "me@example.com", "phone": "+55 48 91234-5678", "linkedin": "linkedin.com/in/me", "github": "github.com/me"}
LINK = "https://portfolio.example/?token=pjr-acme-1-abc"
RAW = ("# ME\n\n**Senior AI Engineer | Agents**\n\nFlorianopolis, Brazil (UTC−3) | Open to remote\n"
       "me@example.com | +55 00 00000-0000 | linkedin.com/in/me | github.com/me | [Portfolio](https://old/?token=x)\n\n"
       "## SKILLS\n• RAG → evals ≥ 3\n\n## PROFESSIONAL EXPERIENCE\n- Jan 2020 – Present\n")


def test_the_contact_line_is_rebuilt_from_the_profile():
    out = cf.normalize(RAW, LINK, personal=PERSONAL)
    line = next(l for l in out.split("\n") if "@" in l)
    assert line == ("me@example.com | +55 48 91234-5678 | [linkedin.com/in/me](https://www.linkedin.com/in/me) | "
                    "[github.com/me](https://github.com/me) | [Portfolio: pjaragao-portfolio.vercel.app](" + LINK + ")")
    assert "00000" not in out


def test_atS_unsafe_characters_become_plain():
    out = cf.normalize(RAW, LINK, personal=PERSONAL)
    assert "UTC-3" in out and "- RAG -> evals >= 3" in out and "Jan 2020 - Present" in out
    assert not cr.UNSAFE_CHARS.search(out)


def test_normalizing_twice_changes_nothing_and_the_location_stays():
    once = cf.normalize(RAW, LINK, personal=PERSONAL)
    assert cf.normalize(once, LINK, personal=PERSONAL) == once
    loc = "Florianopolis/SC | me@example.com | (00) 00000-0000 | linkedin.com/in/me\n## RESUMO PROFISSIONAL\nx"
    out = cf.normalize(loc, LINK, personal=PERSONAL)
    assert out.split("\n")[0].startswith("Florianopolis/SC | me@example.com | +55 48 91234-5678")
    assert "[Portfólio: pjaragao-portfolio.vercel.app]" in out   # Portuguese resume, Portuguese label


def test_the_reviewer_reports_what_the_screenshot_showed():
    bad = ("# ME\n\n**Role**\n\nme@example.com | +55 00 00000-0000 | linkedin.com/in/me | github.com/me | [Portfolio](" + LINK + ")\n\n"
           "## PROFESSIONAL SUMMARY\nx\n\n## LANGUAGES & GLOBAL MOBILITY\nEnglish\n\n## PROFESSIONAL EXPERIENCE\n- Jan 2020 – Present\n- 2015 - 2019\n")
    problems = [i["problem"] for i in cr.ats_issues(bad, None, expect_portfolio=True)]
    text = " | ".join(problems)
    assert "o telefone é um modelo" in text
    assert "LinkedIn é só texto" in text and "GitHub é só texto" in text
    assert "caracteres que o ATS lê mal" in text
    assert "títulos de seção fora do padrão" in text
    assert "estilos de data misturados" in text
    assert [i["severity"] for i in cr.ats_issues(bad, None, True) if "telefone" in i["problem"]] == ["critical"]


def test_a_normalized_resume_passes_the_ats_form_checks():
    good = cf.normalize(RAW.replace("## SKILLS", "## SKILLS").replace("Jan 2020 – Present", "Jan 2020 - Present"), LINK, personal=PERSONAL)
    assert cr.ats_issues(good, None, expect_portfolio=True) == []


def test_the_pdf_has_clickable_links_and_a_title():
    pdf = cr.render_pdf(cf.normalize(RAW, LINK, personal=PERSONAL))
    if pdf is None:   # no PDF service where this runs
        return
    got = cr.pdf_text(pdf)
    text, uris = got
    joined = " ".join(uris)
    assert "linkedin.com/in/me" in joined and "github.com/me" in joined and "portfolio.example" in joined
    assert "+55 48 91234-5678" in text and "00000" not in text
    import io
    import pypdf
    assert pypdf.PdfReader(io.BytesIO(pdf)).metadata.get("/Title") == "Me - Resume"
    assert [i for i in cr.ats_issues(cf.normalize(RAW, LINK, personal=PERSONAL), pdf, True) if i["severity"] == "critical"] == []
