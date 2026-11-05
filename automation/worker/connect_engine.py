"""The invite sent by the worker itself: Playwright and the real mouse, no extension. The fallback of the extension's flow.

It runs only after the extension's flow reached the final click (status verifying) and the check found no proof, and only
when the profile still offers Connect: then nothing went out (2026-11-05: Thiago Reis' dialog took the extension's "Send
without a note", closed, and sent nothing; the check found Connect still in the More menu). At most once per action.

Where Connect is, layered (LinkedIn keeps moving it):
  1. this profile's own /preload/custom-invite/?vanityName=<profile> link on top of its card (2026-11-05, Gavin Nicholls);
  2. a Connect button on the profile's own card (the old layout);
  3. the same link inside the card's More menu (late 2026).
The card is found by the profile's own link or by its name (from the tab title), in an h1 or an h2: never the cards of
other people below. The dialog: only "Send without a note", found also in closed shadow roots (clicks._find_button). A
dialog with anything else (an e-mail to fill, no such button) is left alone and said, never answered."""
import logging
import re
from typing import Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from playwright.async_api import Error as PlaywrightError, Locator, Page

from . import clicks

log = logging.getLogger("worker.connect_engine")

MORE = clicks.MORE
CONNECT = re.compile(r"^\s*(connect|conectar)\s*$", re.I)
PENDING = re.compile(r"^\s*(pending|pendente)\b", re.I)
WITHDRAW = re.compile(r"^\s*(withdraw|retirar)\b|withdraw invitation", re.I)
EMAIL = re.compile(r"e-?mail", re.I)


def _ours(href: str, slug: str) -> bool:
    return "custom-invite" in (href or "") and unquote((parse_qs(urlparse(href).query).get("vanityName") or [""])[0]).lower() == slug


async def _name(page: Page) -> str:
    title = await page.title()
    return re.split(r"\s*[|\-–]\s*LinkedIn", title or "")[0].strip()


async def _own_link(page: Page, slug: str) -> Optional[Locator]:
    """This profile's own Connect link on top of its card (not inside a menu)."""
    links = page.locator('main a[href*="custom-invite"]:not([role="menuitem"])')
    for i in range(await links.count()):
        link = links.nth(i)
        if await link.is_visible() and _ours(await link.get_attribute("href"), slug):
            return link
    return None


async def _card(page: Page, slug: str) -> Optional[Locator]:
    """The profile's own card: the smallest section of <main> with the profile's own link, else the one with its name as a
    heading (h1 or h2). Cards of other people below never."""
    sections = page.locator("main section")
    name = await _name(page)
    for i in range(min(await sections.count(), 8)):
        section = sections.nth(i)
        if await section.locator('a[href*="custom-invite"]').count():
            for j in range(await section.locator('a[href*="custom-invite"]').count()):
                if _ours(await section.locator('a[href*="custom-invite"]').nth(j).get_attribute("href"), slug):
                    return section
        if name and await section.locator("h1, h2").filter(has_text=re.compile(r"^\s*" + re.escape(name), re.I)).count():
            return section
    return None


async def _labels(card: Locator) -> list:
    out = []
    for b in await card.locator('button, a, [role="button"]').all():
        if await b.is_visible():
            out.append(((await b.inner_text()).strip().split("\n")[0], (await b.get_attribute("aria-label")) or ""))
    return out


async def _menu_items(page: Page) -> list:
    items = page.get_by_role("menuitem")
    out = []
    for i in range(await items.count()):
        item = items.nth(i)
        if await item.is_visible():
            out.append(((await item.inner_text()).strip().split("\n")[0], item))
    return out


async def offers_connect(page: Page, slug: str) -> Tuple[bool, str]:
    """(Connect is offered, where: link / button / menu). Pending or withdraw anywhere on the card or menu: False."""
    card = await _card(page, slug)
    if not card:
        return False, "sem cartão do perfil"
    labels = await _labels(card)
    if any(PENDING.match(t) or PENDING.match(a) or WITHDRAW.search(a) for t, a in labels):
        return False, "pendente"
    if await _own_link(page, slug):
        return True, "link"
    name = await _name(page)
    if any(CONNECT.match(t) or (name and a.lower() == f"invite {name.lower()} to connect") for t, a in labels):
        return True, "button"
    more = card.get_by_role("button", name=MORE).first
    if not await more.count():
        return False, "sem Conectar nem Mais"
    await more.click(timeout=5000)
    await page.wait_for_timeout(1200)
    try:
        items = await _menu_items(page)
    finally:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)
    texts = [t for t, _ in items]
    if any(PENDING.match(t) or WITHDRAW.search(t) for t in texts):
        return False, "pendente"
    return (True, "menu") if any(CONNECT.match(t) for t in texts) else (False, "sem Conectar")


