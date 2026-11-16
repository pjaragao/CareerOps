"""What the engine knows about each company site (table automation_sites, migrations_v20).

Recipes (token plan, phase 2): the Next / Submit labels that moved a form on in a successful run, so the worker's adapter
tries them first next time, with no LLM. Site memory (phase 0): what blocked the site before (CAPTCHA, Cloudflare,
account wall), so a site that keeps blocking goes straight to you instead of spending a Claude run to find out again."""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional
from urllib.parse import urlparse

from psycopg2.extras import Json

from app.db.session import get_db_connection, get_db_cursor

# kinds of block that only you can pass (a model run cannot): counted per host
HUMAN_BLOCKS = ("captcha",)
BLOCK_RE = {
    "captcha": re.compile(r"captcha|hcaptcha|recaptcha|turnstile|cloudflare|bot[- ]?(check|verification)|anti-?bot|"
                          r"verifica[cç][aã]o de seguran[cç]a|confirme que [eé] humano|are you (a )?human|not a robot|n[aã]o sou um rob", re.I),
}
# after this many blocks of the same kind on a host, the next action there skips the Claude run
SKIP_AFTER = 2


def host_of(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower()


def _rows(sql: str, params: tuple = ()) -> List[dict]:
    conn = get_db_connection()
    try:
        with get_db_cursor(conn) as cur:
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()] if cur.description else []
        conn.commit()
        return rows
    finally:
        conn.close()


def _labels(values) -> List[str]:
    out: List[str] = []
    for v in values or []:
        t = re.sub(r"\s+", " ", str(v or "")).strip().lower()[:60]
        if t and t not in out:
            out.append(t)
    return out[:8]


class SiteService:
    @staticmethod
    def get(host: str) -> Optional[dict]:
        rows = _rows("SELECT * FROM public.automation_sites WHERE host = %s", (host,))
        return rows[0] if rows else None

    @staticmethod
    def recipe(host: str) -> Dict[str, List[str]]:
        site = SiteService.get(host) or {}
        return {"adapter": site.get("adapter") or "generic", "next": site.get("next_labels") or [], "submit": site.get("submit_labels") or []}

    @staticmethod
    def save_recipe(host: str, adapter: str, next_labels: List[str], submit_labels: List[str], success: bool = False) -> dict:
        """The labels a navigation used go first in the list (most recent wins). A success counts only once the page proved
        the application went out (AutomationService.verify), never at the click."""
        site = SiteService.get(host) or {}
        nxt = _labels(list(next_labels or []) + list(site.get("next_labels") or []))
        sub = _labels(list(submit_labels or []) + list(site.get("submit_labels") or []))
        return _rows("""
            INSERT INTO public.automation_sites (host, adapter, next_labels, submit_labels, successes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (host) DO UPDATE SET adapter = EXCLUDED.adapter, next_labels = EXCLUDED.next_labels,
                submit_labels = EXCLUDED.submit_labels, successes = public.automation_sites.successes + EXCLUDED.successes, updated_at = NOW()
            RETURNING *""", (host, (adapter or "generic")[:40], Json(nxt), Json(sub), 1 if success else 0))[0]

    @staticmethod
    def count_success(url_or_host: str) -> None:
        host = url_or_host if "/" not in (url_or_host or "") else host_of(url_or_host)
        if host:
            _rows("""INSERT INTO public.automation_sites (host, successes) VALUES (%s, 1)
                     ON CONFLICT (host) DO UPDATE SET successes = public.automation_sites.successes + 1, updated_at = NOW()""", (host,))

    @staticmethod
    def block_kind(text: str) -> Optional[str]:
        for kind, rx in BLOCK_RE.items():
            if rx.search(text or ""):
                return kind
        return None

    @staticmethod
    def record_block(url_or_host: str, text: str) -> Optional[str]:
        """Counts what blocked a run on this host (from the agent's or the worker's report). Returns the kind, if any."""
        kind = SiteService.block_kind(text)
        host = url_or_host if "/" not in (url_or_host or "") else host_of(url_or_host)
        if not kind or not host:
            return None
        _rows("""
            INSERT INTO public.automation_sites (host, blocks, last_block, last_block_at, failures)
            VALUES (%s, jsonb_build_object(%s::text, 1), %s, NOW(), 1)
            ON CONFLICT (host) DO UPDATE SET
                blocks = public.automation_sites.blocks || jsonb_build_object(%s::text, COALESCE((public.automation_sites.blocks->>%s)::int, 0) + 1),
                last_block = EXCLUDED.last_block, last_block_at = NOW(), failures = public.automation_sites.failures + 1, updated_at = NOW()""",
              (host, kind, kind, kind, kind))
        return kind

    @staticmethod
    def human_block(url: str) -> Optional[str]:
        """The block a run on this host would hit for sure (seen SKIP_AFTER times, and never passed since): None otherwise."""
        site = SiteService.get(host_of(url))
        if not site:
            return None
        blocks = site.get("blocks") or {}
        for kind in HUMAN_BLOCKS:
            if int(blocks.get(kind) or 0) >= SKIP_AFTER and int(site.get("successes") or 0) == 0:
                return kind
        return None

    @staticmethod
    def clear_block(host: str) -> None:
        """You passed it (or the site changed): the host is tried again."""
        _rows("UPDATE public.automation_sites SET blocks = '{}'::jsonb, last_block = NULL, updated_at = NOW() WHERE host = %s", (host,))


# ── Texts written once and reused (token plan, phase 3; table automation_text_cache) ──
ARCHETYPES = (   # job families that share one approved CV per language; anything else gets its own CV
    ("ai_engineering", re.compile(r"\b(ai|ml|llm|genai|gen ai|machine learning|generative|agentic|agents?|mlops|forward deployed|"
                                  r"artificial intelligence|intelig[eê]ncia artificial|ia gen)\b", re.I)),
    ("data", re.compile(r"\b(data scientist|data engineer|data analyst|analytics|business intelligence|bi analyst|cientista de dados)\b", re.I)),
    ("finance", re.compile(r"\b(fp&a|fp & a|finance|financial|controller|controlling|cfo|treasury|valuation|investment|m&a|"
                           r"corporate development|financeiro|finan[cç]as)\b", re.I)),
    ("infrastructure", re.compile(r"\b(infrastructure|project finance|water|wastewater|utility|utilities|energy|cost manager|"
                                  r"project controls?|saneamento|infraestrutura)\b", re.I)),
)


def archetype_of(title: str) -> Optional[str]:
    for name, rx in ARCHETYPES:
        if rx.search(title or ""):
            return name
    return None


def text_key(*parts: str) -> str:
    raw = ":".join(re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", str(p or "").lower()).encode("ascii", "ignore").decode()).strip("-")
                   for p in parts)
    return raw[:300]


class TextCache:
    @staticmethod
    def get(key: str) -> Optional[str]:
        rows = _rows("SELECT text FROM public.automation_text_cache WHERE cache_key = %s", (key,))
        return rows[0]["text"] if rows else None

    @staticmethod
    def put(key: str, kind: str, text: str) -> None:
        if not key or not (text or "").strip():
            return
        _rows("""INSERT INTO public.automation_text_cache (cache_key, kind, text) VALUES (%s, %s, %s)
                 ON CONFLICT (cache_key) DO UPDATE SET text = EXCLUDED.text, created_at = NOW()""", (key, kind[:40], text))

    @staticmethod
    def drop(key: str) -> None:
        _rows("DELETE FROM public.automation_text_cache WHERE cache_key = %s", (key,))
