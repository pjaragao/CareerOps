"""The CAPTCHA solver's pure parts (2026-11-19): the numbered grid the vision model reads, and that only an OPEN challenge
counts (Ashby and Greenhouse load an invisible reCAPTCHA on every form)."""
import asyncio
import io
import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright")
PIL = pytest.importorskip("PIL")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker import captcha_solver as cs  # noqa: E402


def test_numbered_grid_keeps_the_picture_and_upscales_small_tiles():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (0, 128, 0)).save(buf, format="JPEG")
    out = Image.open(io.BytesIO(cs.numbered_grid(buf.getvalue(), 3, 3)))
    assert out.size == (300, 300)
    assert out.getpixel((150, 150))[1] > 100   # the middle of a cell is still the picture


class Frame:
    def __init__(self, url, box=None, visible=True, checked="false"):
        self.url, self._box, self._visible, self._checked = url, box, visible, checked

    async def frame_element(self):
        outer = self

        class El:
            async def bounding_box(self):
                return outer._box

            async def is_visible(self):
                return outer._visible
        return El()

    def locator(self, sel):
        outer = self

        class Loc:
            async def get_attribute(self, name, timeout=0):
                return outer._checked
        return Loc()


class Page:
    def __init__(self, frames, tokens=None):
        self.frames, self.tokens, self.url = frames, tokens or {}, "https://jobs.ashbyhq.com/acme/1/application"

    async def evaluate(self, _js, name):
        return self.tokens.get(name, "")


BOX = {"x": 10, "y": 300, "width": 304, "height": 78}


def test_invisible_recaptcha_is_not_a_challenge():
    frames = [Frame("https://www.google.com/recaptcha/api2/anchor?ar=1&k=x&size=invisible", BOX),
              Frame("https://www.google.com/recaptcha/api2/bframe?k=x", {"x": 0, "y": -10000, "width": 400, "height": 580}, visible=False)]
    assert asyncio.run(cs.active_kind(Page(frames))) is None
    assert cs.kind_of(Page(frames)) == "recaptcha"   # the frames are there, nothing to solve


def test_open_challenges_are_seen():
    assert asyncio.run(cs.active_kind(Page([Frame("https://www.google.com/recaptcha/api2/anchor?k=x&size=normal", BOX)]))) == "recaptcha"
    assert asyncio.run(cs.active_kind(Page([Frame("https://www.google.com/recaptcha/api2/anchor?k=x&size=normal", BOX, checked="true")]))) is None
    assert asyncio.run(cs.active_kind(Page([Frame("https://www.google.com/recaptcha/api2/bframe?k=x", {"x": 80, "y": 230, "width": 400, "height": 580})]))) == "recaptcha"
    ts = Frame("https://challenges.cloudflare.com/cdn-cgi/challenge-platform/turnstile/if/ov2/av0/rcv/x", {"x": 10, "y": 10, "width": 300, "height": 65})
    assert asyncio.run(cs.active_kind(Page([ts]))) == "turnstile"
    assert asyncio.run(cs.active_kind(Page([ts], {"cf-turnstile-response": "0." + "x" * 40}))) is None


def test_nothing_to_solve_is_reported_as_passed():
    out = asyncio.run(cs.solve(Page([])))
    assert out["solved"] is True and out["kind"] is None
