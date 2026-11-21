"""CAPTCHAs on company-site forms (2026-11-19), solved by the machine before anyone is called. Never on LinkedIn: the
LinkedIn browser and lane never come here (account risk).

Layers, cheapest first; each one stops as soon as the challenge is gone:
1. the checkbox (reCAPTCHA v2, hCaptcha, Cloudflare Turnstile) clicked like a person in the real, headful Chrome: often
   enough on its own;
2. reCAPTCHA challenge by audio: Playwright-reCAPTCHA (github.com/Xewdy444/Playwright-reCAPTCHA, MIT), free Google
   speech recognition;
3. image grids (reCAPTCHA when the audio is refused, hCaptcha): the same library's image flow, with its paid CapSolver
   call swapped for a vision model on Lolo (the free Nous model), reached through the backend (`vision`, below).

A miss says so (`solved: False` with `error`) and the caller goes on as before: the live session on noVNC + WhatsApp,
or the action goes to you. Nothing here ever submits a form."""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from playwright.async_api import Error as PlaywrightError, Frame, Page

log = logging.getLogger("worker.captcha")

# (image png bytes, instruction, number of cells) -> cell numbers (1-based) or None when the model gave nothing usable
Vision = Callable[[bytes, str, int], Awaitable[Optional[List[int]]]]

RECAPTCHA_ANCHOR = re.compile(r"/recaptcha/(api2|enterprise)/anchor")
RECAPTCHA_BFRAME = re.compile(r"/recaptcha/(api2|enterprise)/bframe")
# hCaptcha also comes from a platform's own domain (2026-11-19, Recruitee: captcha-assets.recruiteecdn.com/captcha/v1/…)
HCAPTCHA = re.compile(r"(hcaptcha\.com/.*checkbox|/captcha/v1/.*#frame=checkbox)")
HCAPTCHA_CHALLENGE = re.compile(r"(hcaptcha\.com/.*challenge|/captcha/v1/.*#frame=challenge)")
TURNSTILE = re.compile(r"challenges\.cloudflare\.com")
HCAPTCHA_TIMEOUT = 300   # hcaptcha-challenger: 3 model calls of 20-60 s through Lolo, then our own rounds
SOLVE_TIMEOUT = 200   # seconds for one page, all layers together (a vision answer takes 13-25 s; a dynamic grid asks 5-10)


def kind_of(page: Page) -> Optional[str]:
    urls = [f.url or "" for f in page.frames]
    if any(RECAPTCHA_ANCHOR.search(u) or RECAPTCHA_BFRAME.search(u) for u in urls):
        return "recaptcha"
    if any(HCAPTCHA.search(u) or HCAPTCHA_CHALLENGE.search(u) for u in urls):
        return "hcaptcha"
    if any(TURNSTILE.search(u) for u in urls):
        return "turnstile"
    return None


async def _visible(frame: Frame) -> bool:
    """The iframe is on screen at a usable size (Ashby, Greenhouse… load an invisible reCAPTCHA on every form: its frames
    exist with no challenge, hidden or parked off screen)."""
    try:
        el = await frame.frame_element()
        box = await el.bounding_box()
        if not box or box["width"] < 30 or box["height"] < 30 or box["y"] < -500 or box["x"] < -500:
            return False
        return await el.is_visible()
    except PlaywrightError:
        return False


async def _recaptcha_unchecked(frame: Frame) -> bool:
    try:
        return (await frame.locator("#recaptcha-anchor").get_attribute("aria-checked", timeout=1500)) != "true"
    except PlaywrightError:
        return False


async def active_kind(page: Page) -> Optional[str]:
    """The challenge waiting for an answer on this page, if any: a visible unchecked box or an open challenge."""
    for f in page.frames:
        u = f.url or ""
        if RECAPTCHA_BFRAME.search(u) and await _visible(f):
            return "recaptcha"
        if RECAPTCHA_ANCHOR.search(u) and "size=invisible" not in u and await _visible(f) and await _recaptcha_unchecked(f):
            return "recaptcha"
        if HCAPTCHA_CHALLENGE.search(u) and await _visible(f):
            return "hcaptcha"
        if HCAPTCHA.search(u) and await _visible(f) and not await _token(page, "h-captcha-response"):
            return "hcaptcha"
        if TURNSTILE.search(u) and await _visible(f) and not await _token(page, "cf-turnstile-response"):
            return "turnstile"
    return None


