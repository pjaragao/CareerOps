"""hcaptcha-challenger's model calls answered through CareerOps (worker/hcaptcha_agent.py) and the shim's captcha-reason
route (2026-11-19)."""
import asyncio
import json
import sys
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker import hcaptcha_agent as ha  # noqa: E402
from claude_shim import claude_shim as shim  # noqa: E402


class Point(BaseModel):
    x: int
    y: int


class Answer(BaseModel):
    challenge_prompt: str
    points: list[Point]


def test_first_json_reads_a_fence_or_bare_object():
    assert ha.first_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert ha.first_json('Here: {"a": {"b": 2}} done') == {"a": {"b": 2}}
    assert ha.first_json("no json [1, 2]") is None
    assert ha.first_json('bad {x} then {"ok": true}') == {"ok": True}


def test_provider_sends_images_instructions_and_schema(tmp_path):
    img = tmp_path / "c.png"
    img.write_bytes(b"\x89PNGfake")
    seen = {}

    async def reason(pngs, system, prompt, schema):
        seen.update(pngs=pngs, system=system, prompt=prompt, schema=schema)
        return '```json\n{"challenge_prompt": "click the odd one", "points": [{"x": 410, "y": 360}]}\n```'
    out = asyncio.run(ha.BackendProvider(reason).generate_with_images(
        images=[img, tmp_path / "missing.png"], response_schema=Answer, user_prompt="Solve it", description="You are a solver"))
    assert out.points[0].x == 410 and out.challenge_prompt == "click the odd one"
    assert seen["pngs"] == [b"\x89PNGfake"] and seen["system"] == "You are a solver" and seen["prompt"] == "Solve it"
    assert seen["schema"]["title"] == "Answer"


def test_provider_raises_on_prose_so_the_library_retries():
    async def reason(*a):
        return "There are no shapes in the image."
    try:
        asyncio.run(ha.BackendProvider(reason).generate_with_images(images=[], response_schema=Answer))
    except ValueError as e:
        assert "no JSON" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_shim_tries_gemini_first_then_the_s22(monkeypatch):
    calls = []
    env = {"CAREEROPS_CAPTCHA_GEMINI_KEY": "k", "CAREEROPS_VISION_LOCAL_URL": "http://s22/v1", "CAREEROPS_VISION_LOCAL_KEY": "s"}
    monkeypatch.setattr(shim, "_hermes_env", lambda: env)

    def fake(url, key, body, timeout):
        calls.append((url, body["model"], body.get("reasoning_effort")))
        if "googleapis" in url:
            raise OSError("quota")
        assert body["messages"][0]["content"][0]["type"] == "image_url"   # the S22: picture first, no system message
        assert "You solve" in body["messages"][0]["content"][-1]["text"]
        return '{"points": []}'
    monkeypatch.setattr(shim, "_openai_chat", fake)
    msgs = [{"role": "system", "content": "You solve"},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}},
                                         {"type": "text", "text": "Click it. JSON schema: {}"}]}]
    assert shim.run_captcha_reason(msgs) == '{"points": []}'
    assert calls[0] == (shim.GEMINI_OPENAI, "gemini-2.5-flash", "medium")
    assert calls[1][0] == "http://s22/v1"


def test_shim_says_when_no_model_is_configured(monkeypatch):
    monkeypatch.setattr(shim, "_hermes_env", lambda: {})
    try:
        shim.run_captcha_reason([{"role": "user", "content": "x"}])
    except RuntimeError as e:
        assert "no captcha model configured" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def _png(draw_shapes: bool) -> bytes:
    import io
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (500, 470), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 500, 107), fill=(0, 130, 140))   # the prompt banner
    if draw_shapes:
        d.rectangle((10, 130, 490, 460), fill=(80, 60, 30))
        d.polygon([(100, 300), (140, 380), (60, 380)], fill=(220, 200, 90))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def test_a_challenge_not_drawn_yet_is_blank_and_a_drawn_one_is_not():
    assert ha.blank_picture(_png(False)) is True
    assert ha.blank_picture(_png(True)) is False
    assert ha.blank_picture(b"not a png") is False


def test_a_blank_picture_costs_no_model_call(tmp_path):
    img = tmp_path / "c.png"
    img.write_bytes(_png(False))

    async def reason(*a):
        raise AssertionError("the model must not be asked")
    try:
        asyncio.run(ha.BackendProvider(reason).generate_with_images(images=[img], response_schema=Answer))
    except ValueError as e:
        assert "blank" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_page_count_is_read_again_while_it_says_one():
    seen = iter([1, 1, 2, 2])
    waits = []

    async def count():
        return next(seen)

    async def wait(ms):
        waits.append(ms)
    assert asyncio.run(ha.patient_crumb_count(count, wait)()) == 2
    assert waits == [500, 500]


