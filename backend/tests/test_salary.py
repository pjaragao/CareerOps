import asyncio
from datetime import datetime

import pytest

from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot

FACTS = Copilot._facts()


def answer(label, type_="number", location="Remote", lang="English"):
    return Copilot._salary_answer({"label": label, "type": type_}, FACTS, {"location": location}, lang)


def test_years_count_from_2008():
    years = FACTS["years_of_experience"]
    expected = datetime.now().year - 2008
    assert years["total_professional"] == expected
    assert years["engineering_sanitation_water_infrastructure"] == expected
    assert years["python"] == 2   # a skill keeps its own number


@pytest.mark.parametrize("label,expected", [
    ("Monthly salary expectation in USD", "7000"),
    ("Expected annual salary (USD)", "84000"),
    ("Annual compensation in EUR", "74400"),
    ("Pretensão salarial mensal em EUR", "6200"),
    ("Pretensão salarial mensal em R$", "30000"),
    ("Yearly salary $", "84000"),
])
def test_number_fields_get_the_floor_in_that_currency_and_period(label, expected):
    assert answer(label) == expected


@pytest.mark.parametrize("label", ["Expected salary in GBP", "Salary (CAD)", "Hourly rate expectation in USD salary", "Annual salary in BRL"])
def test_what_has_no_floor_is_left_for_you(label):
    assert answer(label) is None


def test_a_number_with_no_currency_needs_the_location():
    assert answer("Expected salary") is None
    assert answer("Expected salary", location="Lisbon, Portugal") == "74400"
    assert answer("Expected salary", location="Austin, United States") == "84000"


def test_a_bare_number_abroad_is_yearly_never_the_monthly_figure():
    assert answer("Salary in USD") == "84000"


def test_text_fields_say_currency_and_period():
    assert answer("Salary expectation", "text") == "from USD 7,000/month (USD 84,000/year)"
    assert answer("Pretensão salarial em EUR", "text", lang="Portuguese") == "a partir de EUR 6.200/mês (EUR 74.400/ano)"
    assert answer("Pretensão salarial em BRL", "text", lang="Portuguese") == "acima de BRL 30.000/mês (PJ)"


def test_a_list_of_ranges_is_left_for_you():
    assert answer("Salary range", "select") is None


def test_salary_questions_never_reach_the_ai(db, monkeypatch):
    seen = {}

    async def fake_skill(path, context, model_key="ai_model_writing"):
        seen["fields"] = context["fields"]
        return {"answers": {"other": "yes"}, "salary_suggestions": {"gbp": {"value": "9999"}}}

    monkeypatch.setattr("app.services.linkedin_copilot_service._skill", fake_skill)
    monkeypatch.setattr("app.services.profile_service.ProfileService.get_resume_base", staticmethod(lambda lang: "cv"))
    fields = [{"key": "usd", "type": "number", "label": "Monthly salary in USD", "options": []},
              {"key": "gbp", "type": "number", "label": "Salary in GBP", "options": []},
              {"key": "other", "type": "text", "label": "Are you available?", "options": []}]
    result = asyncio.run(Copilot.easy_apply_answers({"location": "Remote"}, fields))
    assert [f["key"] for f in seen["fields"]] == ["other"]
    assert result["answers"]["usd"] == "7000"
    assert "gbp" not in result["answers"] and "gbp" in result["needs_user"]
    assert result["suggestions"] == {}   # an AI estimate is ignored even if it comes


def test_a_saved_answer_is_used_before_anything_else(db, monkeypatch):
    from app.services.automation_service import AutomationService as Auto, _rows
    action = Auto.create_action("connect", "k", "t", "u", {}, status="needs_user")
    Auto.answer(action["id"], [{"question": "Salary in GBP", "answer": "5000", "field_type": "number"}])
    assert _rows("SELECT question_norm FROM public.automation_answers")[0]["question_norm"] == "salary in gbp"
    result = asyncio.run(Copilot.easy_apply_answers({"location": "x"}, [{"key": "gbp", "type": "number", "label": "Salary in GBP *", "options": []}]))
    assert result["answers"]["gbp"] == "5000"
