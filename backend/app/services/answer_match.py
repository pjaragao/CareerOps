"""The answer bank, less literal (2026-11-19).

The apply agent rarely asks a question with the form's exact words: it adds context ("Which timezone are you in? (The form
only offers US timezones…)"), quotes the field ("Campo do formulário: Deutschkenntnisse…"), or the same question comes
in another language. Matching only the exact text asked you the timezone four times. Here:
- `keys_of`: the exact key, the key without the agent's context, and the field labels the agent quoted;
- `same_words`: the same content words, whatever the order, punctuation or filler ("please", "select all that apply");
- `ai_match`: before a question goes to you, the AI looks at the closest saved answers (in any language) and reuses one
  only when it answers the same question, adapting it to the form's options and format;
- `not_an_answer`: "cancele", "arquivar vaga", "me devolva traduzido" are instructions, never saved or reused;
- `translation`: a question that is not in Portuguese or English reaches you translated into Portuguese.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

STOP = {
    # en
    "the", "a", "an", "do", "does", "did", "you", "your", "are", "is", "of", "in", "to", "for", "and", "or", "have", "has",
    "what", "how", "this", "with", "be", "will", "can", "on", "at", "by", "as", "if", "it", "any", "we", "us", "our", "i",
    "my", "me", "there", "that", "which", "would", "should", "could", "from", "into", "currently", "please", "kindly",
    "select", "all", "apply", "choose", "one", "option", "options", "enter", "provide", "indicate", "specify", "below",
    "following", "answer", "question", "required", "optional", "field",
    # pt
    "o", "os", "as", "de", "da", "das", "do", "dos", "voce", "e", "em", "no", "na", "nos", "nas", "para", "por", "qual",
    "quais", "que", "um", "uma", "seu", "sua", "seus", "suas", "se", "ao", "com", "atualmente", "favor", "selecione",
    "informe", "campo", "pergunta", "obrigatorio", "obrigatoria",
}
# an "answer" that is really an instruction to the agent about this one form
NOT_AN_ANSWER = re.compile(
    r"\b(cancel[ea]?|cancela[rd]?|arquiv(e|ar|a)|n[aã]o envi(e|ar)|desist(a|ir)|pul(e|ar) (a|essa) vaga|"
    r"me devolv\w*|traduz\w*|n[aã]o (leio|entendo|sei ler)|em portugu[eê]s|do not (submit|send|apply)|archive)\b", re.I)
QUOTED = re.compile(r"(?:campo(?: do formul[aá]rio)?|form field|field|feld)\s*[:\"“„«']\s*[\"“„«']?([^\"”“«»\n;]{3,160}?)[\"”“»]?\.?\s*(?:[;\n]|$)"
                    r"|[\"“„«]([^\"”“«»\n]{3,160})[\"”“»]", re.I)
# the agent's explanation: a parenthesis, bracket or dash tail of 4+ words ("(The form only offers US timezones…)"). A short
# one is part of the question ("Years of experience (Python)", "Salary - USD") and stays.
CONTEXT = re.compile(r"\([^)]*\)|\s\([^)]*$|\[[^\]]*\]|\s[—–-]\s.*$", re.I)
FIELD_NOTE = re.compile(r"\b(campo do formul[aá]rio|form field)\s*:.*$", re.I)


def norm(text: str) -> str:
    plain = unicodedata.normalize("NFKD", (text or "").lower()).encode("ascii", "ignore").decode()
    plain = plain.split(" › ")[-1]
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", plain).split())[:300]


def core(text: str) -> str:
    """The question without what the agent added around it: parentheses, a dash and an explanation, 'Campo do formulário: …'."""
    t = (text or "").strip()
    first = FIELD_NOTE.sub(" ", re.split(r"(?<=\?)\s", t, maxsplit=1)[0])   # the first question, when the agent explains after it
    long_note = lambda m: " " if len(re.findall(r"\w+", m.group(0))) >= 4 else m.group(0)
    return CONTEXT.sub(long_note, first).strip(" *:-—")


def keys_of(text: str) -> List[str]:
    out: List[str] = []
    quoted = [(a or b) for a, b in QUOTED.findall(text or "")]
    for k in [norm(text), norm(core(text))] + [norm(q) for q in quoted] + [norm(re.split(r"\s\(", q)[0]) for q in quoted]:
        if k and len(k) >= 3 and k not in out:
            out.append(k)
    return out


def _stem(w: str) -> str:
    return w[:-1] if len(w) > 4 and w.endswith("s") else w


def content_words(key: str) -> frozenset:
    return frozenset(_stem(w) for w in (key or "").split() if w not in STOP and len(w) > 1)


def same_words(a: str, b: str) -> bool:
    """The same content words: "Do you have a clean driving record?" = "Clean driving record *". A different number, country
    or skill is a different word, so it never matches (US vs UK, 5 vs 3 years, SQL vs Python)."""
    wa, wb = content_words(a), content_words(b)
    return len(wa) >= 1 and wa == wb


def similarity(a: str, b: str) -> float:
    wa, wb = content_words(a), content_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# ── personal facts asked in any language (2026-11-22) ──
# The date of birth was saved as "Geburtsdatum (TT.MM.JJJJ)" and "Qual é a sua data de nascimento (Geburtstag)?…"; "Date of
# Birth", "Data di nascita" and "Day and month of birth (DDMM)" share no word with them, the AI match only sees the dozen
# closest or most recent answers, so you were asked again and again. Race likewise ("Como você descreveria a si mesmo/a?").
# A question about one of these facts reuses the newest answer about the same fact, whatever its words or language.
TOPICS = {
    "birth_date": (re.compile(r"birth|nascimento|nascita|geburt|nacimiento|naissance|geboorte|urodzeni|f[oö]delse|\bddmm\b|\bdob\b", re.I),
                   re.compile(r"(country|place|city|town|state|pa[ií]s|local|cidade|estado|land|ort|luogo|citt[aà]|lieu|pays|lugar|ciudad)"
                              r"\s+(of\s+|de\s+|di\s+|du\s+)?(birth|nascimento|nascita|naissance|nacimiento)|geburts(ort|land|stadt)|"
                              r"nationalit|cidadania|citizenship|naturalidade", re.I)),
    "race": (re.compile(r"\brace\b|\bra[çc]a\b|\bracial\b|descreveria a si|cor da pele|\bcor\s*/\s*ra[çc]a", re.I),
             re.compile(r"hispanic or latino\?|are you hispanic|[ée] hispan|ethnicity\s*[:?]?\s*$", re.I)),
    "german_level": (re.compile(r"\b(german|deutsch\w*|alem[aã]o|tedesco|allemand|alem[aá]n)\b", re.I),
                     re.compile(r"\b(live|living|based|located|reside|work permit|citizen|right to work|visa|moram?|resid)\b", re.I)),
}


def topic(text: str) -> Optional[str]:
    """The personal fact this question asks for (date of birth, race, German level), or None. Read on the question without
    the agent's explanation around it; a place or country of birth is another fact."""
    t = core(text) or (text or "")
    for name, (asks, not_this) in TOPICS.items():
        if asks.search(t) and not not_this.search(t):
            return name
    return None


