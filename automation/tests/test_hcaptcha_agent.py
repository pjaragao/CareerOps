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
        "Drag the TWO shapes to their matching outlines": None,
        "Please drag the X so it sits inside both shapes": None,
        "Arraste a peça até o lugar certo": None,
        "": None,
        "Something unexpected": None,
    }
    for prompt, want in cases.items():
        assert ha.quick_type(prompt) == want, prompt