async def _dialog_text(page: Page) -> str:
    """The text of what opened, also inside closed shadow roots (CDP pierces them). Hidden video-player dialogs are skipped."""
    session = await page.context.new_cdp_session(page)
    try:
        root = (await session.send("DOM.getDocument", {"depth": -1, "pierce": True}))["root"]
    finally:
        await session.detach()

    def text(n):
        if n.get("nodeType") == 3:
            return n.get("nodeValue", "")
        if n.get("nodeName") in ("SCRIPT", "STYLE"):
            return ""
        return " ".join(text(c) for c in (n.get("children") or []) + (n.get("shadowRoots") or []))

    def dialogs(n, out):
        attrs = dict(zip((n.get("attributes") or [])[::2], (n.get("attributes") or [])[1::2]))
        if n.get("nodeType") == 1 and "vjs-" not in attrs.get("class", "") and (
                attrs.get("role") in ("dialog", "alertdialog") or "send-invite" in attrs.get("class", "")):
            out.append(re.sub(r"\s+", " ", text(n)).strip())
        for c in (n.get("children") or []) + (n.get("shadowRoots") or []):
            dialogs(c, out)
        return out
    return " | ".join(t for t in dialogs(root, []) if t)[:500]


async def _open_dialog(page: Page, slug: str, where: str) -> bool:
    """One click on this profile's Connect, where it is. True when it was clicked."""
    if where == "link":
        link = await _own_link(page, slug)
        if not link:
            return False
        await link.click(timeout=5000)
        return True
    card = await _card(page, slug)
    if not card:
        return False
    if where == "button":
        name = await _name(page)
        target = card.get_by_role("button", name=CONNECT).first
        if not await target.count() and name:
            target = card.locator(f'[aria-label="Invite {name} to connect"]').first
        if not await target.count():
            return False
        await target.click(timeout=5000)
        return True
    await card.get_by_role("button", name=MORE).first.click(timeout=5000)
    await page.wait_for_timeout(1200)
    for _, item in await _menu_items(page):
        if _ours(await item.get_attribute("href") or "", slug):
            await item.click(timeout=5000)
            return True
    await page.keyboard.press("Escape")
    return False


async def send(page: Page, action: dict) -> Tuple[bool, bool, str]:
    """Sends the invite with the mouse. Returns (clicked Send, Connect was offered, what was seen). Never clicks anything
    but Connect of this profile and "Send without a note"."""
    slug = clicks.profile_slug(action["target_url"])
    if not slug:
        return False, False, "endereço sem perfil"
    await page.goto(action["target_url"].split("#")[0], wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(4500)
    if clicks.profile_slug(page.url) != slug:
        return False, False, f"o perfil abriu outro endereço: {page.url}"
    offered, where = await offers_connect(page, slug)
    if not offered:
        return False, False, f"o perfil não oferece Conectar ({where})"
    seen = ""
    for attempt in range(2):   # the dialog does not always open on the first click (Claude saw it open "this time")
        if not await _open_dialog(page, slug, where):
            return False, True, f"Conectar ({where}) não encontrado para clicar"
        await page.wait_for_timeout(2500)   # the dialog draws and settles before its button is pressed
        seen = await _dialog_text(page)
        if seen:
            break
        if attempt == 0:   # nothing opened: the page again, then one more click
            await page.reload(wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4500)
            offered, where = await offers_connect(page, slug)
            if not offered:   # it went out with the click after all
                return True, False, f"enviado sem janela ({where})"
    if EMAIL.search(seen) and "add a note" not in seen.lower() and "adicionar nota" not in seen.lower():
        return False, True, f"a janela pede e-mail: {seen}"
    try:
        clicked = await clicks.click_send(page)
    except PlaywrightError as e:
        return False, True, f"clique falhou: {e}"
    if not clicked:
        await page.keyboard.press("Escape")
        return False, True, f"sem 'Enviar sem nota' na janela: {seen or 'nenhuma janela abriu'}"
    await page.wait_for_timeout(3000)
    return True, True, seen


async def fallback(page: Page, action: dict) -> Tuple[str, bool]:
    """Runs the engine; returns (what it says, Connect was still offered). Errors never escape: the check after it decides."""
    try:
        clicked, offered, seen = await send(page, action)
    except PlaywrightError as e:
        clicked, offered, seen = False, False, f"erro do navegador: {e}"
    log.info("action %s: connect engine: %s (%s)", action["id"], "sent" if clicked else "not sent", seen[:200])
    return ("sent: " if clicked else "not sent: ") + seen, offered