def test_a_one_page_challenge_stops_after_a_few_seconds():
    calls = []

    async def count():
        calls.append(1)
        return 1

    async def wait(ms):
        pass
    assert asyncio.run(ha.patient_crumb_count(count, wait)()) == 1
    assert len(calls) == ha.CRUMB_TRIES + 1


def test_a_video_challenge_sends_the_grid_and_for_movement_its_moments(tmp_path):
    shot, grid = tmp_path / "c.png", tmp_path / "g.png"
    shot.write_bytes(_png(True))
    grid.write_bytes(_png(True) + b"grid")
    seen = []

    async def reason(pngs, system, prompt, schema):
        seen.append((pngs, prompt))
        return '{"challenge_prompt": "x", "points": []}'
    provider = ha.BackendProvider(reason)
    provider.extra, provider.note = [b"SHEET"], "\n\nanimation"
    asyncio.run(provider.generate_with_images(images=[shot, grid], response_schema=Answer, user_prompt="Tap on the item that spins around"))
    asyncio.run(provider.generate_with_images(images=[shot, grid], response_schema=Answer, user_prompt="Click the item for sports"))
    (moving, prompt1), (still, prompt2) = seen
    assert moving == [grid.read_bytes(), b"SHEET"] and prompt1.endswith("animation")
    assert still == [grid.read_bytes()] and "animation" not in prompt2 and "coordinate grid" in prompt2


def test_click_challenges_get_their_type_without_the_model():
    from hcaptcha_challenger.models import ChallengeTypeEnum as T
    single, multi = T.IMAGE_LABEL_SINGLE_SELECT, T.IMAGE_LABEL_MULTI_SELECT
    cases = {
        "Click the item connected to sports and games": single,
        "Tap on the item that spins around": single,
        "Encontre o objeto que gira em círculo": single,
        "Find the thing that turns in a circle": single,
        "Tap on every object that holds a drink": multi,
        "Please click on the TWO icons that break the pattern": multi,
        "Selecione todos os animais que dormem": multi,
        "Drag the TWO shapes to their matching outlines": T.IMAGE_DRAG_MULTI,
        "Please drag the X so it sits inside both shapes": T.IMAGE_DRAG_SINGLE,
        "Arraste a peça até o lugar certo": T.IMAGE_DRAG_SINGLE,
        "Arraste as DUAS formas para os contornos": T.IMAGE_DRAG_MULTI,
        "": None,
        "Something unexpected": None,
    }
    for prompt, want in cases.items():
        assert ha.quick_type(prompt) == want, prompt


def test_white_label_hcaptcha_frames_count_too():
    assert ha.hcaptcha_frame("https://newassets.hcaptcha.com/captcha/v1/abc/static/hcaptcha.html#frame=challenge&id=1", "challenge")
    assert ha.hcaptcha_frame("https://careers.recruitee.com/captcha/v1/abc/static/hcaptcha.html#frame=checkbox&id=1", "checkbox")
    assert not ha.hcaptcha_frame("https://careers.recruitee.com/captcha/v1/abc/static/hcaptcha.html#frame=checkbox", "challenge")
    assert not ha.hcaptcha_frame("https://www.google.com/recaptcha/api2/anchor", "checkbox")


def test_points_outside_the_challenge_are_caught():
    box = {"x": 100, "y": 21, "width": 500, "height": 470}
    inside, far = Point(x=314, y=380), Point(x=832, y=143)
    assert ha.outside([inside], box) == []
    assert ha.outside([inside, far], box) == [far]


def test_a_checked_point_reasoner_refuses_a_point_off_the_picture():
    class Inner:
        cached = "kept"

        async def __call__(self, **kw):
            return Answer(challenge_prompt="x", points=[Point(x=832, y=143)])

    class Arm:
        async def get_challenge_frame_locator(self):
            class Loc:
                async def bounding_box(self):
                    return {"x": 100, "y": 21, "width": 500, "height": 470}

            class Frame:
                def locator(self, sel):
                    return Loc()
            return Frame()
    checked = ha.CheckedPoints(Inner(), Arm())
    assert checked.cached == "kept"   # the library's other calls on it still work
    try:
        asyncio.run(checked(challenge_screenshot="a", grid_divisions="b"))
    except ValueError as e:
        assert "outside" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_an_example_challenge_sends_the_header_with_its_example(tmp_path):
    shot, grid = tmp_path / "c.png", tmp_path / "g.png"
    shot.write_bytes(_png(True))
    grid.write_bytes(_png(True) + b"grid")
    seen = []

    async def reason(pngs, system, prompt, schema):
        seen.append((pngs, prompt))
        return '{"challenge_prompt": "x", "points": []}'
    provider = ha.BackendProvider(reason)
    provider.example = b"HEADER"
    asyncio.run(provider.generate_with_images(images=[shot, grid], response_schema=Answer,
                                              user_prompt="Find the vehicle with the same number of wheels as the example"))
    asyncio.run(provider.generate_with_images(images=[shot, grid], response_schema=Answer, user_prompt="Click the dog"))
    assert seen[0][0] == [grid.read_bytes(), b"HEADER"] and "example (guide)" in seen[0][1]
    assert seen[1][0] == [grid.read_bytes()]


