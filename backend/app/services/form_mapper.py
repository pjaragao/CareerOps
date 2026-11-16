"""Deterministic answers for application-form fields: label -> fact, with no AI.

The facts are config/easy_apply.yml overlaid with the live profile (LinkedInCopilotService._facts), including the
candidate's standing_answers. Only what is not mapped here goes to the AI, in one small call (token plan, phase 2).
A field is answered only when the rule is unambiguous; anything doubtful returns None and is left to the AI or to you.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional

YES = ("yes", "sim", "si", "sí", "ja", "oui", "true")
NO = ("no", "não", "nao", "nein", "non", "false")
START_IN_DAYS = 14          # standing answer: available start date = today + 14 days
SCHOOL = "Universidade Federal de Santa Catarina"
FIELD_OF_STUDY = "Sanitary and Environmental Engineering"
GRADUATION_YEAR = "2011"
DEGREE = "Bachelor's Degree"


def norm(text: Any) -> str:
    plain = unicodedata.normalize("NFKD", str(text or ""))
    plain = "".join(c for c in plain if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[*:?()\[\]]", " ", plain)).strip()


def pick(options: List[str], wanted: Iterable[str]) -> Optional[str]:
    """The option that matches one of the wanted values: exact, then starts-with, then contains (in that order)."""
    opts = [(o, norm(o)) for o in options or [] if str(o).strip()]
    wants = [norm(w) for w in wanted if str(w or "").strip()]
    for test in (lambda o, w: o == w, lambda o, w: o.startswith(w) or w.startswith(o) and len(o) > 2,
                 lambda o, w: w in o or (len(o) > 3 and o in w)):
        for w in wants:
            for raw, o in opts:
                if o and test(o, w):
                    return raw
    return None


def yes_no(options: List[str], yes: bool) -> Optional[str]:
    words = YES if yes else NO
    hit = pick(options, words)
    if hit:
        return hit
    # long options: "Yes, I am authorized…", "No, I will require sponsorship"
    for o in options or []:
        first = norm(o).split(" ")[0].strip(",.")
        if first in words:
            return o
    return None


def _years(facts: dict, label: str) -> Optional[int]:
    years = facts.get("years_of_experience") or {}
    table = [
        (r"python", "python"), (r"\bsql\b", "sql"), (r"power ?bi|business intelligence|\bbi\b", "power_bi_bi"),
        (r"excel|spreadsheet", "excel"), (r"typescript|javascript|react|web dev", "web_development_typescript"),
        (r"\b(ai|llm|genai|generative|machine learning|ml)\b|artificial intelligence|intelig[eê]ncia artificial", "ai_llm_applications"),
        (r"statistic|forecast", "statistics_forecasting"), (r"financial model|feasibility|dcf|valuation", "financial_modeling_feasibility_dcf"),
        (r"fp&?a|budget|corporate finance|controlling", "corporate_finance_fpa_budgeting"),
        (r"project management|gest[aã]o de projetos|project manager", "project_management"),
        (r"people management|managing (a )?team|lideran|leadership", "people_management"),
        (r"proposal|pricing|bid", "proposals_and_pricing"), (r"environmental|licens", "environmental_management_licensing"),
        (r"water|wastewater|sanitation|saneamento|infrastructure", "engineering_sanitation_water_infrastructure"),
    ]
    low = norm(label)
    for rx, key in table:
        if re.search(rx, low) and years.get(key) is not None:
            return int(years[key])
    if re.search(r"\b(total|overall|professional|work) experience\b|years of experience$|anos de experi", low) and years.get("total_professional"):
        return int(years["total_professional"])
    return None


def _country_rule(label: str) -> Optional[str]:
    """The country named in an authorization / sponsorship question."""
    low = norm(label)
    if re.search(r"\bbra[sz]il\b", low):
        return "brazil"
    if re.search(r"united states|\bus\b|\busa\b|u\.s\.|\buk\b|united kingdom|europe|\beu\b|canada|spain|germany|portugal|"
                 r"france|netherlands|ireland|italy|switzerland|australia|country (where|in which)|this country|the country", low):
        return "abroad"
    return None


class FormMapper:
    """answer(field, facts, job, lang) -> str | None. field = {key, type, label, options, current}."""

    def __init__(self, facts: dict, job: Optional[dict] = None, lang: str = "English", today: Optional[date] = None):
        self.facts = facts or {}
        self.job = job or {}
        self.lang = lang
        self.today = today or date.today()
        c = self.facts.get("contact") or {}
        self.contact = c
        self.stand = self.facts.get("standing_answers") or {}
        self.ident = self.facts.get("self_identification") or {}
        self.rules: List[tuple] = self._rules()

    # ── value helpers ──
    def _date_start(self) -> str:
        return (self.today + timedelta(days=START_IN_DAYS)).strftime("%d/%m/%Y")

    def _url(self, value: str) -> str:
        v = (value or "").strip()
        return v if not v or v.startswith("http") else f"https://www.{v}" if v.startswith("linkedin") else f"https://{v}"

    def _lang_level(self, name: str) -> List[str]:
        level = str((self.facts.get("languages") or {}).get(name) or "").lower()
        if "native" in level:
            return ["Native", "Native or bilingual", "Nativo", "Fluent", "C2"]
        if "fluent" in level or "c1" in level:
            return ["Fluent", "Full professional proficiency", "Advanced", "C1", "Fluente", "Avançado", "Proficient"]
        if "intermediate" in level or "b1" in level:
            return ["Intermediate", "B1", "Intermediário", "Conversational", "Limited working proficiency"]
        return ["None", "No knowledge", "Beginner", "Basic", "A1", "Nenhum", "Básico", "Elementary"]

    # ── the rules: (regex on the normalized label, value function returning a list of candidates / a string / None) ──
    def _rules(self) -> List[tuple]:
        c, s, ident = self.contact, self.stand, self.ident
        auth = self.facts.get("work_authorization") or {}

        def const(*vals):
            return lambda f: list(vals)

        def yes(f):
            return True

        def no(f):
            return False

        def authorized(f):
            where = _country_rule(f.get("label"))
            return True if where == "brazil" else (False if where == "abroad" else None)

        def sponsorship(f):
            where = _country_rule(f.get("label"))
            return False if where == "brazil" else (True if auth.get("needs_sponsorship_elsewhere") else None)

        def years(f):
            n = _years(self.facts, f.get("label"))
            return None if n is None else [str(n)]

        def language(f):
            low = norm(f.get("label"))
            for name, rx in (("English", r"english|ingl[eê]s"), ("Spanish", r"spanish|espanhol|espanol"),
                             ("Portuguese", r"portuguese|portugu[eê]s")):
                if re.search(rx, low):
                    return self._lang_level(name)
            if re.search(r"french|german|italian|dutch|franc[eê]s|alem[aã]o", low):
                return self._lang_level("none")
            return None

        def country(f):
            opts = f.get("options") or []
            if opts and not pick(opts, ["Brazil", "Brasil"]):
                return ["Other", "Outro", "Otro", "Andere", "Autre"]   # standing answer: country not listed -> Other
            return ["Brazil", "Brasil"]

        def ethnicity(f):
            opts = f.get("options") or []
            wanted = [s.get("race_ethnicity") or "Hispanic or Latino", "Hispanic/Latino", "Latino", "Hispanic", "Pardo"]
            if f.get("type") == "checkbox" or (opts and not pick(opts, wanted) and yes_no(opts, True)):
                return True   # "Are you Hispanic or Latino?" Yes/No
            return wanted

        def state(f):
            return ["Santa Catarina", "SC"]

        return [
            # identity and contact
            (r"^(legal )?first name|^given name|^primeiro nome|^vorname|^prenom|^nombre$", lambda f: [c.get("first_name")]),
            (r"^(legal )?last name|^surname|^family name|^sobrenome|^nachname|^apellido|^nom de famille", lambda f: [c.get("last_name")]),
            (r"^(full |legal )?name$|^nome( completo)?$|^your name", lambda f: [c.get("name")]),
            (r"e-?mail", lambda f: [c.get("email")]),
            (r"country (phone )?code|phone country|codigo do pais|ddi", const("+55", "Brazil (+55)", "Brasil (+55)", "Brazil")),
            (r"phone|mobile|telefone|celular|telefon|whatsapp", lambda f: [c.get("phone")]),
            (r"linkedin", lambda f: [self._url(c.get("linkedin"))]),
            (r"github", lambda f: [self._url(c.get("github"))]),
            (r"portfolio|personal (web)?site|website", lambda f: [c.get("portfolio")] if c.get("portfolio") else None),
            (r"zip|postal|\bcep\b|postleitzahl|code postal", lambda f: [c.get("zip_code")] if c.get("zip_code") else None),
            (r"neighbo|bairro|barrio", const("Centro")),
            (r"street|address line|^address$|endere[cç]o|logradouro|stra(ss|ß)e", lambda f: [c.get("street_address")] if c.get("street_address") else None),
            (r"^(current )?city$|^cidade|^ciudad|^stadt|^ville", const("Florianópolis", "Florianopolis")),
            (r"^(state|province|region|estado|provincia|bundesland)\b", state),
            (r"country of residence|^country$|^pais|^land\b|^pays|where do you (currently )?live|residence", country),
            (r"^(current )?location$|^localiza|where are you (currently )?(based|located)", lambda f: [c.get("city") or "Florianópolis, Santa Catarina, Brazil"]),
            # work authorization, relocation, schedule
            (r"(legally )?authori[sz]ed to work|work permit|right to work|eligible to work|autoriza[cç][aã]o de trabalho|arbeitserlaubnis", authorized),
            (r"sponsor|(require|need).{0,20}visa", sponsorship),
            (r"relocat|mudar(-se)? para|willing to move|reubica", yes),
            (r"hybrid|on-?site|in the office|office \d|days (a|per) week|commute|presencial|h[ií]brido", yes),
            (r"only (looking for )?(a )?(fully )?remote|strictly remote|fully remote only", no),
            (r"remote", yes),
            (r"18 years|over 18|age of 18|legal age|minimum (working )?age|maior de 18|mayor de edad", yes),
            (r"convicted|criminal|felony|pending charges|antecedentes", no),
            (r"currently (a |enrolled as a )?student|are you a student|estudante no momento|[eé]s estudiante", no),
            (r"how did you (hear|find)|where did you (hear|find)|referral source|source of (application|hire)|como (voc[eê] )?(soube|ficou sabendo)", const("LinkedIn", "Linkedin", "Social media", "Job board")),
            (r"(previously|ever|formerly) (been )?(employed|worked)|former employee|worked for .* before|j[aá] trabalhou", no),
            (r"relative|family member|close friend|parente", no),
            (r"government official|public official|politically exposed", no),
            (r"non-?compete|non-?solicit|restrictive covenant", no),
            (r"customer account|hold any accounts|account with (us|our)", no),
            (r"used (a|our|any) .*product|product in the last", no),
            (r"driver'?s? licen|carteira de motorista|\bcnh\b|f[uü]hrerschein", yes),
            (r"references", yes),
            (r"background check|privacy|terms|data (processing|protection|retention)|talent (pool|community)|consent|"
             r"i (agree|acknowledge|certify|confirm|understand)|attest|acknowledg|nda|non-disclosure|e-?signature|declaro|aceito|concordo", yes),
            # dates and notice
            (r"notice period|aviso pr[eé]vio|k[uü]ndigungsfrist", lambda f: ["21"] if f.get("type") == "number" or "day" in norm(f.get("label")) else ["3 weeks", "2-4 weeks", "1 month or less", "Less than 1 month"]),
            (r"start date|available (from|to start)|availability date|earliest start|when can you start|data dispon|verf[uü]gbar ab|fecha de disponibilidad",
             lambda f: ["2"] if f.get("type") == "number" else [self._date_start()]),
            # self identification (the candidate chose to answer these)
            (r"gender|g[eê]nero|\bsexo\b|geschlecht", lambda f: [ident.get("gender") or s.get("gender"), "Man", "Masculino", "Homem", "Male"]),
            (r"hispanic|latin|race|ethnic|ra[cç]a|etnia", ethnicity),
            (r"veteran", lambda f: [ident.get("veteran"), "I am not a protected veteran", "No", "Not a veteran"]),
            (r"disab|defici[eê]ncia|\bpcd\b", lambda f: [ident.get("disability"), "No, I do not have a disability", "No", "Não"]),
            # education and current role
            (r"highest (level of )?education|degree|escolaridade|grau de forma", const(DEGREE, "Bachelor's", "Bachelor", "Bacharelado", "Graduação", "Ensino superior completo")),
            (r"school|university|institution|universidade|institui[cç][aã]o|faculdade", const(SCHOOL, "Other", "Outro")),
            (r"field of study|major|discipline|area of study|curso|[aá]rea de (estudo|forma)", const(FIELD_OF_STUDY, "Engineering", "Environmental Engineering", "Engenharia")),
            (r"graduation (year|date)|year of graduation|ano de (conclus|forma)", const(GRADUATION_YEAR)),
            (r"current (employer|company)|empresa atual", const("Self-employed")),
            (r"current (job )?title|current (role|position)|cargo atual", const("Data & AI Engineer")),
            (r"walk away|dealbreaker|make you (want to )?leave|culture .* leave", lambda f: [s.get("dealbreakers_culture_or_environment_that_would_make_you_leave", "").replace(" (Paste in the language of the question.)", "")] if s.get("dealbreakers_culture_or_environment_that_would_make_you_leave") else None),
            (r"reason for leaving|motivo (da )?sa[ií]da", lambda f: None),   # needs the role it belongs to: left to the AI with the standing answers
            # languages and years (after the rules above, which own their wording)
            (r"english|ingl[eê]s|spanish|espanhol|portuguese|portugu[eê]s|french|german|franc[eê]s|alem[aã]o", language),
            (r"years|anos de|a[nñ]os de", years),
        ]

    def answer(self, field: Dict[str, Any]) -> Optional[str]:
        label = norm(field.get("label"))
        if not label:
            return None
        kind = field.get("type") or "text"
        options = field.get("options") or []
        for rx, fn in self.rules:
            if not re.search(rx, label):
                continue
            value = fn(field)
            if value is None:
                return None
            return self._shape(kind, options, value)
        return None

    def _shape(self, kind: str, options: List[str], value: Any) -> Optional[str]:
        if isinstance(value, bool):
            if kind == "checkbox":
                return "true" if value else "false"
            if kind in ("select", "radio") or options:
                return yes_no(options, value)
            return ("Yes" if value else "No")
        candidates = [str(v).strip() for v in (value if isinstance(value, (list, tuple)) else [value]) if v is not None and str(v).strip()]
        if not candidates:
            return None
        if kind in ("select", "radio") or options:
            return pick(options, candidates)
        if kind == "checkbox":
            return None
        if kind == "number":
            digits = re.findall(r"\d+(?:[.,]\d+)?", candidates[0])
            return digits[0].replace(",", ".") if digits else None
        return candidates[0]


def map_fields(fields: List[Dict[str, Any]], facts: dict, job: Optional[dict] = None, lang: str = "English",
               today: Optional[date] = None) -> Dict[str, str]:
    mapper = FormMapper(facts, job, lang, today)
    out: Dict[str, str] = {}
    for f in fields:
        if f.get("key") and not f.get("current"):
            v = mapper.answer(f)
            if v is not None:
                out[f["key"]] = v
    return out
