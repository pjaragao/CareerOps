"""Networking from the jobs in the system: companies to follow, people to connect with or follow, posts to join and
messages to connections — suggested by the AI, done by the user on LinkedIn.

Nothing here touches LinkedIn: every suggestion is a search link or a text to copy. People found through a search
link are scored by the extension's "⭐ Avaliar pessoas da página" and land in the prospect list as usual.
"""
import json
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from app.services.ai_settings_service import detect_language
from app.services.linkedin_copilot_service import _one, _rows, _skill
from app.services.linkedin_voice_service import VoiceService

SECTIONS = ("companies", "people", "posts", "messages")
_ACTIVE = ("applied", "interviewing", "offer")
# not employers: no company page worth following
_NOT_EMPLOYER = ("remote", "confidential", "confidencial", "hire with near", "insight global", "bairesdev", "turing", "crossover")

LI = "https://www.linkedin.com"


def _search(kind: str, keywords: str, extra: str = "") -> str:
    return f"{LI}/search/results/{kind}/?keywords={quote((keywords or '').strip())}{extra}"


def _jobs(limit: int = 18) -> List[dict]:
    """Applied/interviewing/offer first, then what was touched in the last 45 days."""
    return _rows("""
        SELECT id, status, job_title, company, location, archetype, evaluation_score, language, left(description, 900) AS description, updated_at
          FROM public.job_listings
         WHERE status IN ('applied', 'interviewing', 'offer')
            OR (status NOT IN ('removed', 'rejected') AND COALESCE(updated_at, created_at) > NOW() - INTERVAL '45 days')
         ORDER BY (status IN ('applied', 'interviewing', 'offer')) DESC, COALESCE(updated_at, created_at) DESC
         LIMIT %s
    """, (limit,))


def _company_key(name: Optional[str]) -> str:
    return (name or "").strip().lower()


