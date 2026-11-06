"""Reading a job from its link when the page is drawn by JavaScript (printed by Chromium in Gotenberg)."""
from app.services import job_link_service as jls

CUT = "The ideal candidate:\nHas a proven track record of shipping agents\nCanindependentlyownthepathfrominitialspecificationsthrough"
FULL = "The ideal candidate:\nHas a proven track record of shipping agents\nPosition available immediately.\nAPPLY"


def test_looks_cut():
    assert jls.looks_cut(CUT)
    assert not jls.looks_cut(FULL)
    assert not jls.looks_cut("")


def _prints(monkeypatch, tall, normal):
    calls = []

    def fake(url, extra):
        calls.append("tall" if extra else "normal")
        return tall if extra else normal
    monkeypatch.setattr(jls, "_print_text", fake)
    return calls


def test_tall_page_first(monkeypatch):
    # a modal with its own scroll prints whole on one tall page (jahnelgroup.com)
    calls = _prints(monkeypatch, FULL, CUT)
    assert jls._rendered_text("https://x.test/job") == FULL
    assert calls == ["tall"]


def test_normal_print_is_the_fallback(monkeypatch):
    calls = _prints(monkeypatch, "", FULL)
    assert jls._rendered_text("https://x.test/job") == FULL
    assert calls == ["tall", "normal"]
    _prints(monkeypatch, CUT, FULL)
    assert jls._rendered_text("https://x.test/job") == FULL


def test_both_cut_keeps_the_longer(monkeypatch):
    _prints(monkeypatch, CUT, CUT[:60] + "Somewordsruntogetherwithoutanyspacesatall")
    assert jls.looks_cut(jls._rendered_text("https://x.test/job"))
