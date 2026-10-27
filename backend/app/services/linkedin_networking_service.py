"""Networking around the jobs you applied to: who at each hiring company could hire you and what to write to them,
companies to follow, people to follow for the jobs' themes, and the hiring companies' posts to engage with.

Nothing here touches LinkedIn: every suggestion is a profile or search link and a text to copy. The hiring team shown
on a LinkedIn job page ("Meet the hiring team"), read by the extension when the job is imported, gives real people;
without it the plan names the likely roles and links a people search.
"""
import json
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from app.services.ai_settings_service import detect_language
from app.services.linkedin_copilot_service import _clean_profile_url, _name_key, _one, _profile_slug, _rows, _skill
from app.services.linkedin_voice_service import VoiceService

SECTIONS = ("contacts", "companies", "follow", "posts")
_ACTIVE = ("applied", "interviewing", "offer")
# not employers: no company page worth following
_NOT_EMPLOYER = ("remote", "confidential", "confidencial", "hire with near", "insight global", "bairesdev", "turing", "crossover")

LI = "https://www.linkedin.com"


def _search(kind: str, keywords: str, extra: str = "") -> str:
    return f"{LI}/search/results/{kind}/?keywords={quote((keywords or '').strip())}{extra}"


def _company_key(name: Optional[str]) -> str:
    return (name or "").strip().lower()


def _team(job: dict) -> List[dict]:
    """hiring_team_json → [{"name", "title", "link"}] (older imports stored one dict, or nothing)."""
    try:
        raw = json.loads(job.get("hiring_team_json") or "[]")
    except (TypeError, ValueError):
        return []
    people = raw if isinstance(raw, list) else [raw]
    return [{"name": (p.get("name") or "").strip(), "title": (p.get("title") or "").strip(), "link": _clean_profile_url(p.get("link"))}
            for p in people if isinstance(p, dict) and (p.get("name") or "").strip()]


def _lang(job: dict) -> str:
    code = (job.get("language") or "").lower()
    return {"pt": "Portuguese", "en": "English", "es": "Spanish"}.get(code) or detect_language(job.get("description") or job.get("job_title") or "")


def _jobs(limit: int = 18) -> List[dict]:
    """Applied/interviewing/offer first, then what was touched in the last 45 days."""
    jobs = _rows("""
        SELECT id, status, job_title, company, location, archetype, evaluation_score, language, hiring_team_json,
               left(description, 900) AS description, updated_at
          FROM public.job_listings
         WHERE status IN ('applied', 'interviewing', 'offer')
            OR (status NOT IN ('removed', 'rejected') AND COALESCE(updated_at, created_at) > NOW() - INTERVAL '45 days')
         ORDER BY (status IN ('applied', 'interviewing', 'offer')) DESC, COALESCE(updated_at, created_at) DESC
         LIMIT %s
    """, (limit,))
    for j in jobs:
        j["hiring_team"] = _team(j)
        j["lang_name"] = _lang(j)
    return jobs


def _works_at(person: dict, company: Optional[str]) -> bool:
    key = _company_key(company)
    return bool(key) and (_company_key(person.get("company")) == key or key in (person.get("headline") or "").lower())


def _tied(person: dict, jobs: List[dict]) -> List[dict]:
    """The jobs at this person's company: only the ones you pursue when there are any, one per title."""
    at = [j for j in jobs if _works_at(person, j["company"])]
    at = [j for j in at if j["status"] in _ACTIVE] or at
    seen, out = set(), []
    for j in at:
        if (j["job_title"], _company_key(j["company"])) not in seen:
            seen.add((j["job_title"], _company_key(j["company"])))
            out.append(j)
    return out[:3]


def related_jobs(person: dict) -> List[dict]:
    return _tied(person, _jobs(40))