def not_an_answer(answer: str) -> bool:
    return bool(NOT_AN_ANSWER.search(answer or ""))


# ── languages ──
PT_EN = {"voce", "nao", "qual", "quais", "seu", "sua", "para", "com", "uma", "que", "como", "esta", "sim", "anos", "tem",
         "possui", "the", "you", "your", "do", "are", "have", "what", "which", "how", "with", "for", "is", "of", "and",
         "years", "experience", "please", "will", "can", "did", "does"}
OTHER = {"der", "die", "das", "und", "ist", "sie", "ihre", "ihr", "nicht", "mit", "fur", "zum", "zur", "bis", "haben",
         "konnen", "welche", "wie", "le", "la", "les", "des", "et", "vous", "votre", "est", "pour", "avec", "quel", "quelle",
         "el", "los", "las", "usted", "su", "cual", "tiene", "del", "es", "y", "il", "di", "che", "het", "een",
         "van", "uw", "je", "jij", "czy", "jest", "nie", "lub", "jak", "och", "att", "ar", "har", "og", "er"}
FOREIGN_CHARS = re.compile(r"[äöüßÄÖÜąęłńśźżŁŚŻåøæñ¿¡]")


def plainly_pt_or_en(text: str) -> bool:
    """Cheap first look: Portuguese/English words and none of another language's, so no AI call is needed."""
    words = norm(text).split()
    pe = sum(w in PT_EN for w in words)
    other = sum(w in OTHER for w in words) + 2 * len(FOREIGN_CHARS.findall(text or ""))
    return pe >= 2 and other == 0


