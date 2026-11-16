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
