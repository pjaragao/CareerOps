"""hCaptcha's 2026 video challenges ("click the item connected to sports and games", "tap on the item that spins around",
"encontre o objeto que gira em círculo"). Found on 2026-11-20 on the hCaptcha demo, the same challenges iCIMS showed:

- the picture is a 3 s .webm (480x330, 30 fps) that hCaptcha decodes off-page and paints on the canvas; there is no
  <video> in the page;
- its objects stay in place but fade in and out, so one screenshot shows only some of them (the right one may be faint);
- on Chrome under Xvfb the canvas often stays white for 10 s or more, though the video itself downloads fine;
- a spinning object can only be told apart over several frames.

So the solver downloads the video itself, decodes it with OpenCV (installed with hcaptcha-challenger) and:
- pastes a composite with every object at its most visible into the challenge screenshot, at the place the video is
  drawn, before the library lays its coordinate grid over it: the clicks keep the library's own mapping;
- gives the model a sheet of 6 moments in time as an extra picture.
"""
from __future__ import annotations

import io
import logging
import re
import tempfile
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

VIEW = (500, 470)   # the challenge view, CSS px
SPOT = (10, 130)    # where the 480x330 video sits in it (demo 2026-11-20: template match 0.93-0.94 at scale 1)
MATCH = 0.6         # below this the screenshot is blank or another picture: fall back to SPOT
STEP = 3            # every 3rd frame is plenty for 3 s at 30 fps

NOTE = ("\n\nThis challenge is a short animation: objects fade in and out and some move. The first picture shows every "
        "object at its most visible, in place; answer with coordinates on it. The last picture shows 6 moments of the "
        "animation in order (t1..t6, left to right, top to bottom), the objects in the same places: use it for anything "
        "about movement (spinning, turning, rotating).")

# an instruction about movement: only then the moments sheet goes along (each picture costs ~20 s through Lolo)
MOTION = re.compile(r"spin|rotat|turn|circle|círculo|circulo|gira|girand|roda|dreh|kreis|tourn", re.I)


class VideoWatch:
    """The challenge videos hCaptcha fetched since its last /getcaptcha (one per page of the challenge)."""

    def __init__(self) -> None:
        self.urls: List[str] = []
        self._decoded: Dict[str, list] = {}
        self.on_new_challenge = None   # called when hCaptcha sends a new challenge

    def on_response(self, response) -> None:
        url = response.url
        if "hcaptcha.com" in url and "/getcaptcha" in url:
            self.urls = []
            if self.on_new_challenge:
                self.on_new_challenge()
        elif url.split("?")[0].endswith(".webm") and url not in self.urls:
            self.urls.append(url)

    async def frames(self, page, page_index: int) -> Optional[list]:
        """The decoded frames of this page's video (the n-th one fetched, else the last), or None."""
        if not self.urls:
            return None
        url = self.urls[page_index] if 0 <= page_index < len(self.urls) else self.urls[-1]
        if url not in self._decoded:
            try:
                res = await page.request.get(url, timeout=20000)
                data = await res.body() if res.ok else b""
            except Exception as e:
                log.info("challenge video not downloaded: %s", e)
                return None
            self._decoded[url] = decode(data) if data else []
        return self._decoded[url] or None


def decode(data: bytes) -> list:
    import cv2
    out = []
    with tempfile.NamedTemporaryFile(suffix=".webm") as f:
        f.write(data)
        f.flush()
        cap = cv2.VideoCapture(f.name)
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if i % STEP == 0:
                out.append(frame)
            i += 1
        cap.release()
    return out


def composite(frames: list):
    """Each pixel from the frame where it is farthest from the video's median: every object at its most visible."""
    import numpy as np
    stack = np.stack(frames).astype(np.int16)
    median = np.median(stack, axis=0)
    pick = np.abs(stack - median).sum(axis=3).argmax(axis=0)
    return np.take_along_axis(stack, pick[None, :, :, None].repeat(3, axis=3), axis=0)[0].astype(np.uint8)


def place(shot, frames) -> Optional[Tuple[int, int, float]]:
    """(x, y, scale) of the video inside the screenshot: found by matching its frames, else the usual spot when the
    screenshot has the challenge view's shape (a blank canvas), else None."""
    import cv2
    H, W = shot.shape[:2]
    h, w = frames[0].shape[:2]
    scale = W / VIEW[0]
    if abs(H / W - VIEW[1] / VIEW[0]) > 0.02 or W < w * scale or H < h * scale:
        return None
    best, at = 0.0, None
    for frame in (frames[-1], frames[len(frames) // 2], frames[0]):
        t = cv2.resize(frame, (round(w * scale), round(h * scale))) if scale != 1 else frame
        res = cv2.matchTemplate(shot, t, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(res)
        if score > best:
            best, at = score, loc
    if best >= MATCH:
        return at[0], at[1], scale
    return round(SPOT[0] * scale), round(SPOT[1] * scale), scale


def paste_into(shot_path, frames) -> bool:
    """Rewrites the challenge screenshot with the composite where the video is drawn. False when it does not fit."""
    import cv2
    shot = cv2.imread(str(shot_path))
    if shot is None or not frames:
        return False
    spot = place(shot, frames)
    if spot is None:
        log.info("challenge video does not fit the screenshot %s", shot.shape)
        return False
    x, y, scale = spot
    comp = composite(frames)
    if scale != 1:
        comp = cv2.resize(comp, (round(comp.shape[1] * scale), round(comp.shape[0] * scale)))
    shot[y:y + comp.shape[0], x:x + comp.shape[1]] = comp
    return bool(cv2.imwrite(str(shot_path), shot))


def moments_sheet(frames: list, n: int = 6) -> bytes:
    """6 moments of the video, 3 by 2, labelled t1..t6, as PNG."""
    from PIL import Image, ImageDraw
    import cv2
    picks = [frames[round(i * (len(frames) - 1) / (n - 1))] for i in range(n)]
    tiles = [Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)) for f in picks]
    w, h = tiles[0].size
    sheet = Image.new("RGB", (w * 3 + 8, h * 2 + 4), "white")
    for i, tile in enumerate(tiles):
        x, y = (i % 3) * (w + 4), (i // 3) * (h + 4)
        sheet.paste(tile, (x, y))
        ImageDraw.Draw(sheet).rectangle((x, y, x + 34, y + 22), fill="black")
        ImageDraw.Draw(sheet).text((x + 6, y + 5), f"t{i + 1}", fill="white")
    out = io.BytesIO()
    sheet.save(out, "PNG")
    return out.getvalue()


__all__ = ["VideoWatch", "decode", "composite", "place", "paste_into", "moments_sheet", "NOTE"]