def test_a_white_picture_inside_the_teal_frame_is_blank():
    fix = Path(__file__).parent / "fixtures"
    assert ha.blank_picture((fix / "hcaptcha_white_with_header.png").read_bytes()) is True    # Recruitee, 2026-11-20
    assert ha.blank_picture((fix / "hcaptcha_video_view.png").read_bytes()) is False           # a drawn one
    assert ha.blank_picture((fix / "hcaptcha_video_blank_view.png").read_bytes()) is True


class _F:
    def __init__(self, url):
        self.url = url


class _Tab:
    def __init__(self, url, frames=()):
        self.url, self.frames = url, [_F(u) for u in frames]


def test_the_solver_finds_the_agents_tab_across_icims_hosts():
    from worker import captcha_server as cs
    cravath = _Tab("https://login.icims.com/signin?x", ["https://newassets.hcaptcha.com/captcha/v1/a#frame=checkbox"])
    lever = _Tab("https://jobs.lever.co/megaport/1/apply")
    assert cs.pick_tab([lever, cravath], "careers-cravath.icims.com") is cravath           # same site, one tab
    inside = _Tab("https://careers-cravath.icims.com/jobs/1", ["https://login.icims.com/signin"])
    assert cs.pick_tab([lever, inside], "login.icims.com") is inside                       # its host on a frame
    bowman = _Tab("https://login.icims.com/signin?y")
    assert cs.pick_tab([cravath, bowman], "careers-cravath.icims.com") is None               # two companies: no guess
    assert cs.pick_tab([lever], "careers-cravath.icims.com") is lever                        # the only one


def test_the_shim_asks_the_careful_model_for_grids(monkeypatch):
    env = {"CAREEROPS_HERMES_URL": "http://lolo", "CAREEROPS_HERMES_KEY": "k", "CAREEROPS_CAPTCHA_NOUS_MODEL": "z-ai/glm-5.3-flash",
           "CAREEROPS_CAPTCHA_NOUS_EFFORT": "low"}
    monkeypatch.setattr(shim, "_hermes_env", lambda: env)
    seen = []
    monkeypatch.setattr(shim, "_openai_chat", lambda url, key, body, timeout: seen.append(
        (body["model"], body["model_options"]["reasoning_effort"])) or "{}")
    shim.run_captcha_reason([{"role": "user", "content": "x"}], "grid")
    shim.run_captcha_reason([{"role": "user", "content": "x"}], "point")
    assert seen == [(shim.CAPTCHA_NOUS_MODEL, "medium"), ("z-ai/glm-5.3-flash", "low")]


def test_the_provider_tells_which_kind_of_question_it_is(tmp_path):
    img = tmp_path / "c.png"
    img.write_bytes(_png(True))
    kinds = []

    async def reason(pngs, system, prompt, schema, kind="other"):
        kinds.append(kind)
        return '{"challenge_prompt": "x", "points": []}'

    class ImageBinaryChallenge(Answer):
        pass

    class ImageAreaSelectChallenge(Answer):
        pass
    p = ha.BackendProvider(reason)
    asyncio.run(p.generate_with_images(images=[img], response_schema=ImageBinaryChallenge))
    asyncio.run(p.generate_with_images(images=[img], response_schema=ImageAreaSelectChallenge))
    assert kinds == ["grid", "point"]


def test_two_icims_companies_are_told_apart_by_their_own_context():
    from worker import captcha_server as cs

    class Ctx:
        def __init__(self):
            self.pages = []
    c1, c2 = Ctx(), Ctx()
    cravath_job, cravath_login = _Tab("https://careers-cravath.icims.com/jobs/3608/login"), _Tab("https://login.icims.com/signin?a")
    rivian_job, rivian_login = _Tab("https://us-careers-rivian.icims.com/jobs/1/login"), _Tab("https://login.icims.com/signin?b")
    for ctx, tabs in ((c1, (cravath_job, cravath_login)), (c2, (rivian_job, rivian_login))):
        for t in tabs:
            t.context = ctx
            ctx.pages.append(t)
    assert cs.pick_tab([rivian_login, cravath_login], "careers-cravath.icims.com") is cravath_login
    assert cs.pick_tab([rivian_login, cravath_login], "us-careers-rivian.icims.com") is rivian_login
