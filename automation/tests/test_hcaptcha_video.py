"""hCaptcha's video challenges (worker/hcaptcha_video.py), on a real one saved from the hCaptcha demo on 2026-11-20:
"click the item connected to sports and games", 8 objects fading in and out over 3 s."""
import io
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker import hcaptcha_video as hv  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def frames():
    return hv.decode((FIX / "hcaptcha_video.webm").read_bytes())


def test_the_video_decodes_to_the_challenge_picture_size():
    got = frames()
    assert len(got) == 30 and got[0].shape == (330, 480, 3)   # 90 frames at 30 fps, every 3rd


def test_the_composite_shows_more_than_any_one_frame():
    import numpy as np
    got = frames()
    comp = hv.composite(got).astype(np.int16)
    median = np.median(np.stack(got).astype(np.int16), axis=0)
    def visible(img):   # pixels clearly off the background
        return int((np.abs(img - median).sum(axis=2) > 120).sum())
    assert visible(comp) > 1.3 * max(visible(f.astype(np.int16)) for f in got)


def test_the_video_is_found_where_the_canvas_drew_it():
    import cv2
    shot = cv2.imread(str(FIX / "hcaptcha_video_view.png"))
    assert hv.place(shot, frames()) == (10, 130, 1.0)


def test_a_blank_canvas_gets_the_video_at_the_usual_spot(tmp_path):
    import cv2
    shot = tmp_path / "view.png"
    shutil.copy(FIX / "hcaptcha_video_blank_view.png", shot)
    assert hv.place(cv2.imread(str(shot)), frames()) == (10, 130, 1.0)
    assert hv.paste_into(shot, frames())
    after = cv2.imread(str(shot))
    assert after[130:460, 10:490].std() > 20           # the picture is there now
    assert (after[:100, 200:300] == cv2.imread(str(FIX / "hcaptcha_video_blank_view.png"))[:100, 200:300]).all()  # prompt kept


def test_a_screenshot_of_another_shape_is_left_alone(tmp_path):
    import numpy as np
    import cv2
    shot = tmp_path / "odd.png"
    cv2.imwrite(str(shot), np.full((300, 900, 3), 255, np.uint8))
    assert hv.paste_into(shot, frames()) is False


def test_the_moments_sheet_is_a_png_of_six_frames():
    from PIL import Image
    img = Image.open(io.BytesIO(hv.moments_sheet(frames())))
    assert img.size == (480 * 3 + 8, 330 * 2 + 4)


class Response:
    def __init__(self, url):
        self.url = url


def test_videos_are_kept_per_challenge():
    w, fresh = hv.VideoWatch(), []
    w.on_new_challenge = lambda: fresh.append(1)
    w.on_response(Response("https://api.hcaptcha.com/getcaptcha/abc"))
    w.on_response(Response("https://imgs3.hcaptcha.com/x/1.webm"))
    w.on_response(Response("https://imgs3.hcaptcha.com/x/2.webm"))
    w.on_response(Response("https://imgs3.hcaptcha.com/x/2.webm"))
    assert w.urls == ["https://imgs3.hcaptcha.com/x/1.webm", "https://imgs3.hcaptcha.com/x/2.webm"]
    w.on_response(Response("https://api.hcaptcha.com/getcaptcha/abc"))
    assert w.urls == [] and fresh == [1, 1]
