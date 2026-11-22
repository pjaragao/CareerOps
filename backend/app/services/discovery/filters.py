"""The cheap filter: no AI. It keeps a job only when the title is one of the four families of the profile, the place can be
done from Brazil (or comes with a visa), and the ad is in a language the candidate works in. Most of what the sources bring
stops here, so the AI reads only what has a real chance.

The places follow the decisions of 2026-11-22:
- remote open to Brazil / LATAM / the Americas / anywhere: kept (mode remoto-br);
- a foreign company's job in Brazil, on-site or hybrid: kept (mode brasil-local; the triage still drops Brazilian employers);
- Europe or the US: only with visa sponsorship or relocation in the ad (visto-eu / visto-us);
- "Remote - Europe/EMEA" without a visa: dropped, unless the ad talks of contractors, EOR or LATAM (remoto-latam);
- anything else (Remote - US only, India, Canada...): dropped.
"""
import re
from dataclasses import dataclass
from typing import Optional

from app.services.job_search_service import _EUROPE, _LATAM, _US, _US_STATE
from app.services.discovery.sources import Job

# title → family (the groups of the LinkedIn search), most specific first
FAMILIES = [
    ("nicho", r"utility rate|\bppp\b|concession|infrastructure (advisory|finance)|climate finance|sustainable (infrastructure|finance)|"
              r"development finance|energy transition|water (infrastructure|utility|resources)|renewable|power (markets?|purchase)|\bppa\b"),
    ("financas", r"financial model|fp&a|fp ?& ?a|\bfpa\b|project finance|corporate finance|strategic finance|valuation|"
                 r"financial (analyst|planning|manager|controller|lead|director)|finance (manager|director|lead|analyst|business partner|transformation|automation)|"
                 r"investment (analyst|associate|manager)|\bcfo\b|head of finance|pricing (manager|analyst|lead|strategy)|treasury|"
                 r"m&a|deal (advisory|analyst)|transaction (services|advisory)|cost manag"),
    ("ia", r"\bai\b|a\.i\.|artificial intelligence|\bllm|genai|gen ai|generative|machine learning|\bml\b|mlops|forward[- ]deploy|"
           r"solutions? (engineer|architect)|automation (engineer|lead|architect)|ai agents?|agentic|agents? (engineer|developer)|"
           r"prompt engineer|applied scien"),
    ("dados", r"data scien|forecast|time series|analytics engineer|data (analyst|engineer|lead|manager)|business intelligence|\bbi\b|"
              r"quantitative|\bquant\b|decision scien|econometric|statistic"),
]
_FAMILY_RE = [(g, re.compile(p, re.I)) for g, p in FAMILIES]
# not the profile, whatever the family word: too junior, or another trade
_NOT_FOR_YOU = re.compile(
    r"\bintern(ship)?\b|\bjunior\b|\bjr\.?\b|\btrainee\b|graduate|working student|werkstudent|est[aá]gi|apprentice|praktik|"
    r"\bsales (development|representative|executive)\b|\baccount executive\b|\bsdr\b|\bbdr\b|recruiter|talent acquisition|"
    r"nurse|physician|driver|warehouse|technician|customer (support|service|success agent)|call cent|teacher|tutor|annotat|"
    r"data entry|labell?ing|\bexpert\b\s*(?:[-–(:]|$)|rlhf|"
    r"ai trainer|writing (evaluator|specialist)|freelance writer|content writer|copywriter|"
    r"frontend|front-end|ios\b|android\b|mobile engineer|\bqa\b|quality assurance|test engineer|game|unity|embedded|firmware|"
    r"security engineer|soc analyst|penetration|network engineer|hardware|chip|asic|fpga|electrical engineer|mechanical",
    re.I)
# where the job may be done, read from the place and the ad
# Brazil by name or city; no state codes: the sources write ISO country codes, and "RS" is Serbia there (seen live 2026-11-22)
_BRAZIL = re.compile(r"(?i:\bbrazil\b|\bbrasil\b|s[aã]o paulo|rio de janeiro|belo horizonte|curitiba|florian[oó]polis|porto alegre|"
                     r"recife|bras[ií]lia|campinas|fortaleza|salvador|goi[aâ]nia)|\bBR\b")
_LATAM_RE = re.compile(r"(?<!new )(?:" + _LATAM + ")", re.I)
# said in so many words; a bare "Remote" is not enough (it often means "in the US"): the ad is read for that
_ANY_RE = re.compile(r"worldwide|anywhere|\bglobal\b|work from anywhere|all countries|any country", re.I)
_EUROPE_RE = re.compile(_EUROPE, re.I)
_US_RE = re.compile(_US + r"|\bus\b|\bu\.s\.", re.I)
_OTHER_RE = re.compile(r"\b(india|bangalore|bengaluru|hyderabad|pune|canada|toronto|vancouver|australia|sydney|melbourne|"
                       r"new zealand|singapore|japan|tokyo|china|hong kong|korea|philippines|manila|indonesia|vietnam|"
                       r"pakistan|nigeria|kenya|south africa|egypt|israel|tel aviv|uae|dubai|saudi|qatar|turkey|istanbul)\b", re.I)
_REMOTE = re.compile(r"\bremote\b|\bremoto\b|work from home|wfh|telecommut|distributed", re.I)
VISA = re.compile(r"visa sponsorship|sponsor(ing|ship)? (a |your |the )?(work )?visa|visa (support|assistance)|"
                  r"relocation (support|package|assistance|bonus|allowance)|we (will|can|do) sponsor|h-?1b|blue card|"
                  r"work permit (support|sponsorship)|relocate to (lisbon|madrid|amsterdam|berlin|dublin|barcelona|munich|london)", re.I)