def _ai(prompt: str) -> dict:
    from app.services.ai_service import AIService
    res = AIService.get_provider("default").generate_json(prompt, temperature=0.1)
    return res if isinstance(res, dict) and not res.get("error") else {}


def translation(question: str, options: Optional[list] = None) -> Optional[dict]:
    """{lang, pt, en, options_pt} for a question that is not in Portuguese or English; None when it is (or on failure)."""
    opts = [str(o) for o in (options or [])][:30]
    if plainly_pt_or_en(question + " " + " ".join(opts)):
        return None
    try:
        res = _ai(
            "A job-application form question. Say its language and translate it.\n"
            f"Question: {json.dumps(question, ensure_ascii=False)}\nOptions: {json.dumps(opts, ensure_ascii=False)}\n"
            'Return JSON: {"lang": "<ISO 639-1 code of the main language of the question>", '
            '"lang_name_pt": "<that language\'s name in Portuguese>", "pt": "<the question in Brazilian Portuguese>", '
            '"en": "<the question in English>", "options_pt": ["<each option in Brazilian Portuguese, same order>"]}')
    except Exception as e:
        log.warning("question translation failed: %s", e)
        return None
    lang = str(res.get("lang") or "").lower()[:5]
    if not res.get("pt") or lang.startswith(("pt", "en")):
        return None
    return {"lang": lang, "lang_name": str(res.get("lang_name_pt") or lang), "pt": str(res["pt"])[:1000],
            "en": str(res.get("en") or "")[:1000], "options_pt": [str(o)[:200] for o in (res.get("options_pt") or [])][:30]}


def ai_match(question: str, field_type: str, options: Optional[list], bank: List[dict],
             also: Optional[List[str]] = None) -> Optional[dict]:
    """A saved answer the AI judges to answer the SAME question (any wording or language), adapted to this form's options
    and format: {answer, question_id, saved_question}. Only the closest dozen go to the AI."""
    texts = [question] + [t for t in (also or []) if t]
    scored = []
    for a in bank:
        if not_an_answer(a.get("answer") or ""):
            continue
        best = max(similarity(k, norm(a["question"])) for t in texts for k in keys_of(t))
        scored.append((best, a))
    scored.sort(key=lambda x: -x[0])
    # cross-language questions share no words: the dozen most recent go along with the closest ones
    near = [a for s, a in scored[:12] if s > 0.15]
    recent = [a for a in bank if a not in near and not not_an_answer(a.get("answer") or "")][:max(0, 12 - len(near))]
    cands = (near + recent)[:20]
    if not cands:
        return None
    listing = [{"i": i, "question": c["question"][:300], "answer": c["answer"][:400]} for i, c in enumerate(cands)]
    try:
        res = _ai(
            "You fill a job application with the candidate's own saved answers. Decide whether one saved answer answers the "
            "NEW question.\n"
            f"New question: {json.dumps(question, ensure_ascii=False)}\n"
            + (f"Also phrased as: {json.dumps(also, ensure_ascii=False)}\n" if also else "")
            + f"Field type: {field_type}\nOptions on the form: {json.dumps([str(o) for o in (options or [])][:30], ensure_ascii=False)}\n"
            f"Saved answers: {json.dumps(listing, ensure_ascii=False)}\n"
            "Rules: match only when the saved question asks for the SAME fact (wording and language may differ). A different "
            "country, city, currency, period, skill, tool, number of years or company is a DIFFERENT question: no match. "
            "Do not guess or combine. When the form has options, give the option that the saved answer means, copied "
            "exactly; when no option fits, no match. Keep the saved meaning but fit the form's format (date pattern, units, "
            "Yes/No, the form's language).\n"
            'Return JSON: {"match": <i or null>, "answer": "<answer for this form, or empty>"}')
    except Exception as e:
        log.warning("answer match failed: %s", e)
        return None
    i, ans = res.get("match"), str(res.get("answer") or "").strip()
    if not isinstance(i, int) or not (0 <= i < len(cands)) or not ans or not_an_answer(ans):
        return None
    opts = [str(o) for o in (options or [])]
    if opts and ans not in opts:
        low = {o.lower(): o for o in opts}
        if ans.lower() not in low:
            return None
        ans = low[ans.lower()]
    return {"answer": ans[:2000], "question_id": cands[i].get("id"), "saved_question": cands[i]["question"]}
