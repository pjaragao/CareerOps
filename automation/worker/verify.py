"""Whether a write really happened, read from the page by the worker. Neither the extension nor the model saying so counts."""
import re
import unicodedata
from urllib.parse import unquote, urlparse
from typing import Tuple

from playwright.async_api import Error as PlaywrightError

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
    """What the visible buttons/links/menu items say: their text AND their aria-label (LinkedIn puts the state in either one)."""
    return await page.evaluate(
        """(scope) => {
            const out = [];
            for (const b of document.querySelectorAll(`${scope} button, ${scope} [role="button"], ${scope} a, ${scope} [role="menuitem"]`)) {
                if (b.offsetParent === null || b.closest('.careerops-card')) continue;
                const text = (b.innerText || '').trim().split('\\n')[0];
                const aria = (b.getAttribute('aria-label') || '').trim();
                if (text) out.push(text);
                if (aria) out.push(aria);
            }
            return out.slice(0, 400);
        }""", scope)


async def _lines(page) -> list:
    """The profile's text, line by line: a lone "Pending" line is the state of the button even when it is no <button>."""
    text = await _main_text(page)
    return [ln.strip() for ln in text.split("\n") if ln.strip()][:400]


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
    if kind == "follow":
        return await _prove_state(page, FOLLOWING, IN_MENU_FOLLOWING, NOTE_FOLLOWING, url)
    proof, evidence = await _prove_state(page, PENDING, IN_MENU_PENDING, NOTE_PENDING, url)
    if not proof:   # last layer: the list of invitations you sent names the person, whatever the profile page shows
        listed = await _in_sent_invitations(page, url)
        if listed:
            return True, {"url": page.url, "button": "sent invitations list"}
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)   # leave the profile there for the screenshot
        await page.wait_for_timeout(2000)
    return proof, evidence


# the state spelled out in an aria-label or a banner, in the languages LinkedIn answers in
NOTE_PENDING = re.compile(r"\b(pending|pendente|pendiente|en attente|ausstehend|in sospeso)\b|invitation sent|convite enviado|"
                          r"invitaci[oó]n enviada|withdraw (invitation|request)|retirar convite|cancelar convite", re.I)
NOTE_FOLLOWING = re.compile(r"^\s*(following|seguindo|siguiendo)\b|unfollow|deixar de seguir|dejar de seguir", re.I)


async def _prove_state(page, button, in_menu, note, url):
    """Layers, each only when the one before found nothing: the buttons' text or aria-label, a lone line of the top of the
    profile, the More menu; then the page is loaded again once (a cached or half-drawn page) and everything is looked at again."""
    for attempt in range(2):
        labels = await _button_labels(page)
        found = next((label for label in labels if button.search(label)), None)
        if not found:   # the state spelled out in an aria-label: only at the top of the page (the profile's own card), never the cards of others below
            found = next((label for label in labels[:40] if note.search(label) and len(label) < 120), None)
        if not found:
            found = next((ln for ln in (await _lines(page))[:60] if button.search(ln) and len(ln) < 40), None)
        if not found:   # 1st-degree profiles (and others): no Following/Pending on top, it sits in the "More" menu
            found = await _in_more_menu(page, in_menu)
        if found:
            return True, {"url": page.url, "button": found}
        if attempt == 0:
            await page.reload(wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4500)
    return False, {"url": page.url, "button": None}


SENT_LIST = "https://www.linkedin.com/mynetwork/invitation-manager/sent/"


async def _in_sent_invitations(page, url) -> bool:
    slug = urlparse(url).path.strip("/").split("/")[-1].lower()
    if not slug:
        return False
    try:
        await page.goto(SENT_LIST, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(4500)
        hrefs = await page.evaluate("() => [...document.querySelectorAll('a[href*=\"/in/\"]')].map((a) => a.getAttribute('href') || '')")
    except PlaywrightError:
        return False
    return any(unquote(urlparse(h).path).lower().strip("/").endswith("in/" + slug) for h in hrefs)


# what the "More" menu says once it happened: you can unfollow / the invitation can be withdrawn
IN_MENU_FOLLOWING = re.compile(r"^\s*(unfollow|deixar de seguir|following|seguindo)\b", re.I)
IN_MENU_PENDING = re.compile(r"^\s*(pending|pendente|pendiente|withdraw|retirar|retirer|cancelar convite)\b", re.I)
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
        for i in range(await items.count()):   # the state may be only in the item's aria-label ("Withdraw invitation to ...")
            texts.append(((await items.nth(i).get_attribute("aria-label")) or "").strip())
        return next((t for t in texts if t and pattern.search(t)), None)
    finally:
        await page.keyboard.press("Escape")
