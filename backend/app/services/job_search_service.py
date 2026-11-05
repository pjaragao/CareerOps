"""The job search engine: the groups of titles and the places to look (also what the "Pesquisar vagas" tab shows), the daily
rounds of the automatic search, and the triage of what they find. A job found stays 'discovered' until you approve it:
no CV or cover letter is generated before that."""
import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urlencode

from psycopg2.extras import Json

from app.core.config import settings
from app.services.automation_service import AutomationService, _one, _rows, config
from app.services.skill_service import SkillService

log = logging.getLogger("job_search")

# Job titles that match the profile (modelagem, dados, IA, infraestrutura), most fitting group first
GROUPS = [
    {"id": "financas", "label": "Modelagem e finanças", "remoteOkTag": "finance",
     "titles": ["Financial Modeling Analyst", "Financial Modeling Manager", "Project Finance Analyst", "Project Finance Associate",
                "Infrastructure Finance Analyst", "FP&A Manager", "Senior FP&A Analyst", "Valuation Analyst",
                "Financial Analyst Renewable Energy", "Pricing Manager"],
     "combo": '("financial modeling" OR "project finance" OR "infrastructure finance" OR "FP&A")'},
    {"id": "dados", "label": "Dados e forecasting", "remoteOkTag": "data-science",
     "titles": ["Forecasting Analyst", "Demand Forecasting Data Scientist", "Data Scientist Time Series", "Quantitative Analyst Energy",
                "Analytics Engineer", "Senior Data Analyst Finance", "Business Intelligence Manager"],
     "combo": '("forecasting" OR "time series") AND ("data scientist" OR "analyst")'},
    {"id": "ia", "label": "IA aplicada", "remoteOkTag": "ai",
     "titles": ["AI Engineer", "Applied AI Engineer", "LLM Engineer", "AI Agent Developer", "AI Solutions Engineer",
                "Forward Deployed Engineer", "AI Automation Engineer", "Finance Automation Lead", "Solutions Engineer Fintech"],
     "combo": '("AI engineer" OR "LLM engineer" OR "applied AI" OR "AI automation")'},
    {"id": "nicho", "label": "Nicho: infraestrutura", "remoteOkTag": "finance",
     "titles": ["Utility Rate Analyst", "Water Infrastructure Financial Analyst", "Infrastructure Advisory Consultant",
                "PPP Financial Advisor", "Concessions Financial Advisor", "Climate Finance Analyst", "Sustainable Infrastructure Analyst",
                "Development Finance Consultant", "Energy Transition Financial Analyst"],
     "combo": '("utility rate" OR "PPP" OR "concessions" OR "infrastructure advisory" OR "climate finance")'},
]

# Where to look: remote jobs that accept someone living in Brazil pass the eligibility check; visa modes are for moving
MODES = [
    {"id": "remoto-br", "label": "Remoto aceitando Brasil (EUA e Europa)", "location": "Brazil", "remote": True, "extra": "",
     "hint": 'Localização "Brazil" + remoto: o LinkedIn mostra vagas de empresas dos EUA e da Europa abertas a quem mora aqui. Com "United States" quase tudo exige autorização de trabalho.',
     "atsTerms": '("LATAM" OR "Latin America" OR "Brazil" OR "anywhere" OR "worldwide")'},
    {"id": "remoto-latam", "label": "Remoto LATAM / contractor", "location": "Latin America", "remote": True, "extra": "",
     "hint": "Vagas com fuso das Américas, muitas como contractor ou via EOR (Deel, Remote.com). É o caminho mais comum para empresas europeias contratarem do Brasil.",
     "atsTerms": '("LATAM" OR "Latin America" OR "contractor" OR "Deel" OR "EOR")'},
    {"id": "visto-eu", "label": "Mudança para a Europa com visto", "location": "European Union", "remote": False, "extra": ' AND ("visa sponsorship" OR relocation)',
     "hint": "Presencial ou híbrido com patrocínio de visto ou relocation. Cidades-alvo: Lisboa, Madri, Amsterdã, Berlim, Dublin.",
     "atsTerms": '("visa sponsorship" OR "relocation") (Lisbon OR Madrid OR Amsterdam OR Berlin OR Dublin)'},
    {"id": "visto-us", "label": "Mudança para os EUA com visto", "location": "United States", "remote": False, "extra": ' AND "visa sponsorship"',
     "hint": "Poucas vagas e H-1B é por sorteio. Vale para consultorias grandes de infraestrutura; para EB-2 NIW, fale com um advogado.",
     "atsTerms": '("visa sponsorship" OR "H-1B")'},
]

