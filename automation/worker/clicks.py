"""Clicks with the real mouse that the extension asks for. LinkedIn ignores a click made by a script on some elements (late
2026: the "More → Connect" link and the invite dialog's buttons), so the extension asks through an attribute on <html>.
The page could write that attribute too, so the worker clicks only fixed targets, each at most once per action:
  connect  the approved profile's own Connect link (/preload/custom-invite/?vanityName=<that profile>), on top of its card
           or in its More menu
  send     "Send without a note" in the invite dialog, only once the backend let the action send (status verifying)
Anything else asked is ignored."""
import logging
import re
import unicodedata
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

from playwright.async_api import Error as PlaywrightError, Page

log = logging.getLogger("worker.clicks")

ATTRIBUTE = "data-careerops-click"
MORE = re.compile(r"^\s*(more|mais)(\s+(actions|a[cç][oõ]es))?\s*$", re.I)
SEND_NO_NOTE = ("send without a note", "send without note", "enviar sem nota", "enviar sem uma nota")


def profile_slug(url: str) -> str:
    m = re.match(r"^/in/([^/?#]+)", urlparse(url or "").path)
    return unquote(m.group(1)).lower() if m else ""


async def asked(page: Page) -> Optional[str]:
    try:
        return await page.evaluate(f"() => document.documentElement.getAttribute('{ATTRIBUTE}')")
    except PlaywrightError:   # navigating right now
        return None


async def _done(page: Page) -> None:
    try:
        await page.evaluate(f"() => document.documentElement.removeAttribute('{ATTRIBUTE}')")
    except PlaywrightError:
        pass


async def click_connect(page: Page, action: dict) -> bool:
    """This profile's Connect link in the More menu: opened with the mouse when it is not open already."""
    slug = profile_slug(action["target_url"])
    if not slug or profile_slug(page.url) != slug:
        return False

    def ours(href: str) -> bool:
        return unquote((parse_qs(urlparse(href or "").query).get("vanityName") or [""])[0]).lower() == slug

    # this profile's own link on top of its card (2026-11-05, Gavin Nicholls: Connect is an <a> to custom-invite, no menu)
    top = page.locator('main a[href*="custom-invite"]:not([role="menuitem"])')
    for i in range(await top.count()):
        link = top.nth(i)
        if await link.is_visible() and ours(await link.get_attribute("href")):
            await link.click(timeout=5000)
            return True
    links = page.locator('a[role="menuitem"][href*="custom-invite"]')
    for _ in range(2):   # the menu may be open already (the extension's own click); otherwise More opens it
        for i in range(await links.count()):
            link = links.nth(i)
            if await link.is_visible() and ours(await link.get_attribute("href")):
                await link.click(timeout=5000)
                return True
        more = page.locator("main").get_by_role("button", name=MORE).first
        if not await more.count():
            return False
        await more.click(timeout=5000)
        await page.wait_for_timeout(1200)
    return False


NO_NOTE_WIDE = re.compile(r"^(send( the)?( invitation| invite)? without( a| an)?( personali[sz]ed)?( note| message)|enviar( o)?( convite)? sem( uma)?( nota| mensagem)|"
                          r"sem nota|enviar sin( una)?( nota| mensaje)|sin nota|inviare senza( una)? nota|senza nota|ohne( eine)? (nachricht|notiz) senden|envoyer sans( note| message))$")


def _norm(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text or "")
    return re.sub(r"\s+", " ", "".join(c for c in plain if not unicodedata.combining(c))).strip().lower().rstrip(".!…")


def _is_no_note(names) -> bool:
    return any(n in SEND_NO_NOTE or NO_NOTE_WIDE.match(n) for n in names if n)


def _find_button(node: dict, labels=None) -> Optional[dict]:
    """The "Send without a note" control by its aria-label, title or text, also inside closed shadow roots (the invite dialog
    lives in one). Layered: <button> first (the old way), then anything that acts as one (role=button, <a>, input)."""
    def text(n):
        return n.get("nodeValue", "") if n.get("nodeType") == 3 else " ".join(text(c) for c in n.get("children") or [])

    def names(n):
        attrs = dict(zip((n.get("attributes") or [])[::2], (n.get("attributes") or [])[1::2]))
        return {_norm(attrs.get("aria-label")), _norm(attrs.get("title")), _norm(text(n))}, attrs

    def walk(n, only_button):
        if n.get("nodeType") == 1:
            tag = n.get("nodeName")
            found, attrs = names(n)
            acts = tag == "BUTTON" if only_button else (tag in ("A", "INPUT") or attrs.get("role") == "button")
            if acts and attrs.get("disabled") is None and attrs.get("aria-disabled") != "true" and _is_no_note(found):
                return n
        for child in (n.get("children") or []) + (n.get("shadowRoots") or []):
            hit = walk(child, only_button)
            if hit:
                return hit
        return None
    return walk(node, True) or walk(node, False)


async def click_send(page: Page) -> bool:
    session = await page.context.new_cdp_session(page)
    try:
        root = (await session.send("DOM.getDocument", {"depth": -1, "pierce": True}))["root"]
        button = _find_button(root)
        if not button:
            return False
        quad = (await session.send("DOM.getBoxModel", {"backendNodeId": button["backendNodeId"]}))["model"]["content"]
        await page.mouse.click((quad[0] + quad[4]) / 2, (quad[1] + quad[5]) / 2)
        return True
    finally:
        await session.detach()


async def serve(page: Page, action: dict, status: str, done: set) -> Optional[str]:
    """Does the click the extension asked for, if it is one of the fixed ones. Returns the step clicked."""
    step = await asked(page)
    if not step:
        return None
    if action["kind"] != "connect" or step not in ("connect", "send") or step in done:
        await _done(page)
        log.warning("action %s: click %r asked: ignored", action["id"], step)
        return None
    if status != {"connect": "running_ext", "send": "verifying"}[step]:
        return None   # the status read may be a moment old (sending was just allowed): asked again at the next look
    await _done(page)   # asked once, answered once
    done.add(step)
    try:
        clicked = await (click_connect(page, action) if step == "connect" else click_send(page))
    except PlaywrightError as e:
        log.info("action %s: click %s failed: %s", action["id"], step, e)
        clicked = False
    log.info("action %s: real click %s: %s", action["id"], step, "done" if clicked else "nothing to click")
    return step if clicked else None
