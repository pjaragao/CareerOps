"""One-off: the comments waiting for approval that were drafted before the versions existed get all of them,
and the whole post to read in the approval list (post_full; before, only its first 500 characters).

One AI call per comment (the same call that drafts a new one). The text you see keeps the technical version;
the others become the buttons in the approval list. Run inside the backend container:
    python -m scripts.comment_versions_backfill
"""
import asyncio

from psycopg2.extras import Json

from app.services.automation_service import _one, _rows
from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot


async def main() -> None:
    full = _rows("""UPDATE public.automation_actions a SET payload = a.payload || jsonb_build_object('post_full', left(e.post_text, 6000))
                      FROM public.linkedin_engagement e
                     WHERE a.kind = 'comment' AND a.status = 'proposed' AND a.target_type = 'engagement' AND e.id = a.target_id
                       AND COALESCE(e.post_text, '') <> '' AND NOT a.payload ? 'post_full'
                 RETURNING a.id""")
    print(f"{len(full)} comentário(s) com o post inteiro para ler")
    todo = _rows("""SELECT e.*, a.id AS action_id, a.payload FROM public.automation_actions a
                      JOIN public.linkedin_engagement e ON a.target_type = 'engagement' AND e.id = a.target_id
                     WHERE a.status = 'proposed' AND a.kind = 'comment' AND e.comment_variants IS NULL AND e.post_url IS NOT NULL
                     ORDER BY a.id""")
    print(f"{len(todo)} comentário(s) sem versões")
    for row in todo:
        try:
            item = await Copilot.add_engagement(row["post_text"] or "", row["post_url"], row.get("author_name"), row.get("author_headline"),
                                                regenerate=True)   # no instruction: it would be recorded as yours
        except Exception as e:   # one failure does not stop the rest
            print(f"  ação {row["action_id"]}: falhou ({e})")
            continue
        variants = item.get("comment_variants") or {}
        if not item.get("comment_draft") or not variants:
            print(f"  ação {row["action_id"]}: a IA não devolveu versões")
            continue
        payload = {**(row["payload"] or {}), "text": item["comment_draft"], "variants": variants}
        _one("UPDATE public.automation_actions SET payload = %s, updated_at = NOW() WHERE id = %s AND status = 'proposed' RETURNING id",
             (Json(payload), row["action_id"]))
        print(f"  ação {row["action_id"]}: {len(variants)} versões")


if __name__ == "__main__":
    asyncio.run(main())
