"""Deterministic navigation of company application forms (token plan, phase 2): after the extension filled a step with
nothing left pending, the worker itself clicks Next / Submit, with no LLM. Only a step it cannot advance (a field left,
an error on the page, an unknown layout) goes to the Claude routine, with the form open where it stopped.

One adapter per ATS family (button wording and how a step shows an error), plus a generic one. Each also tries the
labels learned from earlier successful runs on the same host (recipes, stored by the backend). Every miss is explicit:
step() returns a reason, never a guessed click."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError, Page

ATTRIBUTE = "data-careerops-form"   # set by apply_copilot.js after each filled step: {"sig", "filled", "pending"}

NEXT = ("next", "continue", "save and continue", "save & continue", "proceed", "next step", "review", "review application",
        "apply", "apply now", "apply for this job", "apply for this position", "candidatar-se", "candidate-se", "jetzt bewerben", "postuler",
        "proximo", "próximo", "continuar", "avançar", "avancar", "salvar e continuar", "siguiente", "continuar", "weiter",
        "nächster schritt", "suivant", "continuer")
# "Apply" on a job page only opens the form: it is navigation (NEXT), never the final submit
SUBMIT = ("submit", "submit application", "submit your application", "send application", "enviar candidatura",
          "finalizar candidatura", "enviar solicitud", "bewerbung senden", "bewerbung absenden", "envoyer ma candidature",
          "send my application", "complete application")
ERROR_TEXT = re.compile(r"\b(this field is required|is required|required field|campo obrigat[oó]rio|obrigat[oó]rio|"
                        r"please (fill|complete|enter|select)|pflichtfeld|champ obligatoire|campo requerido)\b", re.I)


def norm(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text or "")
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plain).strip().lower().rstrip(".!→>»› ")


@dataclass
class Adapter:
    name: str
    hosts: Tuple[str, ...] = ()
    next_labels: Tuple[str, ...] = NEXT
    submit_labels: Tuple[str, ...] = SUBMIT
    single_page: bool = False          # the whole form on one page: only Submit is looked for
    learned_next: List[str] = field(default_factory=list)
    learned_submit: List[str] = field(default_factory=list)

    def matches(self, host: str) -> bool:
        return any(host == h or host.endswith("." + h) for h in self.hosts)


ADAPTERS = [
    Adapter("greenhouse", ("greenhouse.io",), submit_labels=("submit application", "submit"), single_page=True),
    Adapter("ashby", ("ashbyhq.com",), submit_labels=("submit application", "submit"), single_page=True),
    Adapter("lever", ("lever.co",), submit_labels=("submit application", "submit"), single_page=True),
    Adapter("personio", ("personio.com", "personio.de"), submit_labels=("send application", "submit application", "bewerbung senden", "absenden", "submit")),
    Adapter("workday", ("myworkdayjobs.com", "workday.com"), next_labels=("save and continue", "next", "continue", "review"),
            submit_labels=("submit",)),
    Adapter("smartrecruiters", ("smartrecruiters.com",), next_labels=("next", "continue"), submit_labels=("submit", "send application")),
    Adapter("teamtailor", ("teamtailor.com",), submit_labels=("send application", "submit application", "submit"), single_page=True),
    Adapter("recruitee", ("recruitee.com",), submit_labels=("send", "apply", "submit"), single_page=True),
    Adapter("successfactors", ("successfactors.com", "successfactors.eu"), next_labels=("next", "continue", "save and continue"),
            submit_labels=("submit", "submit application")),
    Adapter("icims", ("icims.com",), next_labels=("next", "continue", "save and continue"), submit_labels=("submit", "submit application")),
]
GENERIC = Adapter("generic")


def host_of(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower()


def adapter_for(url: str, recipe: Optional[dict] = None) -> Adapter:
    host = host_of(url)
    base = next((a for a in ADAPTERS if a.matches(host)), GENERIC)
    ad = Adapter(base.name, base.hosts, base.next_labels, base.submit_labels, base.single_page)
    if recipe:
        ad.learned_next = [norm(x) for x in recipe.get("next") or []]
        ad.learned_submit = [norm(x) for x in recipe.get("submit") or []]
    return ad


def _matches(name: str, labels: Iterable[str]) -> bool:
    n = norm(name)
    return bool(n) and any(n == norm(l) for l in labels)


async def ready_state(page: Page) -> Optional[dict]:
    """What the extension said about the step it filled last, or None while it has not finished one."""
    try:
        raw = await page.evaluate(f"() => document.documentElement.getAttribute('{ATTRIBUTE}')")
    except PlaywrightError:
        return None
    if not raw:
        return None
    try:
        import json
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


async def page_errors(page: Page) -> List[str]:
    """Visible validation errors after a click (aria-invalid fields, "required" messages)."""
    try:
        return await page.evaluate("""() => {
            const out = [];
            const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
            document.querySelectorAll('[aria-invalid="true"]').forEach((e) => { if (vis(e)) out.push((e.getAttribute('aria-label') || e.name || e.id || 'field').slice(0, 80)); });
            document.querySelectorAll('[role="alert"], .error, .field-error, .invalid-feedback, [class*="error-message"], [data-automation-id="errorMessage"]').forEach((e) => {
                const t = (e.innerText || '').trim(); if (t && vis(e)) out.push(t.slice(0, 120)); });
            return out.slice(0, 12);
        }""")
    except PlaywrightError:
        return []


async def empty_required(page: Page) -> List[str]:
    """Visible required fields still empty (inputs, text areas, lists, radio groups): never submitted like that."""
    try:
        return await page.evaluate("""() => {
            const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
            const out = [];
            const groups = new Set();
            document.querySelectorAll('input, textarea, select').forEach((e) => {
                const req = e.required || e.getAttribute('aria-required') === 'true';
                if (!req || !vis(e) || e.disabled || e.type === 'hidden') return;
                if (e.type === 'radio' || e.type === 'checkbox') {
                    if (!e.name || groups.has(e.name)) return;
                    groups.add(e.name);
                    const any = [...document.querySelectorAll(`input[name="${CSS.escape(e.name)}"]`)].some((x) => x.checked);
                    if (!any) out.push(e.name.slice(0, 60));
                    return;
                }
                if (e.type === 'file' ? !(e.files && e.files.length) : !String(e.value || '').trim())
                    out.push((e.getAttribute('aria-label') || e.name || e.id || e.placeholder || 'field').slice(0, 60));
            });
            return out.slice(0, 12);
        }""")
    except PlaywrightError:
        return []


async def _buttons(page: Page) -> List[Tuple[str, object]]:
    """Visible, enabled controls that act as buttons, with their accessible text."""
    loc = page.locator('button, input[type="submit"], input[type="button"], [role="button"], a[role="button"]')
    out = []
    count = min(await loc.count(), 80)
    for i in range(count):
        el = loc.nth(i)
        try:
            if not await el.is_visible() or not await el.is_enabled():
                continue
            name = (await el.get_attribute("aria-label")) or (await el.inner_text(timeout=1000)) or (await el.get_attribute("value")) or ""
        except PlaywrightError:
            continue
        name = norm(name)
        if name and len(name) <= 60:
            out.append((name, el))
    return out


async def find(page: Page, ad: Adapter) -> Tuple[Optional[str], Optional[object], Optional[str]]:
    """("next"|"submit", element, label) for the button that moves this form on; submit wins on a single-page form."""
    buttons = await _buttons(page)
    order = [("submit", ad.learned_submit), ("next", ad.learned_next)] if ad.single_page else [("next", ad.learned_next), ("submit", ad.learned_submit)]
    order += [("submit", ad.submit_labels), ("next", ad.next_labels)] if ad.single_page else [("next", ad.next_labels), ("submit", ad.submit_labels)]
    for kind, labels in order:
        if not labels:
            continue
        for name, el in buttons:
            if _matches(name, labels):
                return kind, el, name
    return None, None, None


@dataclass
class StepResult:
    outcome: str            # "next" | "submit_ready" | "stuck"
    label: str = ""
    reason: str = ""
    errors: List[str] = field(default_factory=list)
    element: object = None


async def step(page: Page, ad: Adapter) -> StepResult:
    """Looks at the filled step: the button to press next, or why it cannot go on. Never clicks Submit itself."""
    errors = await page_errors(page)
    if errors:
        return StepResult("stuck", reason="a página mostra erro antes de avançar", errors=errors)
    kind, el, name = await find(page, ad)
    if not kind:
        return StepResult("stuck", reason=f"nenhum botão de avançar/enviar reconhecido ({ad.name})")
    if kind == "submit":
        missing = await empty_required(page)
        if missing:
            return StepResult("stuck", reason="campos obrigatórios vazios antes do envio", errors=missing)
        return StepResult("submit_ready", label=name, element=el)
    return StepResult("next", label=name, element=el)