NO_VISA = re.compile(r"(no|not|unable to|cannot|can't|can ?not|won't|will not|do not|does not|don't|doesn't)\s+(be able to\s+)?"
                     r"(provide|offer|support|sponsor)\w*\s+(any\s+)?(visa|sponsorship|work authori)|"
                     r"without (the need for )?(visa )?sponsorship|sponsorship (is )?not (available|provided|offered)", re.I)
CONTRACTOR = re.compile(r"\bcontractor\b|independent contractor|\beor\b|employer of record|\bdeel\b|\bremote\.com\b|\boyster\b|"
                        r"latin america|\blatam\b|south america|the americas", re.I)
# the ad itself says the job is only for people living in one country (and it is not Brazil)
RESIDENCY = re.compile(
    r"(must|need to|required to|should)\s+(be\s+)?(currently\s+)?(based|located|reside|residing|live|living)\s+(in|within)\s+(the\s+)?"
    r"(united states|u\.s\.|us\b|usa|canada|united kingdom|uk\b|europe|eu\b|european union|india|australia)|"
    r"(us|u\.s\.|uk|eu|canada)[- ]based (candidates|applicants) only|only (open to|accepting|considering) "
    r"(candidates|applicants)\s+(who are\s+)?(based |located |residing )?(in|from)\s+(the\s+)?(us|u\.s\.|united states|uk|canada|eu|europe)|"
    r"authori[sz]ed to work in the (united states|us|u\.s\.|uk|eu)\b(?![^.]{0,60}sponsor)", re.I)
# a few common words per language: enough to tell English, Spanish and Portuguese from German, French, Dutch, Polish, Italian
_WORDS = {
    "en": "the and with you for our are will this that your have from experience team".split(),
    "es": "el los las con para una del que por como experiencia equipo trabajo".split(),
    "pt": "os das com para uma não você que por como experiência equipe trabalho".split(),
    "de": "und der die das mit für wir sie ist ein eine auf bei erfahrung".split(),
    "fr": "et les des avec pour vous nous une est sur dans expérience équipe".split(),
    "nl": "en het een met voor wij je van zijn op ervaring".split(),
    "it": "e il della con per una che sono nel esperienza squadra".split(),
    "pl": "i w z na do się jest oraz dla doświadczenie".split(),
}
LANGUAGES_OK = ("en", "es", "pt")


@dataclass
class Verdict:
    keep: bool
    reason: str = ""              # why it was dropped (for the counts)
    group: Optional[str] = None   # financas | dados | ia | nicho
    mode: Optional[str] = None    # remoto-br | remoto-latam | brasil-local | visto-eu | visto-us
    affinity: int = 0             # for the order when the day's limit cuts


def family(title: str) -> Optional[str]:
    for group, pattern in _FAMILY_RE:
        if pattern.search(title or ""):
            return group
    return None


def language(text: str) -> str:
    words = re.findall(r"[a-zà-ÿ]+", (text or "")[:4000].lower())
    if len(words) < 30:
        return "en"   # too short to tell: the triage reads it
    counts = {lang: sum(1 for w in words if w in vocab) for lang, vocab in _WORDS.items()}
    return max(counts, key=counts.get)


def place(job: Job) -> tuple:
    """(mode, reason): mode None when the job cannot be done from Brazil."""
    where = " ".join([job.location or ""] + [c for c in job.countries if c])
    desc = job.description or ""
    remote = bool(job.remote) or bool(_REMOTE.search(where))
    visa = (job.visa_hint or bool(VISA.search(desc))) and not NO_VISA.search(desc)
    if _BRAZIL.search(where) or any(c.upper() in ("BR", "BRA") for c in job.countries):
        return ("remoto-br" if remote else "brasil-local"), ""
    if _LATAM_RE.search(where):
        return "remoto-latam", ""
    if RESIDENCY.search(desc) and not CONTRACTOR.search(desc):
        return None, "residency"
    if _ANY_RE.search(where):
        return "remoto-br", ""
    if _EUROPE_RE.search(where) or any(c.upper() in EU_CODES for c in job.countries):
        if visa:
            return "visto-eu", ""
        if remote and CONTRACTOR.search(desc):
            return "remoto-latam", ""
        return None, "europe_no_visa"
    if _US_RE.search(where) or _US_STATE.search(job.location or "") or any(c.upper() in ("US", "USA") for c in job.countries):
        return ("visto-us", "") if visa else (None, "us_no_visa")
    if _OTHER_RE.search(where) or (job.countries and not remote):
        return None, "place"
    if remote or not where.strip():   # "Remote" and nothing else: the eligibility check reads the ad
        return "remoto-br", ""
    return None, "place"


EU_CODES = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
            "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB", "UK", "CH", "NO", "IS"}


def judge(job: Job) -> Verdict:
    title = job.title or ""
    if _NOT_FOR_YOU.search(title):
        return Verdict(False, "title_other")
    group = family(title)
    if not group:
        return Verdict(False, "title")
    if job.needs_detail and not job.description:
        mode, why = place(job)   # the place from the list alone; the ad is read only if this passes
        return Verdict(bool(mode) or why in ("europe_no_visa", "us_no_visa"), why if not mode else "", group, mode)
    lang = language(f"{title}\n{job.description}")
    if lang not in LANGUAGES_OK:
        return Verdict(False, f"language_{lang}")
    mode, why = place(job)
    if not mode:
        return Verdict(False, why, group)
    affinity = {"remoto-br": 3, "remoto-latam": 3, "brasil-local": 2, "visto-eu": 1, "visto-us": 0}.get(mode, 0)
    affinity += 2 if re.search(r"senior|sr\.?|lead|principal|staff|head|manager|director", title, re.I) else 0
    affinity += 1 if group in ("financas", "ia") else 0
    return Verdict(True, "", group, mode, affinity)
