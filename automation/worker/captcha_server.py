"""The apply agent's way to the CAPTCHA solver (2026-11-19): a tiny HTTP server in the worker, published on the host's
loopback only (docker-compose.yml). The agent's `solve_captcha` tool (runner → mcp_bridge on the host) posts here; the
solver attaches to the company-site browser over CDP (it never leaves this container), finds the tab with the challenge
and runs captcha_solver.solve on it. The LinkedIn browser is never touched.

POST /solve {"url": "<the page the agent is on>"}, header X-CareerOps-Token = the worker token
→ {"solved": bool, "kind": ..., "how"|"error": ...}"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re
from typing import Optional
from urllib.parse import urlparse

from . import captcha_solver, hcaptcha_agent

log = logging.getLogger("worker.captcha_server")

PORT = int(os.environ.get("CAPTCHA_SERVER_PORT", "8940"))
ATS_CDP = "http://127.0.0.1:9223"
MAX_BODY = 8192
OPEN_WAIT_ROUNDS = 10   # seconds a challenge may take to open after the agent's click
LOCK_WAIT = 45          # seconds a caller waits for another tab's solve
BLOCKED_PAGE = re.compile(r"you have been blocked|access denied|error 1020|request blocked|you don't have permission to access|"
                          r"acesso negado|voc[eê] foi bloqueado", re.I)


def _host(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower()


def _site(url_or_host: str) -> str:
    """The last two labels of the host (careers-cravath.icims.com and login.icims.com are both icims.com)."""
    host = _host(url_or_host) if "/" in (url_or_host or "") else (url_or_host or "").lower()
    return ".".join(host.split(".")[-2:]) if host.count(".") >= 1 else host


def pick_tab(tabs: list, want: str):
    """The tab the agent means, among those with a CAPTCHA: its host on the tab or on a frame inside it, else the one tab
    of the same site (iCIMS moves the login to login.icims.com: 2026-11-20, Cravath "CAPTCHA on 2 tabs, none on
    careers-cravath.icims.com"); None when two companies' tabs would fit."""
    if not want:
        return tabs[0] if len(tabs) == 1 else None
    exact = [t for t in tabs if _host(t.url) == want or any(_host(f.url) == want for f in t.frames)]
    if exact:
        return exact[0]
    # each agent has its own browser context: the CAPTCHA tab whose sibling tab is on that host (2026-11-20: Cravath and
    # Rivian both on login.icims.com at once)
    def siblings(t):
        try:
            return [p for p in t.context.pages if p is not t]
        except Exception:
            return []
    kin = [t for t in tabs if any(_host(p.url) == want for p in siblings(t))]
    if len(kin) == 1:
        return kin[0]
    site = [t for t in tabs if _site(t.url) == _site(want) or any(_site(f.url) == _site(want) for f in t.frames)]
    if len(site) == 1:
        return site[0]
    return tabs[0] if len(tabs) == 1 else None


class CaptchaServer:
    def __init__(self, browsers, api):
        self.browsers = browsers
        self.api = api
        self.lock = asyncio.Lock()   # one solve at a time: both company-site agents share one Chrome and one mouse

    async def solve_url(self, url: str) -> dict:
        if not self.browsers.is_open("ats"):
            return {"solved": False, "error": "the company-site browser is not open"}
        # one solve at a time (one mouse); a caller that would wait long is told to come back instead of hanging past its
        # own timeout (2026-11-19: 4 agents queued behind 6-minute image runs and all timed out)
        try:
            await asyncio.wait_for(self.lock.acquire(), timeout=LOCK_WAIT)
        except asyncio.TimeoutError:
            return {"solved": False, "busy": True, "error": "solver busy with another tab: wait 1 minute and call solve_captcha again"}
        try:
            return await self._solve_locked(url)
        finally:
            self.lock.release()

    async def _solve_locked(self, url: str) -> dict:
        browser = await self.browsers.playwright.chromium.connect_over_cdp(ATS_CDP, timeout=15000)
        try:
            pages = [p for c in browser.contexts for p in c.pages if not p.is_closed()]
            want = _host(url)
            # the agent asks right after its click on "submit": the challenge takes a few seconds to open (2026-11-19,
            # Ashby: "no challenge" at once, the box open a moment later)
            with_captcha = []
            for _ in range(OPEN_WAIT_ROUNDS):
                with_captcha = [p for p in pages if captcha_solver.kind_of(p) and await captcha_solver.active_kind(p)]
                if with_captcha:
                    break
                await asyncio.sleep(1)
            if not with_captcha:
                # a firewall's block page is no challenge: say so, so the agent stops at once instead of asking again
                # (2026-11-19, NatWest: Cloudflare "Sorry, you have been blocked")
                for p in [p for p in pages if want and _host(p.url) == want]:
                    try:
                        text = await p.evaluate("() => (document.body && document.body.innerText || '').slice(0, 1500)")
                    except Exception:
                        continue
                    if BLOCKED_PAGE.search(text or ""):
                        return {"solved": False, "kind": "blocked",
                                "error": "the site's firewall blocked this browser (not a CAPTCHA, nothing to solve): stop with needs_user and say 'bloqueado pelo site'"}
                return {"solved": False, "kind": None, "error": "no open CAPTCHA challenge on any company-site tab (already passed, or a full-page check: take a snapshot)"}
            page = pick_tab(with_captcha, want)
            if page is None:
                return {"solved": False, "error": f"CAPTCHA on {len(with_captcha)} tabs, none on {want or 'the given page'}"}
            try:
                await page.bring_to_front()
            except Exception:
                pass
            return await captcha_solver.solve(page, captcha_solver.backend_vision(self.api), hcaptcha_agent.backend_reasoner(self.api))
        finally:
            # disconnects this client only: the tabs, the agent's contexts and the browser stay as they are
            try:
                await browser.close()
            except Exception:
                pass

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        status, body = 500, {"error": "internal"}
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
            lines = head.decode("latin-1").split("\r\n")
            method, path, _ = (lines[0].split(" ") + ["", "", ""])[:3]
            headers = {k.strip().lower(): v.strip() for k, _, v in (l.partition(":") for l in lines[1:] if l)}
            size = min(int(headers.get("content-length") or 0), MAX_BODY)
            raw = await reader.readexactly(size) if size else b""
            if method == "GET" and path == "/health":
                status, body = 200, {"ok": True}
            elif not self.api.token or not hmac.compare_digest(headers.get("x-careerops-token", ""), self.api.token):
                status, body = 401, {"error": "unauthorized"}
            elif method == "POST" and path == "/solve":
                req = json.loads(raw or b"{}")
                status, body = 200, await self.solve_url(str(req.get("url") or ""))
            else:
                status, body = 404, {"error": "not found"}
        except Exception as e:
            log.warning("captcha server: %s", e)
            status, body = 500, {"solved": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
        data = json.dumps(body).encode()
        writer.write(f"HTTP/1.1 {status} OK\r\nContent-Type: application/json\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n".encode() + data)
        try:
            await writer.drain()
        finally:
            writer.close()

    async def serve(self, stopping: asyncio.Event) -> None:
        server = await asyncio.start_server(self._handle, "0.0.0.0", PORT)
        log.info("captcha solver listening on %s", PORT)
        async with server:
            await stopping.wait()
