"""The answer bank reuses an answer given in other words or another language, never an instruction, and a question that is
not in Portuguese or English reaches the candidate translated (2026-11-19)."""
from app.services import answer_match as m
from app.services.automation_service import AutomationService


BANK = [
    {"id": 1, "question": "Which timezone are you currently located in?", "answer": "Florianópolis, UTC-3", "field_type": "text"},
    {"id": 2, "question": "Do you have a clean driving record?", "answer": "Yes", "field_type": "radio"},
    {"id": 3, "question": "Geburtsdatum (TT.MM.JJJJ)", "answer": "12.08.1987", "field_type": "text"},
    {"id": 4, "question": "Are you authorized to work in the US?", "answer": "No", "field_type": "radio"},
    {"id": 5, "question": "Please provide three professional references", "answer": "Arquivar vaga — não enviar candidatura",
     "field_type": "text"},
    {"id": 6, "question": "Years of experience (Python)", "answer": "8", "field_type": "text"},
]


def loose(monkeypatch, label, field_type="text"):
    monkeypatch.setattr(AutomationService, "answers_list", staticmethod(lambda: BANK))
    return AutomationService._loose_answer(label, field_type)


def test_the_agents_context_around_a_question_still_matches(monkeypatch):
    assert loose(monkeypatch, "Which timezone are you currently located in? (The form only offers US timezones: ET, CT, MT)") \
        == "Florianópolis, UTC-3"
    assert loose(monkeypatch, 'No campo "Which timezone are you currently located in?" o formulário só aceita UMA opção') \
        == "Florianópolis, UTC-3"
    assert loose(monkeypatch, "Qual é a sua data de nascimento? Campo do formulário: Geburtsdatum (TT.MM.JJJJ)") == "12.08.1987"


def test_same_words_in_another_order_match(monkeypatch):
    assert loose(monkeypatch, "Clean driving record *", "radio") == "Yes"


def test_a_different_country_skill_or_note_is_a_different_question(monkeypatch):
    assert loose(monkeypatch, "Are you authorized to work in the UK?") is None
    assert loose(monkeypatch, "Years of experience (Java)") is None
    assert loose(monkeypatch, "Years of experience") is None


def test_an_instruction_is_never_reused_nor_saved():
    assert loose.__name__  # keeps the helper referenced
    assert m.not_an_answer("Arquivar vaga — não enviar candidatura")
    assert m.not_an_answer("cancele esse")
    assert m.not_an_answer("me devolva traduzido, nao leio alemao")
    assert not m.not_an_answer("Yes") and not m.not_an_answer("PJ") and not m.not_an_answer("Florianópolis, UTC-3")


def test_instruction_answer_is_skipped(monkeypatch):
    assert loose(monkeypatch, "Please provide three professional references") is None


def test_portuguese_and_english_need_no_translation(monkeypatch):
    monkeypatch.setattr(m, "_ai", lambda prompt: (_ for _ in ()).throw(AssertionError("no AI call")))
    assert m.translation("Do you have 5 years of experience with SQL?") is None
    assert m.translation("Qual é o seu nível de inglês? Você tem experiência com Python?") is None


def test_german_question_is_translated_to_portuguese(monkeypatch):
    monkeypatch.setattr(m, "_ai", lambda prompt: {"lang": "de", "lang_name_pt": "alemão",
                                                  "pt": "Conhecimentos de alemão (escrita e fala)",
                                                  "en": "German skills (written and spoken)",
                                                  "options_pt": ["Nenhum", "Básico", "Fluente"]})
    tr = m.translation("Deutschkenntnisse (schriftlich & mündlich)", ["Keine", "Grundkenntnisse", "Fließend"])
    assert tr["pt"].startswith("Conhecimentos de alemão") and tr["lang_name"] == "alemão"
    assert tr["options_pt"] == ["Nenhum", "Básico", "Fluente"]


def test_spanish_is_translated_too(monkeypatch):
    monkeypatch.setattr(m, "_ai", lambda prompt: {"lang": "es", "lang_name_pt": "espanhol", "pt": "Você tem permissão de trabalho?",
                                                  "en": "Do you have a work permit?", "options_pt": []})
    assert m.translation("¿Tiene usted permiso de trabajo?")["lang"] == "es"


def test_ai_saying_english_means_no_translation(monkeypatch):
    monkeypatch.setattr(m, "_ai", lambda prompt: {"lang": "en", "pt": "x", "en": "x"})
    assert m.translation("Notice period") is None


def test_ai_match_reuses_an_answer_in_another_language_adapted_to_the_options(monkeypatch):
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return {"match": 0, "answer": "fließend"}
    monkeypatch.setattr(m, "_ai", fake)
    bank = [{"id": 9, "question": "What is your English level?", "answer": "Fluent", "field_type": "select"}]
    hit = m.ai_match("Englischkenntnisse", "select", ["Keine", "Gut", "Fließend"], bank, also=["English skills"])
    assert hit == {"answer": "Fließend", "question_id": 9, "saved_question": "What is your English level?"}
    assert "DIFFERENT question" in seen["prompt"]


def test_ai_match_refuses_an_answer_outside_the_options_or_an_instruction(monkeypatch):
    bank = [{"id": 9, "question": "What is your English level?", "answer": "Fluent", "field_type": "select"},
            {"id": 10, "question": "References", "answer": "cancele esse", "field_type": "text"}]
    monkeypatch.setattr(m, "_ai", lambda prompt: {"match": 0, "answer": "Native"})
    assert m.ai_match("Englischkenntnisse", "select", ["Keine", "Gut", "Fließend"], bank) is None
    monkeypatch.setattr(m, "_ai", lambda prompt: {"match": None, "answer": ""})
    assert m.ai_match("Englischkenntnisse", "select", [], bank) is None
    monkeypatch.setattr(m, "_ai", lambda prompt: {"match": 0, "answer": "arquivar vaga"})
    assert m.ai_match("Englischkenntnisse", "text", [], bank) is None


def test_saving_an_instruction_is_skipped():
    class Cur:
        calls = 0

        def execute(self, *a):
            Cur.calls += 1
    AutomationService._upsert_answer(Cur(), "Please provide references", "Arquivar vaga — não enviar candidatura")
    AutomationService._upsert_answer(Cur(), "Clean driving record", "Yes")
    assert Cur.calls == 1