class NetworkingService:
    @staticmethod
    def latest() -> Optional[dict]:
        row = _one("SELECT * FROM public.linkedin_networking_plans ORDER BY id DESC LIMIT 1")
        if not row:
            return None
        jobs = {j["id"]: j for j in _rows("SELECT id, job_title, company, status FROM public.job_listings WHERE id = ANY(%s)", (row["job_ids"],))}
        return {**row, "jobs": [jobs[i] for i in row["job_ids"] if i in jobs]}

    @staticmethod
    async def build() -> dict:
        jobs = _jobs()
        if not jobs:
            raise RuntimeError("Nenhuma vaga no sistema: importe vagas primeiro")
        companies = {_company_key(j["company"]) for j in jobs if j.get("company")}
        prospects = _rows("SELECT id, name, headline, company, profile_text, market, status, message_sent_at FROM public.linkedin_prospects WHERE status <> 'skipped'")
        known = [p for p in prospects if _company_key(p["company"]) in companies
                 or any(c and c in (p["headline"] or "").lower() for c in companies)]
        connections = [p for p in prospects if p["status"] == "accepted" and not p["message_sent_at"]][:25]
        ai = await _skill("linkedin/networking_plan.md", {"jobs": jobs, "known": known[:30], "connections": connections})
        plan = NetworkingService._enrich(ai, jobs, {p["id"]: p for p in connections})
        row = _one("INSERT INTO public.linkedin_networking_plans (job_ids, plan) VALUES (%s, %s) RETURNING id",
                   ([j["id"] for j in jobs], json.dumps(plan)))
        return NetworkingService.latest() if row else {"plan": plan}

    @staticmethod
    def _enrich(ai: Dict[str, Any], jobs: List[dict], connections: Dict[int, dict]) -> dict:
        """Keeps the well-formed items and adds the LinkedIn links (built here, never by the AI)."""
        job_ids = {j["id"] for j in jobs}
        plan: Dict[str, List[dict]] = {s: [] for s in SECTIONS}
        seen = set()
        for c in ai.get("companies") or []:
            name = (c.get("company") or "").strip()
            if not name or _company_key(name) in seen or any(w in _company_key(name) for w in _NOT_EMPLOYER):
                continue
            seen.add(_company_key(name))
            plan["companies"].append({"company": name, "job_ids": [i for i in c.get("job_ids") or [] if i in job_ids],
                                      "market": c.get("market"), "similar": bool(c.get("similar")), "why": c.get("why"),
                                      "url": _search("companies", name)})
        for p in ai.get("people") or []:
            query = (p.get("search") or f"{p.get('role') or ''} {p.get('company') or ''}").strip()
            if not query:
                continue
            plan["people"].append({"action": "follow" if p.get("action") == "follow" else "connect", "role": p.get("role"),
                                   "company": p.get("company"), "search": query, "market": p.get("market"),
                                   "job_id": p.get("job_id") if p.get("job_id") in job_ids else None, "why": p.get("why"),
                                   "url": _search("people", query)})
        for t in ai.get("posts") or []:
            query = (t.get("search") or t.get("topic") or "").strip()
            if not query:
                continue
            plan["posts"].append({"topic": t.get("topic") or query, "search": query, "market": t.get("market"),
                                  "angle": t.get("angle"), "why": t.get("why"),
                                  "url": _search("content", query, '&sortBy=%22date_posted%22')})
        for m in ai.get("messages") or []:
            try:
                person = connections.get(int(m.get("prospect_id")))
            except (TypeError, ValueError):
                person = None
            text = (m.get("text") or "").strip()
            if not person or not text:
                continue
            plan["messages"].append({"prospect_id": person["id"], "name": person["name"], "headline": person["headline"],
                                     "job_id": m.get("job_id") if m.get("job_id") in job_ids else None,
                                     "text": text, "why": m.get("why")})
        return plan

    @staticmethod
    def mark(plan_id: int, key: str, done: bool) -> Optional[dict]:
        """key = "<section>:<index>". A message ticked off is also recorded as sent (prospect + line of thought)."""
        section, _, index = key.partition(":")
        if section not in SECTIONS or not index.isdigit():
            return None
        row = _one("""
            UPDATE public.linkedin_networking_plans
               SET done = CASE WHEN %s THEN array_append(array_remove(done, %s), %s) ELSE array_remove(done, %s) END
             WHERE id = %s RETURNING *
        """, (done, key, key, key, plan_id))
        if row and done and section == "messages":
            items = row["plan"].get("messages") or []
            person = items[int(index)] if int(index) < len(items) else None
            # already sent from the message window (maybe edited there): keep that text
            if person and not (_one("SELECT message_sent_at FROM public.linkedin_prospects WHERE id = %s", (person["prospect_id"],)) or {}).get("message_sent_at"):
                NetworkingService.message_sent(person["prospect_id"], person["text"])
        return row

    # ── Direct messages to connections ───────────────────────────────────
    @staticmethod
    def _related_jobs(person: dict) -> List[dict]:
        company = _company_key(person.get("company"))
        jobs = _jobs(40)
        same = [j for j in jobs if company and _company_key(j["company"]) == company]
        return (same or [j for j in jobs if j["status"] in _ACTIVE])[:3]

    @staticmethod
    async def draft_message(prospect_id: int, instruction: Optional[str] = None) -> Optional[dict]:
        person = _one("SELECT * FROM public.linkedin_prospects WHERE id = %s", (prospect_id,))
        if not person:
            return None
        lang = "Portuguese" if person.get("market") == "br" else "English" if person.get("market") == "intl" \
            else detect_language(f"{person.get('headline') or ''} {person.get('profile_text') or ''}")
        ai = await _skill("linkedin/prospect_message.md", {
            **{k: person.get(k) for k in ("name", "headline", "company", "reason", "profile_text")},
            "lang_name": lang, "jobs": NetworkingService._related_jobs(person),
            "instruction": (instruction or "")[:1000], "previous_draft": person.get("message_draft"),
        })
        text = (ai.get("message") or "").strip()
        if not text:
            raise RuntimeError("A IA não devolveu a mensagem")
        return _one("UPDATE public.linkedin_prospects SET message_draft = %s, updated_at = NOW() WHERE id = %s RETURNING *",
                    (text, prospect_id)) | {"topic": ai.get("topic"), "stance": ai.get("stance"), "instruction": instruction}

    @staticmethod
    def message_sent(prospect_id: int, text: str, instruction: Optional[str] = None, topic: Optional[str] = None,
                     stance: Optional[str] = None) -> Optional[dict]:
        person = _one("""
            UPDATE public.linkedin_prospects SET message_draft = %s, message_sent_at = NOW(), updated_at = NOW()
             WHERE id = %s RETURNING *
        """, (text, prospect_id))
        if person:
            VoiceService.record("message", text, context=" · ".join(filter(None, [person["name"], person["headline"], person["company"]])),
                                topic=topic, stance=stance, instruction=instruction, ref=f"message:{prospect_id}")
        return person
