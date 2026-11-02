from app.core import auth
from app.core.config import settings

from .conftest import APPROVER, WORKER


def test_automation_routes_need_a_token(client):
    assert client.get("/api/automation/status").status_code == 401
    assert client.get("/api/automation/status", headers={"X-CareerOps-Token": "wrong"}).status_code == 401
    assert client.post("/api/automation/actions/1/approve", json={}).status_code == 401
    assert client.post("/api/automation/claim", json={"lane": "ats"}).status_code == 401


def test_worker_token_cannot_approve_or_turn_it_on(client, db):
    assert client.post("/api/automation/actions/1/approve", json={}, headers=WORKER).status_code == 401
    assert client.patch("/api/automation/state", json={"mode": "live"}, headers=WORKER).status_code == 401
    assert client.post("/api/automation/resume", headers=WORKER).status_code == 401
    assert client.get("/api/automation/inbox", headers=WORKER).status_code == 401


def test_approver_token_cannot_report_as_the_worker(client, db):
    assert client.post("/api/automation/claim", json={"lane": "ats"}, headers=APPROVER).status_code == 401
    assert client.post("/api/automation/actions/1/complete", json={"outcome": "executed"}, headers=APPROVER).status_code == 401


def test_status_says_which_role(client, db):
    assert client.get("/api/automation/status", headers=APPROVER).json()["role"] == "approver"
    assert client.get("/api/automation/status", headers=WORKER).json()["role"] == "worker"


def test_a_role_with_no_token_configured_refuses_everything(client, monkeypatch):
    monkeypatch.setattr(settings, "CAREEROPS_APPROVER_TOKEN", "")
    assert client.get("/api/automation/inbox", headers={"X-CareerOps-Token": ""}).status_code == 401


def test_publishing_routes_need_the_approver_token(client, db):
    assert client.post("/api/linkedin-copilot/posts/1/approve", json={}).status_code == 401
    assert client.post("/api/linkedin-copilot/posts/1/publish").status_code == 401


def test_other_sites_are_stopped_even_with_a_token(client, db):
    bad = {**APPROVER, "Origin": "https://evil.example"}
    assert client.get("/api/automation/status", headers=bad).status_code == 403
    assert client.post("/api/linkedin-copilot/posts/1/publish", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.options("/api/automation/status", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"}).status_code == 403


def test_the_app_and_the_extension_are_allowed(client, db):
    for origin in ("http://localhost:5173", "chrome-extension://abcdef"):
        assert client.get("/api/automation/status", headers={**APPROVER, "Origin": origin}).status_code == 200


def test_open_routes_stay_open_from_anywhere(client):
    assert not auth.is_protected("/api/jobs/import-extension")
    assert auth.is_protected("/api/linkedin-copilot/posts/3/publish")
    assert client.get("/health", headers={"Origin": "https://evil.example"}).status_code == 200