async def _token(page: Page, name: str) -> str:
    """The response field the widget fills when it is passed (any of them on the page)."""
    try:
        return await page.evaluate("""(n) => Array.from(document.querySelectorAll(`[name="${n}"]`))
                                             .map(e => e.value || '').find(v => v.length > 20) || ''""", name)
    except PlaywrightError:
        return ""


async def _human_click(page: Page, frame: Frame, x_frac: float = 0.5, y_frac: float = 0.5, x_px: Optional[float] = None) -> bool:
    """A mouse click on a point of an iframe, moved there in steps (a teleporting cursor is what bot checks look for)."""
    try:
        el = await frame.frame_element()
        box = await el.bounding_box()
    except PlaywrightError:
        return False
    if not box or box["width"] < 5:
        return False
    x = box["x"] + (x_px if x_px is not None else box["width"] * x_frac)
    y = box["y"] + box["height"] * y_frac
    await page.mouse.move(x - 120, y - 60)
    await page.mouse.move(x, y, steps=18)
    await page.wait_for_timeout(180)
    await page.mouse.click(x, y, delay=90)
    return True


# ── 3. vision: numbered grid → cells ──

def numbered_grid(png: bytes, rows: int, cols: int) -> bytes:
    """The challenge image with its cells outlined and numbered 1..n, so the model answers with numbers, not positions."""
    from PIL import Image, ImageDraw
    img = Image.open(io.BytesIO(png)).convert("RGB")
    if img.width < 300:
        img = img.resize((img.width * 3, img.height * 3))
    draw = ImageDraw.Draw(img)
    cw, ch = img.width / cols, img.height / rows
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * cw, r * ch
            draw.rectangle([x0, y0, x0 + cw - 1, y0 + ch - 1], outline=(255, 0, 0), width=2)
            n = str(r * cols + c + 1)
            draw.rectangle([x0 + 2, y0 + 2, x0 + 4 + 9 * len(n), y0 + 16], fill=(255, 255, 0))
            draw.text((x0 + 4, y0 + 3), n, fill=(0, 0, 0))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _to_png(raw: bytes) -> bytes:
    from PIL import Image
    out = io.BytesIO()
    Image.open(io.BytesIO(raw)).convert("RGB").save(out, format="PNG")
    return out.getvalue()


# ── 2 + 3. reCAPTCHA through Playwright-reCAPTCHA ──

# The worker's Chrome speaks pt-BR; the library knows European Portuguese only for one label (2026-11-19, seen on
# Google's demo: "Como alternativa, baixe o áudio como MP3"). The audio itself stays English under pt-BR: the library's
# en-US default is right there (a pt-BR transcription gave nonsense and got the IP's audio blocked).
PT_BR_LABELS = {"alternatively_download_audio_as_mp3": ("Como alternativa, baixe o áudio como MP3",),
                # 2026-11-20: pt-BR labels the library does not know yet (it had only "Avançar" and "Pular")
                "next": ("Próximo", "Próxima", "Seguinte"), "skip": ("Ignorar",)}


def _teach_library() -> None:
    from playwright_recaptcha.recaptchav2 import translations
    for key, labels in PT_BR_LABELS.items():
        for label in labels:
            if label not in translations.ELEMENT_TRANSLATIONS[key]:
                translations.ELEMENT_TRANSLATIONS[key] = tuple(translations.ELEMENT_TRANSLATIONS[key]) + (label,)


# "click verify once there are none left" in the languages the worker's Chrome may show
DYNAMIC_GRID = re.compile(r"none left|n[ãa]o houver mais|no quede ninguna|ya no haya|il n'y en a plus|keine mehr|"
                          r"non ce ne sono più|geen meer", re.I)
