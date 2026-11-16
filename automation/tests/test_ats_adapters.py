"""Deterministic ATS navigation (token plan, phase 2): which adapter, which labels, and that "Apply" is never the final submit."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker import ats_adapters as ad  # noqa: E402


def test_adapter_by_host_and_learned_labels():
    a = ad.adapter_for("https://job-boards.greenhouse.io/acme/jobs/1", {"submit": ["Send it"], "next": []})
    assert a.name == "greenhouse" and a.single_page and a.learned_submit == ["send it"]
    assert ad.adapter_for("https://acme.wd5.myworkdayjobs.com/x").name == "workday"
    assert ad.adapter_for("https://careers.example.com/apply").name == "generic"


def test_apply_is_navigation_never_the_final_submit():
    assert ad._matches("Apply now", ad.NEXT) and not ad._matches("Apply now", ad.SUBMIT)
    assert ad._matches("Submit application", ad.SUBMIT)
    assert ad._matches("Próximo »", ad.NEXT)


def test_labels_match_whole_names_only():
    assert not ad._matches("Submit feedback about this page", ad.SUBMIT)


def test_precheck_decides_closed_and_wrong_pages_without_a_model():
    import asyncio
    from worker.handlers import Runner

    class Page:
        def __init__(self, title, text):
            self.url, self._title, self._text = "https://jobs.example.com/1", title, text

        async def title(self):
            return self._title

        async def evaluate(self, _):
            return self._text

    r = Runner(api=None, browsers=None)
    action = {"lane": "ats", "kind": "apply", "payload": {"title": "Senior Data Scientist", "company": "Acme"}}
    closed = Page("Job", "Sorry, this position has been filled. " + "x " * 500)
    assert asyncio.run(r.precheck(closed, action, "external_form_unfinished"))[0] == "job_closed"
    other = Page("Member of Technical Staff, Finance Research", "Micro1 role about finance research " + "lorem " * 300)
    assert asyncio.run(r.precheck(other, action, "external_form_unfinished"))[0] == "wrong_page"
    right = Page("Apply", "Acme is hiring " + "lorem " * 300)
    assert asyncio.run(r.precheck(right, action, "external_form_unfinished")) is None
    assert asyncio.run(r.precheck(other, action, "account_required")) is None   # a login page carries no job title


def test_the_worker_never_submits_a_step_with_no_fields_filled():
    import asyncio
    from worker.handlers import Runner

    class Api:
        def __init__(self):
            self.posts = []

        async def get(self, path):
            return {"recipe": {}}

        async def post(self, path, body=None):
            self.posts.append(path)
            return {}

    class Page:
        url = "https://jobs.ashbyhq.com/acme/1/application"

        async def evaluate(self, script):
            return '{"sig": "a#1", "filled": 0, "pending": []}' if "getAttribute" in script else []

    api = Api()
    r = Runner(api=api, browsers=None)
    form = {"sig": None, "steps": 0, "since": None, "recipe": None, "labels": []}
    out = asyncio.run(r.drive_form(Page(), {"id": 1, "lane": "ats", "kind": "apply"}, {"allow_final": True}, form))
    assert out is None and not any("complete" in p for p in api.posts)


def test_live_captcha_waits_for_you_then_goes_on():
    import asyncio
    from worker import handlers
    from worker.handlers import Runner

    class Api:
        def __init__(self):
            self.posts = []

        async def post(self, path, body=None):
            self.posts.append((path, (body or {}).get("event")))
            return {}

    class Page:
        url, frames = "https://jobs.x.example/1", []

        def __init__(self):
            self.checks = 0

        async def title(self):
            return "Apply"

        async def evaluate(self, _):
            self.checks += 1
            return "Please verify you are human" if self.checks < 3 else "Application form"

        async def bring_to_front(self):
            pass

        def is_closed(self):
            return False

        async def wait_for_timeout(self, ms):
            pass

    orig = handlers.asyncio.sleep
    handlers.asyncio.sleep = lambda s: orig(0)
    try:
        api = Api()
        r = Runner(api=api, browsers=None)

        async def artifact(page, action_id, name):
            return "shot.png"
        r.artifact = artifact
        assert asyncio.run(r.wait_for_human(Page(), {"id": 7})) is True
        events = [e for _, e in api.posts if e]
        assert events[0] == "captcha_waiting" and events[-1] == "captcha_solved"
    finally:
        handlers.asyncio.sleep = orig
