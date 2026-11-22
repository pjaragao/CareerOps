"""Jobs from more places than LinkedIn, every day, into the same funnel: job_listings ('discovered') → the triage (score,
market, eligibility) → the approval list. Nothing here uses the LinkedIn session or its daily read limit.

- Company boards (Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Workable, Personio, Workday): one row per company in
  job_sources, read once a day. The list fills itself: the boards of the companies you already applied to, the companies whose
  jobs scored ≥ 70 (their name tried on the ATS), the companies the job boards point to, a small catalog and what you add.
- Job boards (Remotive, Remote OK, We Work Remotely, Himalayas, Jobicy, Working Nomads, Arbeitnow; Adzuna and Jooble with a key):
  read twice a day.

Before any AI: the cheap filter (discovery/filters.py), jobs already here (same source id, same form address, same company and
title in any source), ads older than max_age_days. What is left enters up to the day's 'source_read' limit, the best first;
the rest waits for the next reading. Every reading leaves its counts in discovery_runs: the measure of each source.

A source that changes its answer fails clearly (unexpected_layout, the raw answer saved under OUTPUT_DIR/discovery/), never
half a job; a company that left its ATS is tried on the others again.
"""
import json
import logging
import os
import re
import threading
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml

from app.core.config import settings
from app.services.automation_service import AutomationService, _local, _one, _rows, config, now
from app.services.discovery import filters
from app.services.discovery.sources import (LABELS, PROBE_KINDS, READERS, Job, SourceError, ats_of, board_name, fetch_json, norm_url)

log = logging.getLogger("discovery")

DEFAULTS = {"enabled": True, "ats_hours": [6], "board_hours": [6, 14], "max_age_days": 14, "max_age_days_ats": 30, "probe_per_day": 60,
            "details_per_round": 150, "dedupe_days": 60}
BOARD_KINDS = [k for k, (_, fam, _) in READERS.items() if fam == "board"]
ATS_KINDS = [k for k, (_, fam, _) in READERS.items() if fam == "ats"]
KEYED = {"adzuna": ("ADZUNA_APP_ID", "ADZUNA_APP_KEY"), "jooble": ("JOOBLE_API_KEY",)}
_SUFFIX = re.compile(r"\b(inc|llc|ltd|limited|gmbh|ag|sa|s\.a|sas|bv|b\.v|plc|corp|corporation|co|company|group|holdings?|"
                     r"technologies|labs?|hq|ab|oy|as|aps|srl|spa|kg|se|nv|pty)\b\.?", re.I)
_TITLE_TAIL = re.compile(r"\s*[-–—|(,/]\s*(remote|remoto|hybrid|h[ií]brido|on-?site|latam|latin america|brazil|brasil|americas|"
                         r"europe|emea|usa?|united states|anywhere|worldwide|contract|contractor|full[- ]time)\b.*$", re.I)


def _cfg() -> dict:
    return {**DEFAULTS, **(config().get("discovery") or {})}


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def company_key(company: Optional[str]) -> str:
    return re.sub(r"\W", "", _SUFFIX.sub("", _plain(company or "")))


def title_key(title: Optional[str]) -> str:
    return re.sub(r"\W", "", _TITLE_TAIL.sub("", _plain(title or "")))


def dedupe_key(company: Optional[str], title: Optional[str]) -> str:
    c, t = company_key(company), title_key(title)
    return f"{c}|{t}" if c and t else ""


def _keys_of(env: Tuple[str, ...]) -> Optional[Tuple[str, ...]]:
    values = tuple(os.getenv(k, "") for k in env)
    return values if all(values) else None