STATIC_RELOADS = 6


def _recaptcha_solver_class():
    from playwright_recaptcha.recaptchav2 import AsyncSolver
    _teach_library()

    class LoloSolver(AsyncSolver):
        """Playwright-reCAPTCHA with its CapSolver call answered by Lolo's vision model: the library keeps the clicks,
        reloads, "next"/"skip" and token details; the "which cells hold a bus?" answers come from Lolo."""

        def __init__(self, page: Page, vision: Optional[Vision], **kw):
            super().__init__(page, capsolver_api_key="lolo-vision", **kw)
            self._vision = vision

        async def _click_checkbox(self, recaptcha_box):
            # a second pass (images after the audio) finds the challenge already open over the box: no click
            if await _visible(recaptcha_box.bframe_frame):   # never the library's any_challenge_is_visible: it waits 30 s
                return
            return await super()._click_checkbox(recaptcha_box)

        async def _is_dynamic(self, recaptcha_box) -> bool:
            """A grid whose clicked pictures are replaced ("click verify once there are none left") needs a model answer
            per round; a static one ("if there are none, click skip") is answered once."""
            try:
                desc = " ".join(await recaptcha_box.bframe_frame.locator(".rc-imageselect-desc-wrapper").all_inner_texts())
            except PlaywrightError:
                return False
            return bool(DYNAMIC_GRID.search(desc))

        async def _solve_image_challenge(self, recaptcha_box) -> None:
            """Reload (free, ~2 s, no model) until a static grid comes, so the whole challenge is ONE model answer and one
            Verify, inside the challenge's ~2 min life (2026-11-19: dynamic grids took 3-6 answers of 15-60 s and expired)."""
            for _ in range(STATIC_RELOADS):
                if not await self._is_dynamic(recaptcha_box):
                    break
                self._payload_response = None
                try:
                    async with self._page.expect_response(re.compile("/recaptcha/(api2|enterprise)/reload"), timeout=8000) as res:
                        await recaptcha_box.new_challenge_button.click()
                    await res.value
                except PlaywrightError:
                    break
                for _ in range(40):
                    if self._payload_response is not None:
                        break
                    await self._page.wait_for_timeout(200)
                await self._page.wait_for_timeout(600)
            if self._payload_response is None:   # the library reads the challenge picture from this response
                img = await recaptcha_box.image_challenge.locator("img").first.get_attribute("src")
                self._payload_response = await self._page.request.get(img)
            return await super()._solve_image_challenge(recaptcha_box)

        async def _solve_tiles(self, recaptcha_box, indexes):
            """The library asks about each replacement tile alone (one model call per tile, 15-45 s each with the free
            model: a dynamic grid ran out of time). Here: click, wait for the new pictures, then ONE question about the
            whole grid per round, until the model sees no more."""
            tiles = recaptcha_box.tile_selector
            dynamic = False
            for index in indexes:
                tile = tiles.nth(index)
                await tile.click()
                await self._page.wait_for_timeout(250)
                dynamic = dynamic or "rc-imageselect-dynamic-selected" in (await tile.get_attribute("class") or "")
            if not dynamic:
                return
            target = await self._target(recaptcha_box)
            n = await tiles.count()
            side = 4 if n >= 16 else 3
            for _ in range(6):
                await self._wait_new_pictures(recaptcha_box)
                try:
                    shot = await recaptcha_box.bframe_frame.locator(".rc-imageselect-target").first.screenshot(timeout=5000)
                except PlaywrightError:
                    return
                got = await self._vision(numbered_grid(shot, side, side),
                                         f"The picture is split into {n} numbered cells. Which cells contain {target}? "
                                         f"Include a cell when any part of {target} is in it.", n) or []
                if not got:
                    return
                for i in got:
                    if 1 <= i <= n:
                        await tiles.nth(i - 1).click()
                        await self._page.wait_for_timeout(250)

        async def _wait_new_pictures(self, recaptcha_box) -> None:
            """Replaced pictures fade in slowly on purpose: wait until no tile is still being swapped (max 7 s)."""
            for _ in range(28):
                await self._page.wait_for_timeout(250)
                try:
                    busy = await recaptcha_box.bframe_frame.locator(".rc-imageselect-dynamic-selected").count()
                except PlaywrightError:
                    return
                if not busy:
                    await self._page.wait_for_timeout(400)
                    return

        async def _target(self, recaptcha_box) -> str:
            texts = await recaptcha_box.bframe_frame.locator("div").all_inner_texts()
            lines = [t.strip() for t in (texts[0] if texts else "").split("\n") if t.strip()]
            return lines[1] if len(lines) > 1 else (lines[0] if lines else "")

        async def _get_capsolver_response(self, recaptcha_box, image_data: bytes) -> Optional[Dict[str, Any]]:
            if self._vision is None:
                return None
            target = await self._target(recaptcha_box)
            if not target:
                return None
            n = await recaptcha_box.tile_selector.count()
            side = 4 if n >= 16 else 3
            try:
                grid = numbered_grid(image_data, side, side)
            except Exception:   # Google sent something that is not a picture: no answer, the library takes a new challenge
                return {"errorId": 0, "solution": {"objects": []}}
            got = await self._vision(grid, f"The picture is split into {side * side} numbered cells. Which cells contain {target}? "
                                           f"Include a cell when any part of {target} is in it.", side * side)
            return {"errorId": 0, "solution": {"objects": [i - 1 for i in (got or []) if 1 <= i <= side * side]}}

    return LoloSolver