# Every day the first group of each kind; in rotation, the visa modes take the place of the last two (see round_for)
DAILY = [("financas", "remoto-br"), ("nicho", "remoto-br"), ("financas", "remoto-latam"), ("nicho", "remoto-latam"), ("dados", "remoto-br"), ("ia", "remoto-br")]
ROTATION = {1: [("financas", "visto-eu"), ("nicho", "visto-eu")], 3: [("financas", "visto-us"), ("financas", "visto-eu")]}
RECENT_SECONDS = 172800   # f_TPR: the last 48 hours, as in the "Só recentes" switch of the tab

_AGO = re.compile(r"(\d+)\s*(min|minute|minuto|hour|hora|day|dia|week|semana|month|m[eê]s|mes)", re.I)


def parse_posted(text: Optional[str], at: Optional[datetime] = None) -> Optional[datetime]:
    """'2 hours ago', 'há 3 horas', 'Reposted 1 day ago', 'just now' → when it was posted. None when it doesn't say."""
    at = at or datetime.now(timezone.utc)
    t = (text or "").lower()
    if re.search(r"just now|agora mesmo|moments? ago", t):
        return at
    m = _AGO.search(t)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    if unit.startswith(("min",)):
        return at - timedelta(minutes=n)
    if unit.startswith(("hour", "hora")):
        return at - timedelta(hours=n)
    if unit.startswith(("day", "dia")):
        return at - timedelta(days=n)
    if unit.startswith(("week", "semana")):
        return at - timedelta(weeks=n)
    return at - timedelta(days=30 * n)


