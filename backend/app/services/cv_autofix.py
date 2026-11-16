"""Deterministic fixes for what the CV reviewer keeps rejecting (2026-11-16): applied before every review round, so a
problem a rule can fix never costs a rewrite, and a CV never gets stuck on it.

  * contact line, links and plain characters (cv_format.normalize)
  * dates: numeric months ("03/2019") -> "Mar 2019"; year-only ranges -> the months the base resume gives that range
  * Portuguese bullets in the first person ("Opero", "Desenvolvo") -> third person ("Opera", "Desenvolve")
  * length: bullets cut from the least relevant sections until the PDF fits two pages (cv_review_service.fit_pages)

None of these adds a fact: dates come from the base resume, verbs keep their meaning, cuts only remove.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

MONTHS = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
          "pt": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]}
NUMERIC_MONTH = re.compile(r"\b(0?[1-9]|1[0-2])/((?:19|20)\d{2})\b")
YEAR_RANGE = re.compile(r"(?<![\w/])((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2}|present|presente|atual|current|now)\b", re.I)
MONTH_RANGE = re.compile(r"\b([A-Za-z]{3,9}\.?\s+((?:19|20)\d{2}))\s*[-–—]\s*([A-Za-z]{3,9}\.?\s+((?:19|20)\d{2})|present|presente|atual|current)\b", re.I)

# first person singular -> third person, the verbs a CV bullet starts with (Portuguese)
PT_VERBS = {
    "opero": "Opera", "desenvolvo": "Desenvolve", "construo": "Constrói", "lidero": "Lidera", "coordeno": "Coordena",
    "gerencio": "Gerencia", "crio": "Cria", "projeto": "Projeta", "modelo": "Modela", "implemento": "Implementa",
    "automatizo": "Automatiza", "analiso": "Analisa", "estruturo": "Estrutura", "conduzo": "Conduz", "elaboro": "Elabora",
    "entrego": "Entrega", "mantenho": "Mantém", "integro": "Integra", "atuo": "Atua", "dirijo": "Dirige", "defino": "Define",
    "oriento": "Orienta", "negocio": "Negocia", "planejo": "Planeja", "monitoro": "Monitora", "otimizo": "Otimiza",
    "reduzo": "Reduz", "aumento": "Aumenta", "treino": "Treina", "apoio": "Apoia", "preparo": "Prepara", "avalio": "Avalia",
    "publico": "Publica", "escrevo": "Escreve", "produzo": "Produz", "organizo": "Organiza", "acompanho": "Acompanha",
    "executo": "Executa", "valido": "Valida", "documento": "Documenta", "arquiteto": "Arquiteta", "faço": "Faz", "sou": "É",
}
BULLET_VERB = re.compile(r"^(\s*[-*+]\s+)(\w+)", re.M)


def _lang(markdown: str) -> str:
    from app.services import cv_format
    return "pt" if cv_format.is_portuguese(markdown) else "en"


def numeric_months(markdown: str, lang: str) -> str:
    names = MONTHS[lang]
    return NUMERIC_MONTH.sub(lambda m: f"{names[int(m.group(1)) - 1]} {m.group(2)}", markdown)


def base_ranges(base: str) -> Dict[tuple, str]:
    """(start year, end year or 'present') -> the month range the base resume writes for it."""
    out: Dict[tuple, str] = {}
    for m in MONTH_RANGE.finditer(base or ""):
        end = m.group(4) or m.group(3)
        end_key = end.lower() if not re.match(r"\d", end or "") else end
        if end_key in ("presente", "atual", "current"):
            end_key = "present"
        out.setdefault((m.group(2), end_key), m.group(0))
    return out


def year_ranges(markdown: str, base: str) -> str:
    """A role dated only by years takes the months the base resume gives that same range (never invented)."""
    known = base_ranges(base)
    if not known:
        return markdown

    def swap(m):
        end = m.group(2).lower()
        end = "present" if end in ("presente", "atual", "current", "now") else end
        return known.get((m.group(1), end), m.group(0))
    has_months = re.search(r"\b(?:jan|feb|fev|mar|apr|abr|may|mai|jun|jul|aug|ago|sep|set|oct|out|nov|dec|dez)[a-z]*\.?\s+\d{4}", markdown, re.I)
    return YEAR_RANGE.sub(swap, markdown) if has_months else markdown


def impersonal_pt(markdown: str) -> str:
    def swap(m):
        word = m.group(2)
        repl = PT_VERBS.get(word.lower())
        return f"{m.group(1)}{repl}" if repl else m.group(0)
    return BULLET_VERB.sub(swap, markdown)


def autofix(markdown: str, base: str = "", portfolio_link: Optional[str] = None, personal: Optional[dict] = None,
            fit=None) -> str:
    """Every deterministic fix, in order. `fit` (cv_review_service.fit_pages) cuts to two pages when given."""
    from app.services import cv_format
    if not (markdown or "").strip():
        return markdown
    lang = _lang(markdown)
    text = numeric_months(markdown, lang)
    text = year_ranges(text, base)
    if lang == "pt":
        text = impersonal_pt(text)
    keeps_portfolio = "[Portf" in text
    text = cv_format.normalize(text, portfolio_link, lang == "pt", personal) if not keeps_portfolio else text
    if fit:
        fitted = fit(text)
        if fitted:
            text = fitted
    return text