# Google refuses the audio challenge to an IP after a few tries ("your computer or network may be sending automated
# queries"); asking again only makes it worse. Once refused, the audio rests this long and the images go first.
# 2026-11-20: 6 h was too long: the audio passed at 21:21 and 21:24, then rested from an unlogged refusal (a solve its
# caller cancelled) and Dayforce fell to the image grid, which timed out. 2 h, and every refusal is logged.
AUDIO_REST_SECONDS = 2 * 3600
_audio_refused_at = 0.0


async def _fresh_widget_if_refused(page: Page) -> None:
    """A box that shows Google's refusal ("automated queries") stays refused even after a reload of the challenge; a new
    widget (grecaptcha.reset: the form's fields are untouched) gets a fresh image challenge (seen on Google's demo)."""
    bframe = next((f for f in page.frames if RECAPTCHA_BFRAME.search(f.url or "")), None)
    if bframe is None:
        return
    try:
        refused = await bframe.locator(".rc-doscaptcha-header, .rc-doscaptcha-body").first.is_visible()
    except PlaywrightError:
        refused = False
    if not refused:
        return
    await page.evaluate("""() => { try { (window.grecaptcha && window.grecaptcha.enterprise || window.grecaptcha).reset(); }
                                   catch (e) {} }""")
    await page.wait_for_timeout(2000)


