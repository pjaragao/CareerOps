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
from typing import Optional
from urllib.parse import urlparse

from . import captcha_solver

log = logging.getLogger("worker.captcha_server")

PORT = int(os.environ.get("CAPTCHA_SERVER_PORT", "8940"))
ATS_CDP = "http://127.0.0.1:9223"
MAX_BODY = 8192


def _host(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower()


class CaptchaServer:
    def __init__(self, browsers, api):
        self.browsers = browsers
        self.api = api
        self.lock = asyncio.Lock()   # one solve at a time: both company-site agents share one Chrome and one mouse

    async def solve_url(self, url: str) -> dict:
        if not self.browsers.is_open("ats"):
            return {"solved": False, "error": "the company-site browser is not open"}
        async with self.lock:
            browser = await self.browsers.playwright.chromium.connect_over_cdp(ATS_CDP, timeout=15000)
            try:
                pages = [p for c in browser.contexts for p in c.pages if not p.is_closed()]
                want = _host(url)
                with_captcha = [p for p in pages if captcha_solver.kind_of(p) and await captcha_solver.active_kind(p)]
                same_host = [p for p in with_captcha if want and _host(p.url) == want]
                if not with_captcha:
                    return {"solved": False, "kind": None, "error": "no open CAPTCHA challenge on any company-site tab (already passed, or a full-page check: take a snapshot)"}
                if not same_host and len(with_captcha) > 1:
                    return {"solved": False, "error": f"CAPTCHA on {len(with_captcha)} tabs, none on {want or 'the given page'}"}
                page = (same_host or with_captcha)[0]
                try:
                    await page.bring_to_front()
                except Exception:
                    pass
                return await captcha_solver.solve(page, captcha_solver.backend_vision(self.api))
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
