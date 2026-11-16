"""The deterministic form mapper (token plan, phase 2): label -> fact with no AI, and None when in doubt."""
from datetime import date

import pytest

from app.services.form_mapper import FormMapper, map_fields, pick, yes_no

FACTS = {
    "contact": {"name": "Paulo José Aragão Júnior", "first_name": "Paulo", "last_name": "José Aragão Júnior",
                "email": "p@example.com", "phone": "+55 48 90000-0000", "city": "Florianópolis, Santa Catarina, Brazil",
                "linkedin": "linkedin.com/in/someone", "github": "github.com/someone", "zip_code": "88000-000"},
    "work_authorization": {"authorized_to_work": ["Brazil"], "needs_sponsorship_elsewhere": True},
    "languages": {"Portuguese": "native", "English": "fluent (C1)", "Spanish": "intermediate (B1)"},
    "self_identification": {"gender": "Male", "veteran": "No (not a protected veteran)", "disability": "No, I do not have a disability"},
    "standing_answers": {"race_ethnicity": "Hispanic or Latino"},
    "years_of_experience": {"python": 2, "sql": 5, "total_professional": 18},
}
M = FormMapper(FACTS, {}, "English", today=date(2026, 11, 16))


def ans(label, kind="text", options=None):
    return M.answer({"key": "k", "label": label, "type": kind, "options": options or []})


@pytest.mark.parametrize("label,expected", [
    ("First Name", "Paulo"), ("Last name*", "José Aragão Júnior"), ("Full name", "Paulo José Aragão Júnior"),
    ("Email address", "p@example.com"), ("Mobile phone", "+55 48 90000-0000"), ("LinkedIn Profile", "https://www.linkedin.com/in/someone"),
    ("GitHub URL", "https://github.com/someone"), ("Postal code", "88000-000"), ("Bairro", "Centro"),
    ("How did you hear about this job?", "LinkedIn"), ("Earliest start date", "30/11/2026"),
])
def test_text_fields(label, expected):
    assert ans(label) == expected


def test_yes_no_rules_follow_the_country_named():
    yn = ["Yes", "No"]
    assert ans("Are you legally authorized to work in the United States?", "select", yn) == "No"
    assert ans("Are you authorized to work in Brazil?", "radio", yn) == "Yes"
    assert ans("Will you now or in the future require visa sponsorship?", "select", yn) == "Yes"
    assert ans("Are you willing to relocate?", "select", yn) == "Yes"
    assert ans("Are you at least 18 years of age?", "radio", yn) == "Yes"
    assert ans("Have you ever been convicted of a criminal offence?", "radio", yn) == "No"
    assert ans("Are you only looking for a fully remote job?", "select", yn) == "No"
    assert ans("I agree to the privacy policy", "checkbox") == "true"


def test_long_options_and_demographics():
    assert ans("Will you require sponsorship?", "select", ["Yes, I will require sponsorship", "No, I will not"]) == "Yes, I will require sponsorship"
    assert ans("Gender", "select", ["Female", "Male", "Decline"]) == "Male"
    assert ans("Race / Ethnicity", "select", ["White", "Hispanic or Latino", "Asian"]) == "Hispanic or Latino"
    assert ans("Are you Hispanic or Latino?", "select", ["Yes", "No", "Decline"]) == "Yes"
    assert ans("Veteran status", "select", ["I am a protected veteran", "I am not a protected veteran"]) == "I am not a protected veteran"


def test_country_not_listed_is_other():
    assert ans("Country of residence", "select", ["Germany", "Austria", "Other"]) == "Other"
    assert ans("Country", "select", ["Brazil", "Spain"]) == "Brazil"


def test_languages_years_and_education():
    assert ans("English proficiency", "select", ["Basic", "Intermediate", "Fluent", "Native"]) == "Fluent"
    assert ans("Years of experience with Python", "number") == "2"
    assert ans("Highest level of education", "select", ["High school", "Bachelor's Degree", "Master's"]) == "Bachelor's Degree"


def test_doubtful_fields_are_left_to_the_ai():
    assert ans("Why do you want to work here?", "textarea") is None
    assert ans("Are you authorized to work?", "select", ["Yes", "No"]) is None   # no country named
    assert ans("Years of experience with Kubernetes", "number") is None
    assert ans("Reason for leaving", "text") is None
    assert ans("Gender", "select", ["Option A", "Option B"]) is None   # no option fits: never a guess


def test_map_fields_skips_filled_ones():
    out = map_fields([{"key": "a", "label": "Email", "type": "text", "current": "x@y.z"},
                      {"key": "b", "label": "City", "type": "text"}], FACTS)
    assert out == {"b": "Florianópolis"}


def test_pick_and_yes_no_helpers():
    assert pick(["Brasil", "Portugal"], ["Brazil", "Brasil"]) == "Brasil"
    assert yes_no(["Sim", "Não"], False) == "Não"


def test_site_memory_and_recipes(db):
    from app.services.site_service import SiteService
    assert SiteService.human_block("https://jobs.example.com/1") is None
    assert SiteService.record_block("https://jobs.example.com/1", "Stopped at a Cloudflare Turnstile challenge") == "captcha"
    assert SiteService.human_block("https://jobs.example.com/2") is None          # once is not enough
    SiteService.record_block("jobs.example.com", "hCaptcha image challenge")
    assert SiteService.human_block("https://jobs.example.com/3") == "captcha"     # twice, never passed: straight to you
    SiteService.save_recipe("jobs.example.com", "generic", ["Next"], ["Submit application"])
    assert SiteService.human_block("https://jobs.example.com/4") is None          # a success there: tried again
    assert SiteService.recipe("jobs.example.com")["submit"] == ["submit application"]
    assert SiteService.record_block("x.com", "the form needs a phone number") is None