class JobSearchService:
    @staticmethod
    def catalog() -> dict:
        return {"groups": GROUPS, "modes": MODES, "recent_seconds": RECENT_SECONDS}

    @staticmethod
    def ensure_seeds() -> None:
        """One row per group × mode. Existing rows keep whatever you changed (enabled)."""
        for group in GROUPS:
            for mode in MODES:
                _rows("""
                    INSERT INTO public.job_searches (slug, name, group_id, mode_id, keywords, location, filters)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (slug) DO NOTHING""",
                      (f"{group['id']}:{mode['id']}", f"{group['label']} · {mode['label']}", group["id"], mode["id"],
                       group["combo"] + mode["extra"], mode["location"], Json({"remote": mode["remote"]})))

    @staticmethod
    def list_searches() -> List[dict]:
        return _rows("SELECT * FROM public.job_searches ORDER BY group_id, mode_id")

    @staticmethod
    def set_enabled(search_id: int, enabled: bool) -> Optional[dict]:
        return _one("UPDATE public.job_searches SET enabled = %s WHERE id = %s RETURNING *", (enabled, search_id))

    @staticmethod
    def linkedin_url(search: dict) -> str:
        """Newest first, last 48 hours: the same address the tab opens (LinkedIn's search page since late 2026)."""
        params = {"keywords": search["keywords"], "location": search["location"], "sortBy": "DD", "f_TPR": f"r{RECENT_SECONDS}"}
        if (search.get("filters") or {}).get("remote"):
            params["f_WT"] = "2"
        return f"https://www.linkedin.com/jobs/search-results/?{urlencode(params)}"   # /jobs/search/ redirects there, adding a salary filter

    @staticmethod
    def round_for(day: date) -> List[dict]:
        """The searches of one round on this day (at most 6)."""
        pairs = DAILY[:4] + ROTATION.get(day.toordinal() % 4, DAILY[4:])
        slugs = [f"{g}:{m}" for g, m in pairs]
        rows = {r["slug"]: r for r in _rows("SELECT * FROM public.job_searches WHERE slug = ANY(%s) AND enabled", (slugs,))}
        return [rows[s] for s in slugs if s in rows]

    @staticmethod
    def next_follow_scan() -> Optional[dict]:
        """A company or a role of the Networking plan not looked up yet: follow suggestions come from what the search shows."""
        plan = _one("SELECT plan FROM public.linkedin_networking_plans ORDER BY id DESC LIMIT 1")
        if not plan:
            return None
        items = [{"key": f"company:{(c.get('company') or '').lower()}", "mode": "company", "name": c.get("company"), "url": c.get("url"),
                  "why": c.get("why"), "market": c.get("market")} for c in plan["plan"].get("companies") or [] if not c.get("similar")]
        items += [{"key": f"people:{(p.get('search') or '').lower()}", "mode": "people", "name": p.get("role") or p.get("search"), "url": p.get("url"),
                   "why": p.get("why"), "market": p.get("market")} for p in plan["plan"].get("follow") or []]
        done = {r["idempotency_key"] for r in _rows("SELECT idempotency_key FROM public.automation_actions WHERE kind = 'follow_scan'")}
        return next((i for i in items if i["url"] and f"follow_scan:{i['key']}" not in done), None)

    # ── What the search found ────────────────────────────────────────────
    @staticmethod
    def unseen(ids: List[str]) -> dict:
        """Which of these LinkedIn job ids are new (rejected and archived ones never come back), and how many ads may still be read today."""
        known = {r["linkedin_job_id"] for r in _rows("SELECT linkedin_job_id FROM public.job_listings WHERE linkedin_job_id = ANY(%s)", (ids,))}
        return {"unseen": [i for i in ids if i not in known], "budget": AutomationService.job_read_budget()}

    @staticmethod
    def add_discovered(jobs: List[dict], search_slug: Optional[str]) -> int:
        """New jobs enter as 'discovered'. An id already here is left alone, whatever its status."""
        added = 0
        for j in jobs:
            job_id = str(j.get("linkedin_job_id") or "").strip()
            if not job_id or not (j.get("description") or "").strip():
                continue
            row = _one("""
                INSERT INTO public.job_listings (linkedin_job_id, url, job_title, company, location, description, status, scraped_at,
                                                 easy_apply, posted_at, search_slug)
                VALUES (%s, %s, %s, %s, %s, %s, 'discovered', NOW(), %s, %s, %s)
                ON CONFLICT DO NOTHING RETURNING id""",
                       (job_id, f"https://www.linkedin.com/jobs/view/{job_id}/", j.get("title") or "", j.get("company") or "", j.get("location") or "",
                        j["description"], bool(j.get("easy_apply")), parse_posted(j.get("posted")), search_slug))
            added += bool(row)
        if search_slug:
            _rows("UPDATE public.job_searches SET last_run_at = NOW(), jobs_found = jobs_found + %s WHERE slug = %s", (added, search_slug))
        return added

    @staticmethod
    def add_saved(jobs: List[dict], ids: List[str]) -> dict:
        """Your saved jobs, read by the server: a new one enters as 'new' (like the import button), so it goes to the approval
        list with its CV and cover letter; one the search found and nobody decided yet ('discovered') moves there too. What
        you already moved on (applied, archived, rejected...) stays as it is: saving is no reason to bring it back."""
        added = 0
        for j in jobs:
            job_id = str(j.get("linkedin_job_id") or "").strip()
            if not job_id or not (j.get("description") or "").strip():
                continue
            row = _one("""
                INSERT INTO public.job_listings (linkedin_job_id, url, job_title, company, location, description, status, scraped_at,
                                                 easy_apply, posted_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'new', NOW(), %s, %s)
                ON CONFLICT DO NOTHING RETURNING id""",
                       (job_id, f"https://www.linkedin.com/jobs/view/{job_id}/", j.get("title") or "", j.get("company") or "", j.get("location") or "",
                        j["description"], bool(j.get("easy_apply")), parse_posted(j.get("posted"))))
            added += bool(row)
        promoted = len(_rows("""UPDATE public.job_listings SET status = 'new', updated_at = NOW()
                                 WHERE linkedin_job_id = ANY(%s) AND status IN ('discovered', 'scraped') RETURNING id""", ([str(i) for i in ids],)))
        if added or promoted:
            from app.services.job_pipeline_service import JobPipelineService
            JobPipelineService.kick()
        return {"added": added, "promoted": promoted}

    # ── Triage ───────────────────────────────────────────────────────────
    @staticmethod
    def decide(job: dict, triage: dict, eligibility: dict) -> str:
        """propose: you approve it here. external_manual: a list with the link while company sites are off. discarded: with the reason."""
        cfg = config().get("jobs") or {}
        if eligibility.get("status") == "blocked":
            return "discarded"
        if triage.get("employer_market") == "br" and "br" not in (cfg.get("markets") or ["intl"]):
            return "discarded"
        if (triage.get("score") or 0) < cfg.get("min_score", 70):
            return "discarded"
        if not job.get("easy_apply") and not cfg.get("external_apply"):
            return "external_manual"
        return "propose"

    @staticmethod
    def _discard_reason(triage: dict, eligibility: dict) -> str:
        if eligibility.get("status") == "blocked":
            issues = eligibility.get("issues") or [{}]
            return f"Elegibilidade: {issues[0].get('reason') or issues[0].get('quote') or 'requisito de residência ou visto'}"
        if triage.get("employer_market") == "br":
            return f"Empregador brasileiro: fora do foco atual. {triage.get('reason') or ''}".strip()
        return triage.get("reason") or "Nota abaixo do mínimo"

    @staticmethod
    async def _read(job: dict) -> dict:
        """The fit of the job to your profile (0-100), why, the employer's market and a pay below your floor."""
        from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot
        from app.services.profile_service import ProfileService
        pay = Copilot._facts().get("salary_expectation") or {}
        floors = {"USD": pay.get("abroad_usd_monthly"), "EUR": pay.get("abroad_eur_monthly"), "BRL": pay.get("brazil_brl_monthly")}
        triage = await SkillService.run_skill("jobs/triage.md", {
            "job_title": job.get("job_title") or "", "company": job.get("company") or "", "location": job.get("location") or "",
            "job_description": (job.get("description") or "")[:8000], "floors": floors,
            "candidate": ProfileService.get_resume_base("en")[:12000]})
        if not isinstance(triage, dict) or triage.get("error") or "score" not in triage:
            raise ValueError(f"no triage answer: {triage}")
        triage["score"] = max(0, min(100, int(triage.get("score") or 0)))
        return triage

    @staticmethod
    async def _triage_one(job: dict) -> None:
        from app.services.job_pipeline_service import JobPipelineService
        eligibility = await JobPipelineService.check_eligibility(job["id"])
        triage = await JobSearchService._read(job)
        score = triage["score"]
        outcome = JobSearchService.decide(job, triage, eligibility)
        reason = JobSearchService._discard_reason(triage, eligibility) if outcome == "discarded" else (triage.get("reason") or "")
        _rows("""UPDATE public.job_listings SET triage_score = %s, triage_reason = %s, triage_outcome = %s, employer_market = %s, salary_flag = %s, updated_at = NOW()
                  WHERE id = %s""", (score, reason[:1000], outcome, triage.get("employer_market") or "unknown", (triage.get("salary_flag") or None), job["id"]))
        if outcome == "propose":
            AutomationService.propose_job(job)

    @staticmethod
    def triage_pending(limit: int = 10) -> int:
        """Up to `limit` jobs waiting for their first reading, newest ad first (blocking: call it from a thread)."""
        done = 0
        for job in _rows("""SELECT * FROM public.job_listings WHERE status = 'discovered' AND triage_score IS NULL
                             ORDER BY posted_at DESC NULLS LAST, created_at DESC LIMIT %s""", (limit,)):
            try:
                asyncio.run(JobSearchService._triage_one(job))
                done += 1
            except Exception as e:
                log.warning("job %s not triaged: %s", job["id"], e)
        return done

    @staticmethod
    def score_proposed(limit: int = 5) -> int:
        """Jobs you added yourself reach the approval list without the triage: they get the same fit score, so the list compares
        like with like. Nothing is discarded here: you chose them."""
        done = 0
        for job in _rows("""SELECT j.* FROM public.job_listings j JOIN public.automation_actions a ON a.target_type = 'job' AND a.target_id = j.id
                             WHERE a.kind = 'apply' AND a.status = 'proposed' AND j.triage_score IS NULL AND COALESCE(j.description, '') <> ''
                             ORDER BY a.id DESC LIMIT %s""", (limit,)):
            try:
                triage = asyncio.run(JobSearchService._read(job))
            except Exception as e:
                log.warning("job %s not scored: %s", job["id"], e)
                continue
            _rows("""UPDATE public.job_listings SET triage_score = %s, triage_reason = %s, employer_market = %s, salary_flag = %s, updated_at = NOW()
                      WHERE id = %s""", (triage["score"], (triage.get("reason") or "")[:1000], triage.get("employer_market") or "unknown",
                                         triage.get("salary_flag") or None, job["id"]))
            done += 1
        return done
