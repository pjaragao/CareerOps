"""hCaptcha with hcaptcha-challenger (2026-11-19; QIN2DIM/hcaptcha-challenger, GPL-3.0, the most used open-source hCaptcha
solver). Our own solver gave up on the 2026 challenges drawn on a canvas ("click on…", "drag…"), the ones iCIMS sites show.
The library reads the challenge type from hCaptcha's own /getcaptcha answer and has a spatial reasoner for each type (points
for area-select, paths for drag-drop) on a coordinate grid.

Its model calls (Gemini by default) go instead through a provider of ours: the backend's /automation/captcha/reason,
which passes them to the host shim (model "captcha-reason"): the worker holds no AI key. The shim picks the model:
Gemini when the runner env has CAREEROPS_CAPTCHA_GEMINI_KEY, else another OpenAI-compatible one, else the S22.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from . import hcaptcha_video

log = logging.getLogger(__name__)

# (images as PNG bytes, system text, user text, JSON schema) -> the model's text, or None
Reasoner = Callable[[List[bytes], str, str, dict], Awaitable[Optional[str]]]

EXECUTION_TIMEOUT = 220   # one challenge: a type check and 2 rounds, 20-60 s a model call through Lolo (solver: 300 s)
RESPONSE_TIMEOUT = 20
CAPTURE_TRIES = 10   # 1 s apart, for a canvas not drawn yet
WORK_DIR = Path(tempfile.gettempdir()) / "hcaptcha-challenger"


def first_json(text: str) -> Optional[dict]:
    """The first JSON object in a model's answer, in a ```json fence or bare."""
    if not text:
        return None
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text)
    for chunk in fenced + [text]:
        start = chunk.find("{")
        while start != -1:
            depth = 0
            for i in range(start, len(chunk)):
                depth += {"{": 1, "}": -1}.get(chunk[i], 0)
                if depth == 0:
                    try:
                        got = json.loads(chunk[start:i + 1])
                        if isinstance(got, dict):
                            return got
                    except ValueError:
                        pass
                    break
            start = chunk.find("{", start + 1)
    return None


class BackendProvider:
    """hcaptcha-challenger's ChatProvider protocol, answered through CareerOps instead of the Gemini SDK."""

    def __init__(self, reason: Reasoner):
        self._reason = reason
        # for a video challenge: its moments sheet, sent after the library's pictures, and a note on how to read them
        self.extra: List[bytes] = []
        self.note = ""
        # for a challenge that compares with an example ("same number of wheels as the example", "icons shown in the guide"):
        # its header, where hCaptcha draws the example; the library photographs only the picture below it
        self.example: Optional[bytes] = None

    async def generate_with_images(self, *, images, response_schema, user_prompt=None, description=None, **kwargs):
        pngs = [Path(p).read_bytes() for p in images or [] if p and Path(p).exists()]
        if pngs and blank_picture(pngs[0]):
            # the canvas had not drawn yet (2026-11-19 demo: a white picture under the prompt, and the model rightly said
            # "no points"): no model call; the library refreshes and gets a new challenge
            raise ValueError("challenge picture still blank")
        schema = response_schema.model_json_schema()
        prompt = user_prompt or ""
        if len(pngs) >= 2:
            # the library sends [challenge picture, the same picture under its coordinate grid]. Lolo takes ~20 s an image
            # (2026-11-20: 1 image 19-24 s, 3 images 57 s, text alone 3 s) and hCaptcha drops a challenge answered too
            # late: the grid one alone carries the challenge and the coordinates
            pngs = pngs[1:]
            prompt += "\n\n(Only the picture with the coordinate grid is attached; it shows the whole challenge.)"
        if self.example and pngs and EXAMPLE_WORDS.search(prompt):
            pngs = pngs + [self.example]
            prompt += ("\n\nThe next picture is the challenge's header: the instruction and the example (guide) it refers to. "
                       "Compare with that example, and answer with coordinates on the grid picture.")
        if self.extra and pngs and hcaptcha_video.MOTION.search(prompt):
            pngs, prompt = pngs + self.extra, prompt + self.note
        text = await self._reason(pngs, description or "", prompt, schema)
        data = first_json(text or "")
        if data is None:
            raise ValueError(f"no JSON in the model's answer: {(text or '')[:200]}")
        return response_schema(**data)