async def solve_recaptcha(page: Page, vision: Optional[Vision]) -> Dict[str, Any]:
    global _audio_refused_at
    from playwright_recaptcha.errors import RecaptchaNotFoundError, RecaptchaRateLimitError, RecaptchaSolveError, CapSolverError
    cls = _recaptcha_solver_class()
    tried = []
    audio_ok = time.monotonic() - _audio_refused_at > AUDIO_REST_SECONDS or not _audio_refused_at
    # audio first: Google's speech recognition answers in seconds and is right when the language is (en-US even on a
    # pt-BR page); Lolo's free vision model is right on the grids too, but takes 15-130 s an answer (2026-11-19), so it
    # is the second chance, and the only one while the audio rests after a refusal.
    passes = ([False] if audio_ok else []) + ([True] if vision is not None else [])
    if not audio_ok:
        tried.append(f"audio resting (refused {round((time.monotonic() - _audio_refused_at) / 60)} min ago)")
    for image in passes:
        await _fresh_widget_if_refused(page)
        solver = cls(page, vision, attempts=3)
        try:
            token = await asyncio.wait_for(solver.solve_recaptcha(wait=True, wait_timeout=10, image_challenge=image), timeout=150 if image else 60)
            if token:
                return {"solved": True, "how": "image+vision" if image else "audio"}
        except RecaptchaNotFoundError:
            return {"solved": False, "error": "reCAPTCHA not found on the page"}
        except RecaptchaRateLimitError:
            if not image:
                _audio_refused_at = time.monotonic()
                log.warning("reCAPTCHA audio refused by Google on %s: resting %d min", (page.url or "")[:100], AUDIO_REST_SECONDS // 60)
            tried.append("audio refused (rate limit)" if not image else "rate limit")
        except (RecaptchaSolveError, CapSolverError, asyncio.TimeoutError) as e:
            tried.append(f"{'image' if image else 'audio'}: {type(e).__name__}")
        except Exception as e:   # the library meets a layout it does not know: say so, never guess on
            # 2026-11-20: 0 of 27 in 3 days, most "Timeout waiting for get_by_role("button", name=re.compile(…" cut before
            # the name. Keep which name it waited for and the buttons the challenge really shows, to fix the labels.
            text = str(e)
            wanted = next((l.strip() for l in text.splitlines() if "waiting for" in l), "")
            seen = await _recaptcha_buttons(page)
            tried.append(f"{'image' if image else 'audio'}: {type(e).__name__}: {text.splitlines()[0][:100]}"
                         + (f" | {wanted[:260]}" if wanted else "") + (f" | buttons: {seen}" if seen else ""))
        finally:
            solver.close()
    return {"solved": False, "error": "; ".join(tried) or "not solved"}


async def _recaptcha_buttons(page: Page) -> List[str]:
    """The names of the buttons the reCAPTCHA challenge shows now (aria-label, title or text)."""
    bframe = next((f for f in page.frames if RECAPTCHA_BFRAME.search(f.url or "")), None)
    if bframe is None:
        return []
    try:
        return await bframe.evaluate("""() => [...document.querySelectorAll('button, [role=button], input[type=button], input[type=submit]')]
            .filter(b => b.offsetParent !== null)
            .map(b => (b.getAttribute('aria-label') || b.title || b.innerText || b.value || '').trim()).filter(Boolean)
            .filter((n, i, all) => all.indexOf(n) === i).slice(0, 25)""")
    except Exception:
        return []


# ── hCaptcha ──

async def solve_hcaptcha(page: Page, vision: Optional[Vision], reasoner=None) -> Dict[str, Any]:
    box = next((f for f in page.frames if HCAPTCHA.search(f.url or "")), None)
    # 2026-11-19: hcaptcha-challenger first (it reads the challenge type from hCaptcha and reasons on points and paths);
    # 2026-11-20: white-label frames too (Recruitee): hcaptcha_agent points the library's selectors at any host
    if reasoner is not None and box is not None and not await _token(page, "h-captcha-response"):
        from . import hcaptcha_agent
        if hcaptcha_agent.available():
            ch = next((f for f in page.frames if HCAPTCHA_CHALLENGE.search(f.url or "")), None)
            out = await hcaptcha_agent.run(page, reasoner, challenge_open=bool(ch is not None and await _visible(ch)))
            if out.get("solved") or await _token(page, "h-captcha-response"):
                return {"solved": True, "how": out.get("how") or "hcaptcha-challenger"}
            log.info("hcaptcha-challenger did not pass: %s", out.get("error"))
            # 2026-11-20: the old grid solver below never passed a 2026 challenge after this one failed (0 of 28) and held
            # the solver lock 1-2 min more; its error also hid what this one saw. Its answer is the final one.
            return {"solved": False, "error": out.get("error") or "hcaptcha-challenger did not pass"}
    if box is not None and not await _token(page, "h-captcha-response"):
        await _human_click(page, box, x_px=30)
        for _ in range(16):
            await page.wait_for_timeout(500)
            if await _token(page, "h-captcha-response"):
                return {"solved": True, "how": "checkbox"}
    if vision is None:
        return {"solved": False, "error": "hCaptcha challenge and no vision model"}
    canvas_rounds = 0
    for round_ in range(HCAPTCHA_ROUNDS):
        ch = next((f for f in page.frames if HCAPTCHA_CHALLENGE.search(f.url or "")), None)
        if ch is None:
            break
        try:
            prompt = (await ch.locator(".prompt-text, h2").first.inner_text(timeout=4000)).strip()
            tiles = ch.locator(".task-image")
            n = await tiles.count()
        except PlaywrightError:
            return {"solved": False, "error": "hCaptcha challenge of a kind not handled (no prompt)"}
        if n not in (9, 16):
            # the 2026 challenges are drawn on a canvas (no tiles): a "click on…" one is answered on a numbered grid laid
            # over the picture; a "drag…" one is swapped for another (2026-11-19: Megaport, adesso stopped on them)
            canvas_rounds += 1
            if await _hcaptcha_canvas_round(page, ch, prompt, vision):
                return {"solved": True, "how": f"vision on canvas ({canvas_rounds} rounds)"}
            continue
        side = 3 if n == 9 else 4
        try:
            shot = await ch.locator(".task-grid").first.screenshot(timeout=6000)
        except PlaywrightError:
            return {"solved": False, "error": "hCaptcha grid not visible"}
        got = await vision(numbered_grid(shot, side, side), f"The picture is split into {n} numbered cells. {prompt} "
                                                            f"Answer with the numbers of the matching cells.", n)
        for i in got or []:
            if 1 <= i <= n:
                await tiles.nth(i - 1).click(timeout=4000)
                await page.wait_for_timeout(250)
        try:
            await ch.locator(".button-submit").first.click(timeout=4000)
        except PlaywrightError:
            pass
        await page.wait_for_timeout(2500)
        if await _token(page, "h-captcha-response"):
            return {"solved": True, "how": f"vision ({round_ + 1} rounds)"}
    return {"solved": bool(await _token(page, "h-captcha-response")), "error": f"hCaptcha not passed after {HCAPTCHA_ROUNDS} rounds"}


HCAPTCHA_ROUNDS = 4   # 2026-11-19 demo: the canvas puzzles (semantic, tiny items) beat the E4B; few rounds, then you
HCAPTCHA_DRAG = re.compile(r"\b(drag|arraste|arrastar|arrastre|faites glisser|ziehen)\b", re.I)
CANVAS_SIDE = 4   # cells per side of the grid laid over a canvas challenge


async def _hcaptcha_refresh(ch: Frame, page: Page) -> None:
    for name in ("refresh", "atualizar", "actualizar", "aktualisieren", "actualiser"):
        try:
            btn = ch.get_by_role("button", name=re.compile(name, re.I)).first
            if await btn.count():
                await btn.click(timeout=3000)
                await page.wait_for_timeout(2000)
                return
        except PlaywrightError:
            continue


async def _hcaptcha_canvas_round(page: Page, ch: Frame, prompt: str, vision: Vision) -> bool:
    """One canvas challenge: a drag one is refreshed; a click one gets a numbered grid over its picture, and the centres
    of the cells the model names are clicked, then submit. True when the token is there."""
    if not prompt or HCAPTCHA_DRAG.search(prompt):
        await _hcaptcha_refresh(ch, page)
        return False
    try:
        canvas = ch.locator("canvas").first
        box = await canvas.bounding_box(timeout=4000) if await canvas.count() else None
        if not box:
            await _hcaptcha_refresh(ch, page)
            return False
        shot = await canvas.screenshot(timeout=6000)
    except PlaywrightError:
        await _hcaptcha_refresh(ch, page)
        return False
    n = CANVAS_SIDE * CANVAS_SIDE
    got = await vision(numbered_grid(shot, CANVAS_SIDE, CANVAS_SIDE),
                       f"The picture is split into {n} numbered cells. Task: {prompt} "
                       f"Which cells must be clicked to do the task? Answer with their numbers.", n) or []
    if not got:
        await _hcaptcha_refresh(ch, page)
        return False
    cw, chh = box["width"] / CANVAS_SIDE, box["height"] / CANVAS_SIDE
    for i in got[:6]:
        r, c = divmod(i - 1, CANVAS_SIDE)
        x, y = box["x"] + (c + 0.5) * cw, box["y"] + (r + 0.5) * chh
        await page.mouse.move(x, y, steps=8)
        await page.mouse.click(x, y, delay=80)
        await page.wait_for_timeout(300)
    try:
        await ch.locator(".button-submit").first.click(timeout=4000)
    except PlaywrightError:
        pass
    await page.wait_for_timeout(2500)
    return bool(await _token(page, "h-captcha-response"))


# ── Cloudflare Turnstile (widget or the full-page check) ──

async def solve_turnstile(page: Page) -> Dict[str, Any]:
    for attempt in range(3):
        if await _token(page, "cf-turnstile-response") or await active_kind(page) != "turnstile":
            return {"solved": True, "how": "checkbox" if attempt else "passed on its own"}
        frame = next((f for f in page.frames if TURNSTILE.search(f.url or "")), None)
        if frame is None:
            break
        await page.wait_for_timeout(2500)   # it often passes alone in a real browser: give it the chance first
        if await _token(page, "cf-turnstile-response"):
            return {"solved": True, "how": "passed on its own"}
        await _human_click(page, frame, x_px=30)
        for _ in range(12):
            await page.wait_for_timeout(500)
            if await _token(page, "cf-turnstile-response") or await active_kind(page) != "turnstile":
                return {"solved": True, "how": "checkbox"}
    return {"solved": False, "error": "Turnstile not passed after 3 clicks"}


async def solve(page: Page, vision: Optional[Vision] = None, reasoner=None) -> Dict[str, Any]:
    """Tries every layer on this page. {"solved", "kind", "how"|"error"}; {"solved": True, "kind": None} when there is
    nothing to solve."""
    kind = await active_kind(page)
    if kind is None:
        return {"solved": True, "kind": None, "how": "no open challenge on the page"}
    try:
        if kind == "recaptcha":
            out = await asyncio.wait_for(solve_recaptcha(page, vision), timeout=SOLVE_TIMEOUT)
        elif kind == "hcaptcha":
            out = await asyncio.wait_for(solve_hcaptcha(page, vision, reasoner), timeout=HCAPTCHA_TIMEOUT if reasoner else SOLVE_TIMEOUT)
        else:
            out = await asyncio.wait_for(solve_turnstile(page), timeout=SOLVE_TIMEOUT)
    except asyncio.TimeoutError:
        out = {"solved": False, "error": f"took more than {HCAPTCHA_TIMEOUT if kind == 'hcaptcha' and reasoner else SOLVE_TIMEOUT}s"}
    except PlaywrightError as e:
        out = {"solved": False, "error": f"browser: {str(e)[:200]}"}
    out["kind"] = kind
    log.info("captcha %s on %s: %s", kind, (page.url or "")[:120], out)
    return out


def backend_vision(api) -> Vision:
    """The vision model through the backend (POST /automation/captcha/vision → Lolo): the worker holds no AI key."""
    async def ask(png: bytes, instruction: str, cells: int) -> Optional[List[int]]:
        try:
            res = await api.call("POST", "/automation/captcha/vision", timeout=150,
                                 json={"image_b64": base64.b64encode(png).decode(), "instruction": instruction, "cells": cells})
        except Exception as e:
            log.warning("vision call failed: %s", e)
            return None
        if not res or res.get("error"):
            return None
        return [int(i) for i in res.get("cells") or [] if isinstance(i, (int, float))]
    return ask


__all__ = ["solve", "kind_of", "active_kind", "backend_vision", "numbered_grid"]