class NetworkingService:
    # ── Hiring team (from the job page) ──────────────────────────────────
    @staticmethod
    def save_hiring_team(linkedin_job_id: Optional[str], url: Optional[str], team: Any) -> int:
        """Stores the hiring team read on the job page and adds each person to the prospects, tied to the company."""
        people = team if isinstance(team, list) else [team] if isinstance(team, dict) else []
        people = [{"name": (p.get("name") or "").strip()[:120], "title": (p.get("title") or "").strip()[:300],
                   "link": _clean_profile_url(p.get("link"))} for p in people if isinstance(p, dict) and (p.get("name") or "").strip()]
        if not people:
            return 0
        job = _one("""
            UPDATE public.job_listings SET hiring_team_json = %s
             WHERE linkedin_job_id = %s OR url = %s RETURNING id, job_title, company, language, description
        """, (json.dumps(people, ensure_ascii=False), linkedin_job_id, url))
        if not job:
            return 0
        market = "br" if _lang(job) == "Portuguese" else "intl"
        for p in people:
            if not p["link"] or "/in/" not in p["link"]:
                continue
            _one("""
                INSERT INTO public.linkedin_prospects (profile_url, name, headline, company, profile_text, market, segment, fit, reason, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'hiring_team', 90, %s, 'to_contact')
                ON CONFLICT (profile_url) WHERE profile_url IS NOT NULL
                DO UPDATE SET company = COALESCE(linkedin_prospects.company, EXCLUDED.company),
                              segment = 'hiring_team', fit = GREATEST(COALESCE(linkedin_prospects.fit, 0), 90),
                              reason = EXCLUDED.reason, updated_at = NOW()
                RETURNING id
            """, (p["link"], p["name"], p["title"] or None, job["company"], p["title"] or p["name"], market,
                  f"Equipe de contratação da vaga {job['job_title']}"))
        return len(people)

    # ── Plan ─────────────────────────────────────────────────────────────
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
        if not any(j["status"] in _ACTIVE for j in jobs):
            raise RuntimeError("Nenhuma vaga em andamento: marque como aplicada as vagas em que você se candidatou")
        companies = {_company_key(j["company"]) for j in jobs if j.get("company")}
        prospects = _rows("SELECT id, profile_url, name, headline, company, status FROM public.linkedin_prospects WHERE status <> 'skipped'")
        known = [p for p in prospects if any(_works_at(p, c) for c in companies)]
        ai = await _skill("linkedin/networking_plan.md", {"jobs": jobs, "known": known[:30]})
        plan = NetworkingService._enrich(ai, jobs, prospects)
        _one("INSERT INTO public.linkedin_networking_plans (job_ids, plan) VALUES (%s, %s) RETURNING id",
             ([j["id"] for j in jobs], json.dumps(plan, ensure_ascii=False)))
        return NetworkingService.latest()

    @staticmethod
    def _enrich(ai: Dict[str, Any], jobs: List[dict], prospects: List[dict]) -> dict:
        """Keeps the well-formed items, ties named contacts to real profiles and adds the LinkedIn links (built here,
        never by the AI)."""
        by_id = {j["id"]: j for j in jobs}
        plan: Dict[str, List[dict]] = {s: [] for s in SECTIONS}

        def person_for(name: str, job: dict) -> Optional[dict]:
            """A named contact → the hiring-team member or prospect with that name (profile link, prospect id)."""
            key = _name_key(name)
            if not key:
                return None
            member = next((h for h in job["hiring_team"] if _name_key(h["name"]) == key), None)
            slug = _profile_slug(member["link"]) if member and member.get("link") else ""
            prospect = next((p for p in prospects if (slug and _profile_slug(p["profile_url"]) == slug)
                             or (_name_key(p["name"]) == key and _works_at(p, job["company"]))), None)
            if not member and not prospect:
                return None
            return {"profile_url": (member or {}).get("link") or (prospect or {}).get("profile_url"),
                    "prospect_id": (prospect or {}).get("id"), "status": (prospect or {}).get("status"),
                    "title": (member or {}).get("title") or (prospect or {}).get("headline")}

        for c in ai.get("contacts") or []:
            job = by_id.get(c.get("job_id"))
            note, message = (c.get("note") or "").strip(), (c.get("message") or "").strip()
            if not job or not (note or message):
                continue
            name = (c.get("name") or "").strip()
            found = person_for(name, job) if name else None
            if name and not found:   # a name the AI made up: keep the role, drop the name
                name = ""
            query = (c.get("search") or f"{c.get('role') or ''} {job['company'] or ''}").strip()
            plan["contacts"].append({
                "job_id": job["id"], "company": job["company"], "name": name or None, "role": c.get("role") or (found or {}).get("title"),
                "why": c.get("why"), "note": note[:300], "message": message,
                "profile_url": (found or {}).get("profile_url"), "prospect_id": (found or {}).get("prospect_id"),
                "prospect_status": (found or {}).get("status"),
                "search": None if found else query, "url": (found or {}).get("profile_url") or _search("people", query),
            })
        seen = set()
        for c in ai.get("companies") or []:
            name = (c.get("company") or "").strip()
            if not name or _company_key(name) in seen or any(w in _company_key(name) for w in _NOT_EMPLOYER):
                continue
            seen.add(_company_key(name))
            plan["companies"].append({"company": name, "job_ids": [i for i in c.get("job_ids") or [] if i in by_id],
                                      "market": c.get("market"), "similar": bool(c.get("similar")), "why": c.get("why"),
                                      "url": _search("companies", name)})
        for p in ai.get("follow") or []:
            query = (p.get("search") or p.get("role") or "").strip()
            if query:
                plan["follow"].append({"role": p.get("role"), "search": query, "market": p.get("market"),
                                       "job_id": p.get("job_id") if p.get("job_id") in by_id else None, "why": p.get("why"),
                                       "url": _search("people", query)})
        for t in ai.get("posts") or []:
            job = by_id.get(t.get("job_id")) or next((j for j in jobs if _company_key(j["company"]) == _company_key(t.get("company"))), None)
            company = (job or {}).get("company") or (t.get("company") or "").strip()
            if not company or any(w in _company_key(company) for w in _NOT_EMPLOYER):
                continue
            # the hiring team's own activity first: their posts are where a comment is seen by who hires
            people = [{"name": h["name"], "url": f"{h['link']}/recent-activity/all/"} for h in (job or {}).get("hiring_team", []) if h.get("link")]
            people += [{"name": c["name"], "url": f"{c['profile_url']}/recent-activity/all/"} for c in plan["contacts"]
                       if c["company"] == company and c["profile_url"] and c["name"] not in {p["name"] for p in people}]
            plan["posts"].append({"company": company, "job_id": (job or {}).get("id"), "angle": t.get("angle"), "why": t.get("why"),
                                  "people": people,
                                  "url": _search("content", f'"{company}"', '&sortBy=%22date_posted%22')})
        return plan

    @staticmethod
    def mark(plan_id: int, key: str, done: bool) -> Optional[dict]:
        """key = "<section>:<index>"."""
        section, _, index = key.partition(":")
        if section not in SECTIONS or not index.isdigit():
            return None
        return _one("""
            UPDATE public.linkedin_networking_plans
               SET done = CASE WHEN %s THEN array_append(array_remove(done, %s), %s) ELSE array_remove(done, %s) END
             WHERE id = %s RETURNING *
        """, (done, key, key, key, plan_id))

    # ── Messages to people tied to a job ─────────────────────────────────
    @staticmethod
    async def draft_message(prospect_id: int, instruction: Optional[str] = None) -> Optional[dict]:
        person = _one("SELECT * FROM public.linkedin_prospects WHERE id = %s", (prospect_id,))
        if not person:
            return None
        jobs = related_jobs(person)
        if not jobs:
            raise RuntimeError("Esta pessoa não está ligada a nenhuma vaga do sistema")
        lang = jobs[0]["lang_name"]
        ai = await _skill("linkedin/prospect_message.md", {
            **{k: person.get(k) for k in ("name", "headline", "company", "reason", "profile_text")},
            "lang_name": lang, "jobs": jobs, "connected": person["status"] in ("accepted", "replied"),
            "instruction": (instruction or "")[:1000], "previous_draft": person.get("message_draft"),
        })
        text = (ai.get("message") or "").strip()
        if not text:
            raise RuntimeError("A IA não devolveu a mensagem")
        if person["status"] not in ("accepted", "replied"):
            text = text[:300]   # a connection-request note
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

    @staticmethod
    def job_ties(prospects: List[dict]) -> Dict[int, List[dict]]:
        """prospect id → the jobs at their company (for the Mensagem button)."""
        jobs = _jobs(40)
        out: Dict[int, List[dict]] = {}
        for p in prospects:
            tied = [{"id": j["id"], "job_title": j["job_title"], "company": j["company"], "status": j["status"]} for j in _tied(p, jobs)]
            if tied:
                out[p["id"]] = tied
        return out