def blank_picture(png: bytes) -> bool:
    """The challenge screenshot with nothing drawn below the prompt banner: the inside of its lower part (borders left out:
    2026-11-20 on Recruitee/Lever the teal frame made a white picture look drawn, and the model "clicked" the example in
    the header) is nearly all one light colour."""
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(png)).convert("L")
        w, h = img.size
        inner = img.crop((int(w * 0.04), int(h * 0.42), int(w * 0.96), int(h * 0.96)))
        hist = inner.histogram()
        total = sum(hist) or 1
        light = sum(hist[235:]) / total
        lo, hi = inner.getextrema()
        return light > 0.985 or hi - lo < 12
    except Exception:
        return False


def available() -> bool:
    try:
        import hcaptcha_challenger  # noqa: F401
        return True
    except Exception as e:   # missing on an image built before the dependency
        log.warning("hcaptcha-challenger unavailable: %s", e)
        return False


async def run(page, reason: Reasoner, challenge_open: bool) -> Dict[str, Any]:
    """Clicks the checkbox (or refreshes an open challenge, so hCaptcha sends a fresh task the library can read) and
    lets the library solve it. {"solved": bool, "how"|"error"}."""
    from hcaptcha_challenger import AgentConfig, AgentV
    from hcaptcha_challenger.models import ChallengeSignal

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    config = AgentConfig(
        GEMINI_API_KEY="via-careerops-backend",   # never used: every reasoner gets our provider below
        cache_dir=WORK_DIR / "cache", challenge_dir=WORK_DIR / "challenge", captcha_response_dir=WORK_DIR / "captcha",
        EXECUTION_TIMEOUT=EXECUTION_TIMEOUT, RESPONSE_TIMEOUT=RESPONSE_TIMEOUT, RETRY_ON_FAILURE=False,
        enable_skills_update=False,
        WAIT_FOR_CHALLENGE_VIEW_TO_RENDER_MS=2500,
    )
    agent = AgentV(page=page, agent_config=config)
    provider = BackendProvider(reason)
    arm = agent.robotic_arm
    for name in ("_challenge_router", "_image_classifier", "_spatial_path_reasoner", "_spatial_point_reasoner"):
        tool = getattr(arm, name, None)
        if tool is not None:
            tool._provider = provider
    # the library takes one screenshot per round; on Chrome under Xvfb the canvas is often not drawn yet (2026-11-19
    # demo: round 2 white every time, even after 5 s). Take it again until there is a picture, up to CAPTURE_TRIES s.
    capture = arm._capture_spatial_mapping
    videos = hcaptcha_video.VideoWatch()

    def new_challenge():
        provider.extra, provider.note = [], ""
    videos.on_new_challenge = new_challenge

    async def patient_capture(frame, cache_key, crumb_id):
        raw, grid = await capture(frame, cache_key, crumb_id)
        provider.example = await header_picture(arm) if EXAMPLE_WORDS.search(arm._challenge_prompt or "") else None
        # a video challenge: the composite of its video in place of whatever the canvas showed, and the grid again
        frames = await videos.frames(page, int(crumb_id) if str(crumb_id).isdigit() else -1)
        if frames:
            try:
                if hcaptcha_video.paste_into(raw, frames):
                    grid = await _regrid(frame, raw, grid, config)
                    provider.extra, provider.note = [hcaptcha_video.moments_sheet(frames)], hcaptcha_video.NOTE
                    log.info("hCaptcha video challenge: composite of %d frames in place", len(frames))
                    return raw, grid
            except Exception as e:
                log.warning("hCaptcha video challenge not used: %s", e)
        provider.extra, provider.note = [], ""
        for _ in range(CAPTURE_TRIES):
            if not blank_picture(Path(raw).read_bytes()):
                break
            await page.wait_for_timeout(1000)
            raw, grid = await capture(frame, cache_key, crumb_id)
        else:
            log.warning("hCaptcha picture blank after %d s (%s); the challenge loaded: %s", CAPTURE_TRIES,
                        (arm._challenge_prompt or "")[:60], await hcaptcha_video.challenge_loads(page))
        return raw, grid
    arm._capture_spatial_mapping = patient_capture
    arm.check_crumb_count = patient_crumb_count(arm.check_crumb_count, page.wait_for_timeout)
    arm.check_challenge_type = quick_check_type(arm, arm.check_challenge_type)
    if getattr(arm, "_spatial_point_reasoner", None) is not None:
        arm._spatial_point_reasoner = CheckedPoints(arm._spatial_point_reasoner, arm)
    any_hcaptcha_frames(arm, page)
    # 2026-11-20, Cravath iCIMS: right tiles, "Verificar", then no /checkcaptcha/ answer reached the library in 20 s.
    # Note hCaptcha's own calls so a failure says whether the answer went out and what came back.
    calls: List[str] = []

    def note(response):
        videos.on_response(response)
        url = response.url
        if "hcaptcha" in url or "/getcaptcha" in url or "/checkcaptcha" in url:   # white-label hosts too
            name = next((k for k in ("getcaptcha", "checkcaptcha", "checksiteconfig") if k in url), None)
            if name:
                calls.append(f"{name} {response.status}")
    page.on("response", note)
    signal = None
    try:
        if not challenge_open and not await _checkbox_visible(page):
            # invisible hCaptcha (Lever: no checkbox, the challenge opens on submit): the library would spend 30 s looking
            # for a checkbox (2026-11-20, Megaport). Wait for the challenge instead.
            challenge_open = await _wait_open_challenge(page, INVISIBLE_WAIT_S)
            if not challenge_open:
                return {"solved": False, "error": "hcaptcha-challenger: invisible hCaptcha and no challenge open: submit first"}
        if challenge_open:
            await arm.refresh_challenge()
        else:
            await arm.click_checkbox()
        signal = await agent.wait_for_challenge()
    except Exception as e:
        return {"solved": False, "error": f"hcaptcha-challenger: {type(e).__name__}: {str(e)[:160]}"}
    finally:
        for handler in (agent._task_handler, note):
            try:
                page.remove_listener("response", handler)
            except Exception:
                pass
    if signal == ChallengeSignal.SUCCESS:
        return {"solved": True, "how": "hcaptcha-challenger"}
    log.warning("hcaptcha-challenger failed (%s); hCaptcha calls: %s", getattr(signal, "value", signal), calls[-8:])
    await _keep_failure_picture(page)
    return {"solved": False, "error": f"hcaptcha-challenger: {getattr(signal, 'value', signal)}; calls: {', '.join(calls[-4:])}"}


