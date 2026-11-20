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

    async def generate_with_images(self, *, images, response_schema, user_prompt=None, description=None, **kwargs):
        pngs = [Path(p).read_bytes() for p in images or [] if p and Path(p).exists()]
        if pngs and blank_picture(pngs[0]):
            # the canvas had not drawn yet (2026-11-19 demo: a white picture under the prompt, and the model rightly said
            # "no points"): no model call; the library refreshes and gets a new challenge
            raise ValueError("challenge picture still blank")
        schema = response_schema.model_json_schema()
        text = await self._reason(pngs, description or "", user_prompt or "", schema)
        data = first_json(text or "")
        if data is None:
            raise ValueError(f"no JSON in the model's answer: {(text or '')[:200]}")
        return response_schema(**data)


def blank_picture(png: bytes) -> bool:
    """The challenge screenshot with nothing below the prompt banner: one flat colour (white) in its lower 3/4."""
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(png)).convert("L")
        w, h = img.size
        lower = img.crop((0, h // 4, w, h))
        lo, hi = lower.getextrema()
        return hi - lo < 12
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

    async def patient_capture(frame, cache_key, crumb_id):
        raw, grid = await capture(frame, cache_key, crumb_id)
        for _ in range(CAPTURE_TRIES):
            if not blank_picture(Path(raw).read_bytes()):
                break
            await page.wait_for_timeout(1000)
            raw, grid = await capture(frame, cache_key, crumb_id)
        return raw, grid
    arm._capture_spatial_mapping = patient_capture
    try:
        if challenge_open:
            await arm.refresh_challenge()
        else:
            await arm.click_checkbox()
        signal = await agent.wait_for_challenge()
    except Exception as e:
        return {"solved": False, "error": f"hcaptcha-challenger: {type(e).__name__}: {str(e)[:160]}"}
    finally:
        try:
            page.remove_listener("response", agent._task_handler)
        except Exception:
            pass
    if signal == ChallengeSignal.SUCCESS:
        return {"solved": True, "how": "hcaptcha-challenger"}
    return {"solved": False, "error": f"hcaptcha-challenger: {getattr(signal, 'value', signal)}"}


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
