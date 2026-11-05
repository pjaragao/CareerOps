"""The invite sent by the worker itself: Playwright and the real mouse, no extension. The fallback of the extension's flow.

It runs only after the extension's flow reached the final click (status verifying) and the check found no proof, and only
when the profile still offers Connect: then nothing went out (2026-11-05: Thiago Reis' dialog took the extension's "Send
without a note", closed, and sent nothing; the check found Connect still in the More menu). At most once per action.

Layered like the rest: the Connect button on top of the profile's own card (the old layout), then the More menu's
/preload/custom-invite/ link of this very profile (late 2026). The dialog: only "Send without a note", found also in closed
shadow roots (clicks._find_button). A dialog with anything else (an e-mail to fill, no such button) is left alone and
said, never answered."""
import logging
import re
from typing import Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from playwright.async_api import Error as PlaywrightError, Page

from . import clicks

log = logging.getLogger("worker.connect_engine")

MORE = clicks.MORE
CONNECT = re.compile(r"^\s*(connect|conectar)\s*$", re.I)
PENDING = re.compile(r"^\s*(pending|pendente)\b", re.I)
EMAIL = re.compile(r"e-?mail", re.I)


async def _top_card(page: Page):
    """The profile's own card: the first section of <main> that holds the name heading. Cards of other people below never."""
    card = page.locator("main section").filter(has=page.locator("h1")).first
    return card if await card.count() else None


async def _menu_items(page: Page) -> list:
    items = page.get_by_role("menuitem")
    out = []
    for i in range(await items.count()):
        item = items.nth(i)
        if await item.is_visible():
            out.append(((await item.inner_text()).strip().split("\n")[0], item))
    return out


async def offers_connect(page: Page) -> Tuple[bool, str]:
    """(Connect is offered, where). Pending anywhere on the card or in the menu means it went out: False."""
    card = await _top_card(page)
    if not card:
        return False, ""
    labels = [((await b.inner_text()).strip().split("\n")[0], (await b.get_attribute("aria-label")) or "")
              for b in await card.get_by_role("button").all() if await b.is_visible()]
    if any(PENDING.match(t) or PENDING.match(a) for t, a in labels):
        return False, ""
    if any(CONNECT.match(t) for t, _ in labels):
        return True, "top"
    more = card.get_by_role("button", name=MORE).first
    if not await more.count():
        return False, ""
    await more.click(timeout=5000)
    await page.wait_for_timeout(1200)
    try:
        texts = [t for t, _ in await _menu_items(page)]
    finally:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)
    if any(PENDING.match(t) or re.match(r"^\s*(withdraw|retirar)", t, re.I) for t in texts):
        return False, ""
    return (True, "menu") if any(CONNECT.match(t) for t in texts) else (False, "")


async def _dialog_text(page: Page) -> str:
    """The text of what opened, also inside closed shadow roots (CDP pierces them)."""
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
        if n.get("nodeType") == 1 and (attrs.get("role") in ("dialog", "alertdialog") or "send-invite" in attrs.get("class", "")):
            out.append(re.sub(r"\s+", " ", text(n)).strip())
        for c in (n.get("children") or []) + (n.get("shadowRoots") or []):
            dialogs(c, out)
        return out
    return " | ".join(t for t in dialogs(root, []) if t)[:500]


async def send(page: Page, action: dict) -> Tuple[bool, str]:
    """Sends the invite with the mouse. Returns (clicked Send, what was seen). Never clicks anything but Connect of this
    profile and "Send without a note"."""
    slug = clicks.profile_slug(action["target_url"])
    if not slug:
        return False, "endereço sem perfil"
    await page.goto(action["target_url"].split("#")[0], wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(4000)
    if clicks.profile_slug(page.url) != slug:
        return False, f"o perfil abriu outro endereço: {page.url}"
    offered, where = await offers_connect(page)
    if not offered:
        return False, "o perfil não oferece Conectar (já pendente ou conectado)"
    card = await _top_card(page)
    if where == "top":
        await card.get_by_role("button", name=CONNECT).first.click(timeout=5000)
    else:
        await card.get_by_role("button", name=MORE).first.click(timeout=5000)
        await page.wait_for_timeout(1200)
        link = None
        for _, item in await _menu_items(page):
            href = await item.get_attribute("href") or ""
            if "custom-invite" in href and unquote((parse_qs(urlparse(href).query).get("vanityName") or [""])[0]).lower() == slug:
                link = item
                break
        if link is None:
            await page.keyboard.press("Escape")
            return False, "o Conectar do menu não é deste perfil"
        await link.click(timeout=5000)
    await page.wait_for_timeout(2500)   # the dialog draws and settles before its button is pressed
    seen = await _dialog_text(page)
    if EMAIL.search(seen) and "add a note" not in seen.lower() and "adicionar nota" not in seen.lower():
        return False, f"a janela pede e-mail: {seen}"
    try:
        clicked = await clicks.click_send(page)
    except PlaywrightError as e:
        return False, f"clique falhou: {e}"
    if not clicked:
        await page.keyboard.press("Escape")
        return False, f"sem 'Enviar sem nota' na janela: {seen}"
    await page.wait_for_timeout(3000)
    return True, seen


async def fallback(page: Page, action: dict) -> Optional[str]:
    """Runs the engine; returns what it says, for the events. Errors never escape: the check after it decides."""
    try:
        clicked, seen = await send(page, action)
    except PlaywrightError as e:
        clicked, seen = False, f"erro do navegador: {e}"
    log.info("action %s: connect engine: %s (%s)", action["id"], "sent" if clicked else "not sent", seen[:200])
    return ("sent: " if clicked else "not sent: ") + seen