async def _regrid(frame, raw: Path, grid: Path, config) -> Path:
    """The library's coordinate grid laid again over a screenshot we changed (as its _capture_spatial_mapping does)."""
    from hcaptcha_challenger.helper import create_coordinate_grid
    import matplotlib.pyplot as plt
    bbox = await frame.locator("//div[@class='challenge-view']").bounding_box()
    result = create_coordinate_grid(
        raw, bbox,
        x_line_space_num=config.coordinate_grid.x_line_space_num,
        y_line_space_num=config.coordinate_grid.y_line_space_num,
        color=config.coordinate_grid.color,
        adaptive_contrast=config.coordinate_grid.adaptive_contrast,
    )
    plt.imsave(str(Path(grid).resolve()), result)
    return grid


async def _keep_failure_picture(page) -> None:
    """The challenge as it was left, for the next look (WORK_DIR/failed-<time>.png, the last 20 kept)."""
    try:
        import time
        for frame in page.frames:
            if "hcaptcha" in frame.url and "frame=challenge" in frame.url:
                el = await frame.query_selector(".challenge-container") or await frame.query_selector("body")
                if el:
                    await el.screenshot(path=str(WORK_DIR / f"failed-{int(time.time())}.png"))
                break
        for old in sorted(WORK_DIR.glob("failed-*.png"))[:-20]:
            old.unlink(missing_ok=True)
    except Exception as e:
        log.info("no failure picture: %s", e)


