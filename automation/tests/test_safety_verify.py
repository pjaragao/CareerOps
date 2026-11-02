import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker import safety  # noqa: E402
from worker.safety import classify  # noqa: E402

L = "https://www.linkedin.com"


@pytest.mark.parametrize("url,code", [
    (f"{L}/checkpoint/challenge/abc", "checkpoint"),
    (f"{L}/checkpoint/lg/login-submit", "checkpoint"),
    (f"{L}/login", "session_expired"),
    (f"{L}/uas/login?session_redirect=x", "session_expired"),
    (f"{L}/authwall?trk=x", "session_expired"),
])
def test_linkedin_addresses_that_stop(url, code):
    assert classify(url) == code


@pytest.mark.parametrize("text,code", [
    ("Your account has been temporarily restricted", "restriction_notice"),
    ("We've restricted your account", "restriction_notice"),
    ("Sua conta foi temporariamente restringida", "restriction_notice"),
    ("Let's do a quick security check", "checkpoint"),
    ("Too many requests", "rate_limited"),
])
def test_linkedin_warnings_at_the_top_of_a_page(text, code):
    assert classify(f"{L}/feed/", "", text) == code


def test_http_status_stops():
    assert classify(f"{L}/feed/", http_status=429) == "rate_limited"
    assert classify(f"{L}/feed/", http_status=999) == "rate_limited"


def test_normal_pages_go_on():
    assert classify(f"{L}/jobs/view/123/", "Analyst", "Apply now. We need a security engineer") is None
    assert classify(f"{L}/in/ana/", "Ana", "Connect Message") is None


def test_a_word_deep_in_an_ad_does_not_stop_everything():
    assert classify(f"{L}/jobs/view/1/", "x", "a" * 2000 + " your account has been restricted") is None


@pytest.mark.parametrize("text,code", [
    ("Please complete the captcha", "captcha"),
    ("Create an account to apply for this job", "account_required"),
    ("Sign in with LinkedIn", "account_required"),
    ("Verify your email to continue", "email_verification"),
])
def test_company_sites_stop_for_you(text, code):
    assert classify("https://boards.greenhouse.io/acme/jobs/1", "", text) == code


def test_a_company_page_with_linkedin_in_the_address_is_not_linkedin():
    assert safety.is_linkedin("https://linkedin.com.evil.example/login") is False
    assert safety.is_linkedin(f"{L}/feed") is True
    assert classify("https://linkedin.com.evil.example/checkpoint/x") is None


def test_challenge_widget():
    assert safety.has_captcha_frame(["https://www.google.com/recaptcha/api2/bframe?x"]) is True
    assert safety.has_captcha_frame(["https://www.google.com/recaptcha/api2/anchor?size=invisible"]) is False


verify = pytest.importorskip("worker.verify")


@pytest.mark.parametrize("text,expected", [("Applied 2 minutes ago", True), ("Candidatou-se há 1 minuto", True), ("Your application was sent", False),
                                           ("Easy Apply", False), ("Apply", False)])
def test_applied(text, expected):
    assert verify.applied_in(text) is expected


def test_comment_must_be_the_approved_text():
    assert verify.comment_in("Ana\nÓtimo   ponto,\nparabéns!\nLike Reply", "Ótimo ponto, parabéns!") is True
    assert verify.comment_in("Ana\nÓtimo ponto", "Ótimo ponto, parabéns!") is False
    assert verify.comment_in("anything", "") is False


@pytest.mark.parametrize("text,expected", [("Thank you for applying!", True), ("Your application has been received", True), ("Recebemos sua candidatura", True),
                                           ("Apply for this job", False), ("Submit application", False)])
def test_external_sent(text, expected):
    assert verify.external_sent_in(text) is expected