class DiscoveryService:
    _lock = threading.Lock()

    # ── The list of places ───────────────────────────────────────────────
    @staticmethod
    def kinds_off() -> List[str]:
        row = _one("SELECT discovery_off FROM public.automation_state WHERE id = 1")
        return list((row or {}).get("discovery_off") or [])

    @staticmethod
    def set_kind(kind: str, enabled: bool) -> List[str]:
        if kind not in READERS:
            raise ValueError("Fonte desconhecida")
        off = set(DiscoveryService.kinds_off())
        off.discard(kind) if enabled else off.add(kind)
        _rows("UPDATE public.automation_state SET discovery_off = %s, updated_at = NOW() WHERE id = 1", (sorted(off),))
        return sorted(off)

    @staticmethod
    def add_source(kind: str, slug: str, company: Optional[str], origin: str) -> Optional[dict]:
        """One company board (or job board) more. An existing one is left as it is, except a 'gone' one found again."""
        return _one("""INSERT INTO public.job_sources (kind, slug, company, origin) VALUES (%s, %s, %s, %s)
                       ON CONFLICT (kind, slug) DO UPDATE SET status = CASE WHEN job_sources.status = 'gone' AND EXCLUDED.origin <> 'probe'
                                                                            THEN 'ok' ELSE job_sources.status END,
                                                             failures = CASE WHEN job_sources.status = 'gone' AND EXCLUDED.origin <> 'probe'
                                                                             THEN 0 ELSE job_sources.failures END,
                                                             company = COALESCE(job_sources.company, EXCLUDED.company)
                       RETURNING *""", (kind, slug, (company or "")[:200] or None, origin))

    @staticmethod
    def add_by_link(url: str, company: Optional[str] = None) -> dict:
        """You paste a company's job page (Greenhouse, Lever, Ashby…): its board joins the daily reading."""
        found = ats_of(url)
        if not found:
            raise ValueError("Não reconheci o sistema de vagas desse link (Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Workable, Personio ou Workday)")
        row = DiscoveryService.add_source(found[0], found[1], company, "manual")
        _rows("UPDATE public.job_sources SET enabled = TRUE WHERE id = %s", (row["id"],))
        return row

    @staticmethod
    def ensure_boards() -> None:
        """One row per job board; Adzuna and Jooble only with their key in the environment."""
        for kind in BOARD_KINDS:
            if kind in KEYED and not _keys_of(KEYED[kind]):
                continue
            DiscoveryService.add_source(kind, "all", LABELS.get(kind), "catalog")

    @staticmethod
    def catalog() -> List[dict]:
        path = settings.CONFIG_DIR / "job_sources.yml"
        if not path.exists():
            return []
        return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("companies") or []

    @staticmethod
    def seed_watchlist() -> int:
        """The boards already known: the catalog, the company sites you applied through, the forms of jobs already here."""
        made = 0
        for c in DiscoveryService.catalog():
            found = ats_of(c.get("url") or "") or ((c.get("kind"), c.get("slug")) if c.get("kind") in ATS_KINDS and c.get("slug") else None)
            if found:
                made += bool(DiscoveryService.add_source(found[0], found[1], c.get("company"), "catalog"))
        urls = _rows("""SELECT DISTINCT a.target_url AS url, j.company FROM public.automation_actions a
                          LEFT JOIN public.job_listings j ON a.target_type = 'job' AND j.id = a.target_id
                         WHERE a.kind = 'apply' AND a.lane = 'ats' AND a.target_url IS NOT NULL
                        UNION SELECT DISTINCT apply_url, company FROM public.job_listings WHERE apply_url IS NOT NULL""")
        known = {(r["kind"], r["slug"]) for r in _rows("SELECT kind, slug FROM public.job_sources")}
        for r in urls:
            found = ats_of(r["url"] or "")
            if found and found not in known:
                known.add(found)
                made += bool(DiscoveryService.add_source(found[0], found[1], r.get("company"), "applied"))
        return made

    @staticmethod
    def _slug_guesses(company: str) -> List[str]:
        base = _SUFFIX.sub("", _plain(company)).strip()
        words = re.findall(r"[a-z0-9]+", base)
        if not words:
            return []
        out = ["".join(words), "-".join(words)]
        return list(dict.fromkeys(s for s in out if len(s) >= 3))

    @staticmethod
    def probe_companies(limit: Optional[int] = None) -> int:
        """Companies with a job scored ≥ 70 here (foreign) and no board known yet: their name is tried on Greenhouse, Lever and
        Ashby. A board counts only when it is really that company (its name on Greenhouse, the exact slug on the others)."""
        limit = int(limit if limit is not None else _cfg()["probe_per_day"])
        if limit <= 0:
            return 0
        have = {company_key(r["company"]) for r in _rows("SELECT company FROM public.job_sources WHERE company IS NOT NULL")}
        probed = {r["company_key"] for r in _rows("SELECT company_key FROM public.job_source_probes")}
        rows = _rows("""SELECT company, MAX(triage_score) AS best FROM public.job_listings
                         WHERE triage_score >= 70 AND COALESCE(employer_market, 'unknown') <> 'br' AND COALESCE(company, '') <> ''
                         GROUP BY company ORDER BY best DESC, company""")
        found = 0
        for r in rows:
            key = company_key(r["company"])
            if not key or key in have or key in probed:
                continue
            if limit <= 0:
                break
            limit -= 1
            probed.add(key)
            hit = DiscoveryService._probe_one(r["company"], key)
            _rows("""INSERT INTO public.job_source_probes (company_key, company, found_kind, found_slug) VALUES (%s, %s, %s, %s)
                     ON CONFLICT (company_key) DO UPDATE SET found_kind = EXCLUDED.found_kind, found_slug = EXCLUDED.found_slug, probed_at = NOW()""",
                  (key, r["company"], hit[0] if hit else None, hit[1] if hit else None))
            if hit:
                DiscoveryService.add_source(hit[0], hit[1], r["company"], "probe")
                found += 1
        return found

    @staticmethod
    def _probe_one(company: str, key: str) -> Optional[Tuple[str, str]]:
        for slug in DiscoveryService._slug_guesses(company):
            for kind in PROBE_KINDS:
                try:
                    if kind == "greenhouse":
                        name = board_name(kind, slug)
                        if name and company_key(name) == key:
                            return kind, slug
                        continue
                    if re.sub(r"\W", "", slug) != key:   # Lever and Ashby do not say the name: only the exact name as slug
                        continue
                    url = (f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1" if kind == "lever"
                           else f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
                    data = fetch_json(url)
                    if (isinstance(data, list) and data) or (isinstance(data, dict) and data.get("jobs")):
                        return kind, slug
                except SourceError:
                    continue
        return None

    # ── Reading ──────────────────────────────────────────────────────────
    @staticmethod
    def _save_raw(kind: str, slug: str, raw: Optional[str]) -> str:
        folder = settings.OUTPUT_DIR / "discovery" / now().strftime("%Y-%m-%d")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{kind}-{re.sub(r'[^A-Za-z0-9._-]', '_', slug)[:80]}-{now().strftime('%H%M%S')}.txt"
        path.write_text(raw or "", encoding="utf-8")
        return str(path)

    @staticmethod
    def read_source(src: dict) -> Tuple[List[Job], Optional[SourceError]]:
        reader, _, _ = READERS[src["kind"]]
        try:
            extra = _keys_of(KEYED[src["kind"]]) if src["kind"] in KEYED else ()
            if src["kind"] in KEYED and not extra:
                raise SourceError("missing_key", "a chave da API não está configurada")
            jobs = reader(src["slug"], src.get("company") or "", *extra)
        except SourceError as e:
            failures = src["failures"] + 1
            status = "failing"
            if e.code == "not_found" and (failures >= 2 or src["kind"] in ATS_KINDS):
                status = "gone"   # the company left this ATS: its name is tried on the others again
                _rows("DELETE FROM public.job_source_probes WHERE company_key = %s", (company_key(src.get("company") or src["slug"]),))
            text = e.text
            if e.code == "unexpected_layout":
                text += f" (resposta guardada em {DiscoveryService._save_raw(src['kind'], src['slug'], e.raw)})"
            log.warning("source %s/%s failed: %s", src["kind"], src["slug"], text)
            _rows("""UPDATE public.job_sources SET status = %s, failures = %s, last_run_at = NOW(), last_error_code = %s, last_error = %s
                      WHERE id = %s""", (status, failures, e.code, text[:1000], src["id"]))
            return [], e
        except Exception as e:   # a bug here must not stop the other sources
            log.exception("source %s/%s crashed", src["kind"], src["slug"])
            _rows("""UPDATE public.job_sources SET status = 'failing', failures = failures + 1, last_run_at = NOW(),
                            last_error_code = 'step_stuck', last_error = %s WHERE id = %s""", (str(e)[:1000], src["id"]))
            return [], SourceError("step_stuck", str(e))
        for j in jobs:
            if not j.company:
                j.company = src.get("company") or src["slug"]
        _rows("""UPDATE public.job_sources SET status = 'ok', failures = 0, last_run_at = NOW(), last_ok_at = NOW(), last_error_code = NULL,
                        last_error = NULL, jobs_seen = %s WHERE id = %s""", (len(jobs), src["id"]))
        return jobs, None

    # ── What is already here ─────────────────────────────────────────────
    @staticmethod
    def _known_ids(jobs: Iterable[Job]) -> set:
        by_source: Dict[str, List[str]] = {}
        for j in jobs:
            by_source.setdefault(j.source, []).append(j.source_job_id)
        out = set()
        for source, ids in by_source.items():
            out |= {(source, r["source_job_id"]) for r in _rows(
                "SELECT source_job_id FROM public.job_listings WHERE source = %s AND source_job_id = ANY(%s)", (source, ids))}
        return out

    @staticmethod
    def _here() -> Tuple[Dict[str, int], Dict[str, int]]:
        """{form or ad address: job id} and {company|title: job id} of the jobs here in the last dedupe_days, any source,
        except copies discarded only for their place."""
        days = int(_cfg()["dedupe_days"])
        rows = _rows("""SELECT id, company, job_title, url, apply_url FROM public.job_listings
                         WHERE created_at > NOW() - make_interval(days => %s) AND COALESCE(triage_reason, '') NOT LIKE 'Local fora do foco%%'""",
                     (days,))
        urls: Dict[str, int] = {}
        keys: Dict[str, int] = {}
        for r in rows:
            for u in (r["url"], r["apply_url"]):
                if u and "linkedin.com/jobs/view" not in u:
                    urls.setdefault(norm_url(u), r["id"])
            k = dedupe_key(r["company"], r["job_title"])
            if k:
                keys.setdefault(k, r["id"])
        for r in _rows("""SELECT target_id, target_url FROM public.automation_actions
                           WHERE kind = 'apply' AND lane = 'ats' AND target_url IS NOT NULL AND created_at > NOW() - make_interval(days => %s)""", (days,)):
            urls.setdefault(norm_url(r["target_url"]), r["target_id"])
        return urls, keys

    # ── One round ────────────────────────────────────────────────────────
    @staticmethod
    def run_round(family: str, kinds: Optional[List[str]] = None) -> dict:
        """Reads every enabled source of the family, then lets in what is new and passes the filter, within the day's limit."""
        cfg = _cfg()
        off = set(DiscoveryService.kinds_off())
        kinds = [k for k in (kinds or (ATS_KINDS if family == "ats" else BOARD_KINDS)) if k not in off]
        if family == "ats":
            DiscoveryService.seed_watchlist()
            try:
                DiscoveryService.probe_companies()
            except Exception as e:
                log.warning("company probe failed: %s", e)
        else:
            DiscoveryService.ensure_boards()
        stats: Dict[str, dict] = {}
        jobs: List[Job] = []
        for kind in kinds:
            sources = _rows("""SELECT * FROM public.job_sources WHERE kind = %s AND enabled AND status <> 'gone' ORDER BY last_run_at NULLS FIRST, id""",
                            (kind,))
            st = stats.setdefault(kind, {"sources": 0, "fetched": 0, "errors": 0, "codes": {}, "run": None})
            if not sources:
                continue
            st["run"] = _one("INSERT INTO public.discovery_runs (kind) VALUES (%s) RETURNING id", (kind,))["id"]
            for src in sources:
                got, err = DiscoveryService.read_source(src)
                st["sources"] += 1
                st["fetched"] += len(got)
                if err:
                    st["errors"] += 1
                    st["codes"][err.code] = st["codes"].get(err.code, 0) + 1
                for j in got:
                    j._source_id = src["id"]   # type: ignore[attr-defined]
                jobs.extend(got)
        age = int(cfg["max_age_days_ats"] if family == "ats" else cfg["max_age_days"])
        result = DiscoveryService.ingest(jobs, stats, max_age_days=age, details=int(cfg["details_per_round"]))
        for kind, st in stats.items():
            if st["run"]:
                k = result["by_kind"].get(kind, {})
                _rows("""UPDATE public.discovery_runs SET finished_at = NOW(), sources = %s, fetched = %s, filtered = %s, duplicates = %s,
                                known = %s, added = %s, deferred = %s, errors = %s, error_code = %s, details = %s WHERE id = %s""",
                      (st["sources"], st["fetched"], k.get("filtered", 0), k.get("duplicates", 0), k.get("known", 0), k.get("added", 0),
                       k.get("deferred", 0), st["errors"], next(iter(st["codes"]), None),
                       json.dumps({"codes": st["codes"], "reasons": k.get("reasons", {})}), st["run"]))
        DiscoveryService._alert(stats)
        return {"family": family, "kinds": {k: {**{x: v for x, v in st.items() if x != "run"}, **result["by_kind"].get(k, {})} for k, st in stats.items()},
                "added": result["added"], "deferred": result["deferred"]}

    @staticmethod
    def ingest(jobs: List[Job], stats: Optional[dict] = None, max_age_days: int = 14, details: int = 150) -> dict:
        by_kind: Dict[str, dict] = {}

        def count(job: Job, what: str, reason: Optional[str] = None) -> None:
            k = by_kind.setdefault(job.source, {"filtered": 0, "duplicates": 0, "known": 0, "added": 0, "deferred": 0, "reasons": {}})
            k[what] += 1
            if reason:
                k["reasons"][reason] = k["reasons"].get(reason, 0) + 1

        known = DiscoveryService._known_ids(jobs)
        urls, keys = DiscoveryService._here()
        oldest = now() - timedelta(days=max_age_days)
        seen_ids, batch_keys = set(), {}
        candidates: List[Tuple[Job, filters.Verdict]] = []
        board_ats: List[Tuple[str, str, str]] = []
        for j in jobs:
            ident = (j.source, j.source_job_id)
            if ident in known or ident in seen_ids:
                count(j, "known")
                continue
            seen_ids.add(ident)
            ats = ats_of(j.apply_url) if j.source in BOARD_KINDS else None
            if ats:
                board_ats.append((ats[0], ats[1], j.company))
            verdict = filters.judge(j)
            if not verdict.keep:
                count(j, "filtered", verdict.reason)
                continue
            if j.posted_at and j.posted_at < oldest:   # after the filter, so "old" counts only jobs of your profile
                count(j, "filtered", "old")
                continue
            twin = urls.get(norm_url(j.apply_url)) or urls.get(norm_url(j.url))
            key = dedupe_key(j.company, j.title)
            if twin or (key and (key in keys or key in batch_keys)):
                count(j, "duplicates")
                continue
            if key:
                batch_keys[key] = True
            candidates.append((j, verdict))
        # the ad of a list without descriptions (SmartRecruiters, Workday) is read only now, for what passed so far
        ready: List[Tuple[Job, filters.Verdict]] = []
        for j, verdict in candidates:
            if j.needs_detail and not j.description:
                if details <= 0:
                    count(j, "deferred")
                    continue
                details -= 1
                try:
                    READERS[j.source][2](j)
                except SourceError as e:
                    count(j, "filtered", f"detail_{e.code}")
                    continue
                verdict = filters.judge(j)
                if not verdict.keep:
                    count(j, "filtered", verdict.reason)
                    continue
                if j.posted_at and j.posted_at < oldest:
                    count(j, "filtered", "old")
                    continue
            ready.append((j, verdict))
        ready.sort(key=lambda p: (p[1].affinity, p[0].posted_at or datetime(1970, 1, 1, tzinfo=timezone.utc)), reverse=True)
        left = next((l["left"] for l in AutomationService.limits() if l["kind"] == "source_read"), 0)
        added = deferred = 0
        for j, verdict in ready:
            if left <= 0:
                count(j, "deferred")
                deferred += 1
                continue
            if DiscoveryService._insert(j, verdict):
                left -= 1
                added += 1
                count(j, "added")
                _rows("UPDATE public.job_sources SET jobs_added = jobs_added + 1 WHERE id = %s", (getattr(j, "_source_id", 0),))
            else:
                count(j, "known")
        for kind, slug, company in board_ats:   # the job boards point to company boards: those join the daily reading
            DiscoveryService.add_source(kind, slug, company, "board")
        return {"by_kind": by_kind, "added": added, "deferred": deferred}

    @staticmethod
    def _insert(j: Job, verdict: filters.Verdict) -> bool:
        description = j.description[:20000]
        if j.salary:
            description += f"\n\nSalary (as stated by {LABELS.get(j.source, j.source)}): {j.salary}"
        row = _one("""INSERT INTO public.job_listings (linkedin_job_id, url, job_title, company, location, description, status, scraped_at,
                                                       easy_apply, posted_at, search_slug, source, source_job_id, apply_url)
                      VALUES (NULL, %s, %s, %s, %s, %s, 'discovered', NOW(), FALSE, %s, %s, %s, %s, %s)
                      ON CONFLICT DO NOTHING RETURNING id""",
                   (j.url[:2000], j.title[:300], (j.company or "")[:300], (j.location or "")[:500], description, j.posted_at,
                    f"{verdict.group}:{verdict.mode}", j.source, j.source_job_id[:500], (j.apply_url or j.url)[:2000]))
        return bool(row)

    # ── When ─────────────────────────────────────────────────────────────
    @staticmethod
    def due(family: str, local: Optional[datetime] = None) -> bool:
        cfg = _cfg()
        if not cfg.get("enabled", True):
            return False
        local = local or _local()
        hours = [h for h in cfg["ats_hours" if family == "ats" else "board_hours"] if h <= local.hour]
        if not hours:
            return False
        slot = local.replace(hour=max(hours), minute=0, second=0, microsecond=0)
        last = _one("SELECT MAX(started_at) AS at FROM public.discovery_runs WHERE kind = %s", (f"round:{family}",))
        return not (last and last["at"] and last["at"] >= slot)

    @staticmethod
    def run_due() -> List[dict]:
        """Every few minutes (main.py): the rounds whose hour came. One at a time, whatever calls it."""
        if not DiscoveryService._lock.acquire(blocking=False):
            return []
        try:
            out = []
            for family in ("ats", "board"):
                if DiscoveryService.due(family):
                    mark = _one("INSERT INTO public.discovery_runs (kind) VALUES (%s) RETURNING id", (f"round:{family}",))
                    result = DiscoveryService.run_round(family)
                    _rows("UPDATE public.discovery_runs SET finished_at = NOW(), added = %s, deferred = %s WHERE id = %s",
                          (result["added"], result["deferred"], mark["id"]))
                    log.info("discovery round %s: %s added, %s deferred", family, result["added"], result["deferred"])
                    out.append(result)
            DiscoveryService.daily_report()
            return out
        finally:
            DiscoveryService._lock.release()

    @staticmethod
    def run_now(family: str) -> dict:
        if family not in ("ats", "board"):
            raise ValueError("ats ou board")
        if not DiscoveryService._lock.acquire(blocking=False):
            raise ValueError("Uma leitura já está em andamento")
        try:
            mark = _one("INSERT INTO public.discovery_runs (kind) VALUES (%s) RETURNING id", (f"round:{family}",))
            result = DiscoveryService.run_round(family)
            _rows("UPDATE public.discovery_runs SET finished_at = NOW(), added = %s, deferred = %s WHERE id = %s",
                  (result["added"], result["deferred"], mark["id"]))
            return result
        finally:
            DiscoveryService._lock.release()

    # ── Telling you ──────────────────────────────────────────────────────
    @staticmethod
    def _alert(stats: Dict[str, dict]) -> None:
        """A reader that no longer knows the answer of its source, or a job board that failed twice in a row: one message."""
        from app.services.bot_service import BotService
        day = _local().date().isoformat()
        for kind, st in stats.items():
            layout = st["codes"].get("unexpected_layout", 0)
            board_down = kind in BOARD_KINDS and st["sources"] and st["errors"] == st["sources"] and _one(
                "SELECT 1 AS y FROM public.job_sources WHERE kind = %s AND failures >= 2 LIMIT 1", (kind,))
            if layout >= (1 if kind in BOARD_KINDS else 3) or board_down:
                why = "mudou o formato da resposta (unexpected_layout)" if layout else "não responde há 2 leituras"
                BotService.notify("discovery", f"🔎 *Busca de vagas*: {LABELS.get(kind, kind)} {why}. As outras fontes seguem; "
                                               f"vejo o detalhe em Pesquisar vagas → Fontes.", {"kind": kind, "codes": st["codes"]},
                                  key=f"discovery:{kind}:{day}")

    @staticmethod
    def daily_report() -> Optional[dict]:
        """After 7h, once a day: what came in yesterday per source, with the approval link. No approval by reply."""
        local = _local()
        if local.hour < 7:
            return None
        day = local.date()
        key = f"discovery_report:{day.isoformat()}"
        if _one("SELECT 1 AS y FROM public.bot_notifications WHERE dedupe_key = %s", (key,)):
            return None
        rows = DiscoveryService.stats(days=1, until_today=True)["sources"]
        added = sum(r["added"] for r in rows)
        if not added:
            return None
        from app.services.approval_link_service import ApprovalLinkService
        from app.services.bot_service import BotService
        top = sorted((r for r in rows if r["added"]), key=lambda r: -r["proposed"])
        parts = ", ".join(f"{r['label']} {r['proposed']}" for r in top if r["proposed"])
        proposed = sum(r["proposed"] for r in rows)
        waiting = _one("SELECT COUNT(*) AS n FROM public.automation_actions WHERE kind = 'apply' AND status = 'proposed'")["n"]
        text = (f"🔎 *Busca de vagas* · ontem: {added} novas, {proposed} propostas" + (f" ({parts})" if parts else "") + ".\n"
                + (f"{waiting} vagas esperando você: {ApprovalLinkService.create_link()}" if waiting else "Nada esperando aprovação."))
        return BotService.notify("discovery", text, {"added": added, "proposed": proposed}, key=key)

    # ── The measure ──────────────────────────────────────────────────────
    @staticmethod
    def stats(days: int = 7, until_today: bool = False) -> dict:
        """Per source: new jobs, what the triage proposed, what you approved; and the health of each kind of source."""
        start = _local().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days if until_today else days - 1)
        end = _local().replace(hour=0, minute=0, second=0, microsecond=0) if until_today else now() + timedelta(days=1)
        rows = _rows("""
            SELECT j.source, COUNT(*) AS added, COUNT(*) FILTER (WHERE j.triage_score IS NOT NULL) AS triaged,
                   COUNT(a.id) AS proposed, COUNT(a.id) FILTER (WHERE a.approved_at IS NOT NULL) AS approved,
                   COUNT(a.id) FILTER (WHERE a.status = 'done') AS applied
              FROM public.job_listings j
              LEFT JOIN public.automation_actions a ON a.kind = 'apply' AND a.target_type = 'job' AND a.target_id = j.id
             WHERE j.created_at >= %s AND j.created_at < %s AND (j.source <> 'linkedin' OR j.search_slug IS NOT NULL)
             GROUP BY j.source""", (start, end))
        runs = {r["kind"]: r for r in _rows("""
            SELECT kind, SUM(fetched) AS fetched, SUM(filtered) AS filtered, SUM(duplicates) AS duplicates, SUM(deferred) AS deferred,
                   SUM(errors) AS errors FROM public.discovery_runs WHERE started_at >= %s AND started_at < %s AND kind NOT LIKE 'round:%%'
             GROUP BY kind""", (start, end))}
        health = {r["kind"]: r for r in _rows("""
            SELECT kind, COUNT(*) AS boards, COUNT(*) FILTER (WHERE enabled AND status = 'ok') AS ok,
                   COUNT(*) FILTER (WHERE status = 'failing') AS failing, COUNT(*) FILTER (WHERE status = 'gone') AS gone,
                   MAX(last_ok_at) AS last_ok_at, MAX(last_run_at) AS last_run_at,
                   (ARRAY_AGG(last_error ORDER BY last_run_at DESC NULLS LAST) FILTER (WHERE last_error IS NOT NULL))[1] AS last_error
              FROM public.job_sources GROUP BY kind""")}
        by = {r["source"]: r for r in rows}
        off = set(DiscoveryService.kinds_off())
        out = []
        for kind in ["linkedin"] + list(READERS):
            r, run, h = by.get(kind) or {}, runs.get(kind) or {}, health.get(kind) or {}
            if kind in KEYED and not _keys_of(KEYED[kind]) and not r:
                h = {**h, "last_error": "sem chave da API"}
            out.append({"kind": kind, "label": LABELS.get(kind, kind), "family": "linkedin" if kind == "linkedin" else READERS[kind][1],
                        "enabled": kind not in off, "added": int(r.get("added") or 0), "triaged": int(r.get("triaged") or 0),
                        "proposed": int(r.get("proposed") or 0), "approved": int(r.get("approved") or 0), "applied": int(r.get("applied") or 0),
                        "fetched": int(run.get("fetched") or 0), "filtered": int(run.get("filtered") or 0),
                        "duplicates": int(run.get("duplicates") or 0), "deferred": int(run.get("deferred") or 0), "errors": int(run.get("errors") or 0),
                        "boards": int(h.get("boards") or 0), "ok": int(h.get("ok") or 0), "failing": int(h.get("failing") or 0),
                        "gone": int(h.get("gone") or 0), "last_ok_at": h.get("last_ok_at"), "last_run_at": h.get("last_run_at"),
                        "last_error": h.get("last_error")})
        rounds = _rows("""SELECT kind, started_at, finished_at, added, deferred FROM public.discovery_runs WHERE kind LIKE 'round:%%'
                           ORDER BY id DESC LIMIT 6""")
        return {"days": days, "sources": out, "rounds": rounds}

    @staticmethod
    def list_sources(kind: Optional[str] = None, limit: int = 300) -> List[dict]:
        return _rows(f"""SELECT * FROM public.job_sources {"WHERE kind = %s" if kind else ""}
                          ORDER BY status = 'ok', jobs_added DESC, company NULLS LAST LIMIT %s""", ((kind, limit) if kind else (limit,)))

    @staticmethod
    def set_source(source_id: int, enabled: bool) -> Optional[dict]:
        return _one("UPDATE public.job_sources SET enabled = %s WHERE id = %s RETURNING *", (enabled, source_id))