DRAG_WORDS = re.compile(r"\b(drag|move|slide|arrast\w*|mova|mover|desliz\w*|zieh\w*|verschieb\w*|fais glisser|glisse\w*|"
                        r"d[ée]place\w*|arrastr\w*)\b", re.I)
CLICK_WORDS = re.compile(r"\b(click|tap|select|pick|choose|find|identify|clique|clicar|toque|tocar|selecione|selecionar|escolha|"
                         r"encontre|ache|identifique|haga clic|pulse|seleccione|encuentre|klick\w*|tippe\w*|w[äa]hle\w*|"
                         r"finde\w*|cliquez|touchez|s[ée]lectionnez|trouvez)\b", re.I)
MANY_WORDS = re.compile(r"\b(every|all|each|both|two|three|todos|todas|cada|ambos|ambas|dois|duas|tr[êe]s|alle|jede\w*|beide\w*|"
                        r"zwei|drei|tous|toutes|chaque|deux|trois|cualquier)\b", re.I)


def quick_type(prompt: str):
    """The type of a canvas challenge read from its instruction, for click challenges only: the library would otherwise ask
    the model, 25-30 s through Lolo (2026-11-20 demo), and hCaptcha replaced a challenge answered after ~150 s. Drag
    challenges and anything unclear go to the model as before (None)."""
    from hcaptcha_challenger.models import ChallengeTypeEnum
    text = (prompt or "").strip()
    if not text or DRAG_WORDS.search(text) or not CLICK_WORDS.search(text):
        return None
    if MANY_WORDS.search(text):
        return ChallengeTypeEnum.IMAGE_LABEL_MULTI_SELECT
    return ChallengeTypeEnum.IMAGE_LABEL_SINGLE_SELECT


def quick_check_type(arm, original):
    """arm.check_challenge_type, without the model call when the instruction says plainly what to do."""
    async def check():
        try:
            frame = await arm.get_challenge_frame_locator()
            if await frame.locator("//div[@class='task-image']").count() == 0:
                prompt = (await frame.locator(".prompt-text").first.inner_text(timeout=3000)).strip()
                kind = quick_type(prompt)
                if kind is not None:
                    arm._challenge_prompt = prompt
                    log.info("hCaptcha challenge type from its instruction: %s (%s)", kind.value, prompt[:80])
                    return kind
        except Exception as e:
            log.info("challenge type not read from the page: %s", e)
        return await original()
    return check


def hcaptcha_frame(url: str, which: str) -> bool:
    """hCaptcha's checkbox or challenge frame, on its own host (newassets.hcaptcha.com) or a white-label one (Recruitee
    serves it from its own domain: /captcha/v1/…#frame=…)."""
    return "/captcha/v1/" in (url or "") and f"frame={which}" in url


def any_hcaptcha_frames(arm, page) -> None:
    """The library looks for frames under https://newassets.hcaptcha.com only, so on a white-label page it found none and
    our old solver took over (2026-11-20, Lefebvre on Recruitee). Its selectors and frame lookup, for any host."""
    arm._checkbox_selector = "//iframe[contains(@src,'/captcha/v1/') and contains(@src,'frame=checkbox')]"
    arm._challenge_selector = "//iframe[contains(@src,'/captcha/v1/') and contains(@src,'frame=challenge')]"
    original = arm.get_challenge_frame_locator

    async def find():
        for frame in page.frames:
            if hcaptcha_frame(frame.url, "challenge"):
                try:
                    if await frame.locator("//div[@class='challenge-view']").is_visible():
                        return frame
                except Exception:
                    pass
        return await original()
    arm.get_challenge_frame_locator = find


