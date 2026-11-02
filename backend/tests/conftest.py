"""Tests run against a throwaway PostgreSQL (TEST_DB_* below), never the real database: conftest refuses any other name."""
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TMP = tempfile.mkdtemp(prefix="careerops-tests-")
os.environ.update({
    "SUPABASE_DB_HOST": os.environ.get("TEST_DB_HOST", "127.0.0.1"),
    "SUPABASE_DB_PORT": os.environ.get("TEST_DB_PORT", "55432"),
    "SUPABASE_DB_NAME": "careerops_pytest",
    "SUPABASE_DB_USER": "postgres",
    "SUPABASE_DB_PASSWORD": os.environ.get("TEST_DB_PASSWORD", "test"),
    "CAREEROPS_APPROVER_TOKEN": "approver-token",
    "CAREEROPS_WORKER_TOKEN": "worker-token",
    "CAREEROPS_BOT_TOKEN": "bot-token",
    "AUTOMATION_ALLOW_FINAL_SUBMIT": "true",
    "CONFIG_DIR": str(ROOT / "config"),
    "OUTPUT_DIR": TMP,
    "AUTH_DIR": TMP,
    "GMAIL_ADDRESS": "",
    "GMAIL_APP_PASSWORD": "",
})

import psycopg2  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(scope="session")
def database():
    admin = psycopg2.connect(host=os.environ["SUPABASE_DB_HOST"], port=os.environ["SUPABASE_DB_PORT"], dbname="postgres",
                             user="postgres", password=os.environ["SUPABASE_DB_PASSWORD"])
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("DROP DATABASE IF EXISTS careerops_pytest WITH (FORCE)")
        cur.execute("CREATE DATABASE careerops_pytest")
    admin.close()
    from app.db.session import get_db_connection
    from app.services import automation_service
    conn = get_db_connection()
    assert conn.get_dsn_parameters()["dbname"] == "careerops_pytest"
    with conn.cursor() as cur:
        cur.execute((Path(__file__).parent / "schema_base.sql").read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    automation_service.ensure_schema()
    yield


TABLES = ("automation_login_links", "bot_notifications", "improvement_suggestions", "automation_events", "automation_runs", "automation_actions", "automation_answers", "job_email_events", "job_searches",
          "job_listings", "linkedin_engagement", "linkedin_prospects", "linkedin_networking_plans")


@pytest.fixture
def db(database, monkeypatch):
    """Clean tables, automation live on the main account, any hour, no gap between writes."""
    from app.db.session import get_db_connection
    from app.services import automation_service, job_search_service
    base = dict(automation_service.config())
    # the reviewer agent calls an AI: its own tests turn it on (test_cv_review.py)
    cfg = {**base, "automation": {**base["automation"], "window": {"start_hour": 0, "end_hour": 24}, "write_gap_minutes": [0, 0]},
           "jobs": {**base["jobs"], "cv_review": "you"}}
    monkeypatch.setattr(automation_service, "config", lambda: cfg)
    monkeypatch.setattr(job_search_service, "config", lambda: cfg)
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join('public.' + t for t in TABLES)} RESTART IDENTITY CASCADE")
        cur.execute("""UPDATE public.automation_state SET mode = 'live', account_kind = 'main', allow_final_submit = TRUE, halted_at = NULL,
                       halted_reason = NULL, halted_lanes = '{}', invites_paused_until = NULL, ramp_step = 2, ramp_step_at = NOW(), ramp_auto = TRUE,
                       confirm_submit_left = 0, review_cv_left = 0, next_write_at = NULL, session_status = 'logged_in'""")
    conn.commit()
    conn.close()
    yield cfg


@pytest.fixture
def sql():
    from app.services.automation_service import _rows
    return _rows


@pytest.fixture
def client(database):
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


APPROVER = {"X-CareerOps-Token": "approver-token"}
WORKER = {"X-CareerOps-Token": "worker-token"}
BOT = {"X-CareerOps-Token": "bot-token"}


@pytest.fixture
def add_job(sql):
    def make(job_id="100", status="discovered", resume="CV", cover="Carta", easy_apply=True, company="Acme", title="Financial Modeling Manager", posted_at=None):
        return sql("""INSERT INTO public.job_listings (linkedin_job_id, url, status, job_title, company, location, description, resume_markdown, cover_letter, easy_apply, posted_at)
                      VALUES (%s, %s, %s, %s, %s, 'Remote', 'Descrição da vaga', %s, %s, %s, %s) RETURNING *""",
                   (job_id, f"https://www.linkedin.com/jobs/view/{job_id}/", status, title, company, resume, cover, easy_apply, posted_at))[0]
    return make
