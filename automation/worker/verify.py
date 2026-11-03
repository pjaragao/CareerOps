"""Whether a write really happened, read from the page by the worker. Neither the extension nor the model saying so counts."""
import re
import unicodedata
from typing import Tuple

APPLIED = re.compile(r"\bapplied \d|\bapplied\b.{0,20}\bago\b|application submitted|you applied|candidatou-se|candidatura enviada|"
                     r"voc[eê] se candidatou", re.I)
FOLLOWING = re.compile(r"^\s*(following|seguindo)\b", re.I)
PENDING = re.compile(r"^\s*(pending|pendente)\b", re.I)
EXTERNAL_SENT = re.compile(r"thank you for (applying|your application|your interest)|thanks for applying|application (has been |was )?(received|submitted|sent)|"
                           r"we (have )?received your application|obrigad[oa] por se candidatar|candidatura (foi )?(recebida|enviada)|recebemos sua candidatura", re.I)


def normalize(text: str) -> str:
    plain = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", plain).strip().lower()


def applied_in(page_text: str) -> bool:
    return bool(APPLIED.search(page_text or ""))


def comment_in(page_text: str, comment: str) -> bool:
    target = normalize(comment)
    return bool(target) and target in normalize(page_text)


def external_sent_in(page_text: str) -> bool:
    return bool(EXTERNAL_SENT.search(page_text or ""))


async def _button_labels(page, scope: str = "main") -> list:
    return await page.evaluate(
        """(scope) => [...document.querySelectorAll(`${scope} button, ${scope} [role="button"], ${scope} a`)]
            .filter((b) => b.offsetParent !== null && !b.closest('.careerops-card'))
            .map((b) => (b.innerText || b.getAttribute('aria-label') || '').trim().split('\\n')[0]).slice(0, 200)""", scope)


async def _main_text(page) -> str:
    return await page.evaluate("() => (document.querySelector('main') || document.body).innerText || ''")


async def prove(page, action: dict) -> Tuple[bool, dict]:
    """Opens the target again and looks. Returns (proof, evidence). The page is left there for a screenshot."""
    kind = action["kind"]
    url = action["target_url"]
    if action["lane"] == "ats":   # the form's own page, kept open: the address may have moved on after sending
        text = await _main_text(page)
        return external_sent_in(text), {"url": page.url}
    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(3500)
    if kind == "apply":
        return applied_in(await _main_text(page)), {"url": page.url}
    if kind == "comment":
        text = action["payload"].get("text") or ""
        return comment_in(await page.evaluate("() => document.body.innerText || ''"), text), {"url": page.url}
    labels = await _button_labels(page)
    pattern = FOLLOWING if kind == "follow" else PENDING
    found = next((label for label in labels if pattern.search(label)), None)
    if not found:   # 1st-degree profiles (and others): no Following/Pending on top, it sits in the "More" menu
        found = await _in_more_menu(page, IN_MENU_FOLLOWING if kind == "follow" else IN_MENU_PENDING)
    return bool(found), {"url": page.url, "button": found}


# what the "More" menu says once it happened: you can unfollow / the invitation can be withdrawn
IN_MENU_FOLLOWING = re.compile(r"^\s*(unfollow|deixar de seguir|following|seguindo)\b", re.I)
IN_MENU_PENDING = re.compile(r"^\s*(pending|pendente|withdraw|retirar)\b", re.I)
MORE = re.compile(r"^\s*(more|mais)(\s+(actions|a[cç][oõ]es))?\s*$", re.I)


async def _in_more_menu(page, pattern):
    """Opens the profile's "More" menu, reads its items and closes it (Escape): a look, never a click on an item."""
    more = page.locator("main").get_by_role("button", name=MORE).first
    if not await more.count():
        return None
    try:
        await more.click(timeout=5000)
        await page.wait_for_timeout(1200)
        items = page.get_by_role("menuitem")   # in the page or in LinkedIn's shadow-root layer: the locator reaches both
        texts = [t.strip().split("\n")[0] for t in await items.all_inner_texts()]
        return next((t for t in texts if pattern.search(t)), None)
    finally:
        await page.keyboard.press("Escape")