EXAMPLE_WORDS = re.compile(r"example|guide|sample|reference|exemplo|guia|refer[êe]ncia|amostra|modelo mostrado|beispiel|vorlage|"
                           r"exemple|mod[èe]le|ejemplo|muestra", re.I)


async def view_box(arm) -> Optional[dict]:
    try:
        frame = await arm.get_challenge_frame_locator()
        return await frame.locator("//div[@class='challenge-view']").bounding_box() if frame else None
    except Exception:
        return None


async def header_picture(arm) -> Optional[bytes]:
    try:
        frame = await arm.get_challenge_frame_locator()
        return await frame.locator(".challenge-header").first.screenshot(type="png", timeout=5000) if frame else None
    except Exception as e:
        log.info("challenge header not captured: %s", e)
        return None


def outside(points, box: dict, margin: float = 6) -> list:
    """The points that fall outside the challenge picture (page coordinates, as the library's grid labels them)."""
    return [p for p in points or [] if not (box["x"] - margin <= p.x <= box["x"] + box["width"] + margin
                                             and box["y"] - margin <= p.y <= box["y"] + box["height"] + margin)]


class CheckedPoints:
    """The library's point reasoner, with its answer checked: points outside the challenge (2026-11-20, Cravath: GLM
    answered x=832 on a 500 px challenge) raise, and the library takes a new challenge instead of clicking at random."""

    def __init__(self, inner, arm):
        self._inner, self._arm = inner, arm

    def __getattr__(self, name):
        return getattr(self._inner, name)

    async def __call__(self, *args, **kwargs):
        out = await self._inner(*args, **kwargs)
        box = await view_box(self._arm)
        bad = outside(getattr(out, "points", None), box) if box else []
        if bad:
            raise ValueError(f"points outside the challenge picture: {[(p.x, p.y) for p in bad]}")
        return out


INVISIBLE_WAIT_S = 10


async def _checkbox_visible(page) -> bool:
    """An hCaptcha checkbox frame on screen, at any depth and on any host."""
    for frame in page.frames:
        if hcaptcha_frame(frame.url, "checkbox"):
            try:
                if await (await frame.frame_element()).is_visible():
                    return True
            except Exception:
                pass
    return False


async def _wait_open_challenge(page, seconds: int) -> bool:
    for _ in range(seconds * 2):
        for frame in page.frames:
            if hcaptcha_frame(frame.url, "challenge"):
                try:
                    if await frame.locator("//div[@class='challenge-view']").is_visible():
                        return True
                except Exception:
                    pass
        await page.wait_for_timeout(500)
    return False


CRUMB_TRIES = 8   # 0.5 s apart


def patient_crumb_count(count: Callable[[], Awaitable[int]], wait: Callable[[int], Awaitable[Any]]):
    """The library counts a challenge's pages once, from the page dots, 0.5 s after it opens. Without hCaptcha's own
    payload (its HSW decode fails on these sites) and with the challenge still drawing, it read 1 page on a 2-page grid
    (2026-11-20, Cravath iCIMS: right tiles on page 1, "Next", then no verdict to wait for). Read again for a few seconds
    while it says 1."""
    async def patient() -> int:
        n = await count()
        for _ in range(CRUMB_TRIES):
            if n > 1:
                break
            await wait(500)
            n = await count()
        return n
    return patient


def backend_reasoner(api) -> Reasoner:
    async def reason(pngs: List[bytes], system: str, prompt: str, schema: dict) -> Optional[str]:
        try:
            res = await api.call("POST", "/automation/captcha/reason", timeout=170, json={
                "images_b64": [base64.b64encode(p).decode() for p in pngs][:6],
                "system": system[:20000], "prompt": prompt[:8000], "schema": schema})
        except Exception as e:
            log.warning("captcha reason call failed: %s", e)
            return None
        if not res or res.get("error"):
            log.warning("captcha reason: %s", (res or {}).get("error"))
            return None
        return res.get("text")
    return reason


__all__ = ["run", "available", "backend_reasoner", "BackendProvider", "first_json"]
