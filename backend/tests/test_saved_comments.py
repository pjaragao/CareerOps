"""Posts saved with the 📌 get a comment drafted by the backend, to approve in the Automação tab."""
import asyncio
from pathlib import Path

import pytest

from app.services import linkedin_copilot_service as svc
from app.services.automation_service import AutomationService as Auto
from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot

URL = "https://www.linkedin.com/feed/update/urn:li:activity:7526000000000000001/"
TEXT = "A long enough post about agents in production and what broke on the way."


async def fake_skill(name, ctx):
    return {"comment": "Bom ponto sobre agentes.", "relevance": 9, "reason": "x", "variants": {"tecnico": "Bom ponto sobre agentes."}}


@pytest.fixture
def inspirations(db, sql):
    """The test schema has no saved themes table: the migration that makes it, and a clean one."""
    from app.db.session import get_db_connection
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute((Path(__file__).parents[1] / "app/db/migrations/migrations_v10.sql").read_text(encoding="utf-8"))
        cur.execute("TRUNCATE public.linkedin_inspirations RESTART IDENTITY")
    conn.commit()
    conn.close()


def test_a_saved_post_becomes_a_comment_to_approve(db, sql, inspirations, monkeypatch):
    monkeypatch.setattr(svc, "_skill", fake_skill)
    sql("INSERT INTO public.linkedin_inspirations (post_url, post_text) VALUES (%s, %s)", (URL, TEXT))
    # a post you already commented on (it has a note) and one without a link are left alone
    sql("INSERT INTO public.linkedin_inspirations (post_url, post_text, note) VALUES (%s, %s, 'Você comentou: ok')", (URL + "x", TEXT))
    sql("INSERT INTO public.linkedin_inspirations (post_text) VALUES (%s)", (TEXT + " other",))
    assert asyncio.run(Copilot.draft_saved_comments()) == 1
    assert asyncio.run(Copilot.draft_saved_comments()) == 0          # drafted once
    Auto.sync_proposals()
    rows = sql("SELECT status, payload FROM public.automation_actions WHERE kind = 'comment'")
    assert [r["status"] for r in rows] == ["proposed"] and rows[0]["payload"]["text"] == "Bom ponto sobre agentes."
