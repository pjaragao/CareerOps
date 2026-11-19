"""The two browsers: "linkedin" holds your session; "ats" has no LinkedIn session and is where company sites open, so a
malicious site never shares a browser with your account. Each task gets its own window: a background tab is not rendered
by Chrome and LinkedIn's lists stop at the first 10 items (see extension/background.js)."""
import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from playwright.async_api import BrowserContext, Page, async_playwright

log = logging.getLogger("worker.browser")

import asyncio
import os
import shutil
import signal
import subprocess
from pathlib import Path

PROFILES = {"linkedin": {"dir": "/data/profiles/linkedin", "port": 9222}, "ats": {"dir": "/data/profiles/ats", "port": 9223}}
# Token plan, phase 1: on company sites a click or a keystroke no longer returns the whole page (the agent asks for a
# snapshot when it needs one), screenshots carry no image, and only console errors come back.
LEAN_MCP = ["--snapshot-mode", "none", "--image-responses", "omit", "--console-level", "error"]
MCP_PORTS = {
    "linkedin": {"port": 8931, "cdp": 9222, "blocked": "", "extra": []},
    "ats": {"port": 8932, "cdp": 9223, "blocked": "https://www.linkedin.com;https://linkedin.com", "extra": LEAN_MCP},
    # a second agent on company sites at the same time (2026-11-17): same browser, but every session in its own fresh
    # context (--isolated), so the two agents never share or switch each other's tabs; no extra Chrome in memory
}
# more company-site agents in parallel (2026-11-19: "o mais rápido possível, só o limite do servidor"): slot n on port
# 8931 + n, each session in its own isolated context of the same Chrome
ATS_SLOTS = 4
for _n in range(2, ATS_SLOTS + 1):
    MCP_PORTS[f"ats{_n}"] = {"port": 8931 + _n, "cdp": 9223, "blocked": "https://www.linkedin.com;https://linkedin.com",
                             "extra": LEAN_MCP + ["--isolated"]}
# servers that live and die with a browser: the other company-site servers follow the company-site browser
MCP_COMPANIONS = {"ats": [f"ats{_n}" for _n in range(2, ATS_SLOTS + 1)]}


async def _stop_mcp(name: str) -> None:
    """Terminates any running playwright-mcp instance bound to the named lane's port."""
    cfg = MCP_PORTS.get(name)
    if not cfg or not Path("/data/run").is_dir():
        return
    needle = f"--port {cfg['port']}"
    killed = []
    proc_dir = Path("/proc")
    if proc_dir.is_dir():
        for entry in proc_dir.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
            except OSError:
                continue
            if "playwright-mcp" in raw and needle in raw:
                pid = int(entry.name)
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed.append(pid)
                except OSError:
                    pass
    if killed:
        await asyncio.sleep(0.4)
        for pid in killed:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


async def _restart_mcp(name: str) -> None:
    """Replaces any stale playwright-mcp with a fresh instance pointing at the live CDP port."""
    cfg = MCP_PORTS.get(name)
    if not cfg or not Path("/data/run").is_dir() or not shutil.which("playwright-mcp"):
        return
    await _stop_mcp(name)
    cmd = [
        "playwright-mcp",
        "--cdp-endpoint", f"http://127.0.0.1:{cfg['cdp']}",
        "--host", "0.0.0.0",
        "--port", str(cfg["port"]),
        "--allowed-hosts", "*",
        "--allow-unrestricted-file-access",
    ]
    if cfg["blocked"]:
        cmd.extend(["--blocked-origins", cfg["blocked"]])
    cmd.extend(cfg.get("extra") or [])
    log_path = Path(f"/data/run/mcp-{name}.log")
    with open(log_path, "ab") as log_file:
        subprocess.Popen(cmd, cwd="/data/run", stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)
    await asyncio.sleep(0.4)
EXTENSION = os.environ.get("EXTENSION_DIR", "/app/extension")
BROWSER_MODE = os.environ.get("BROWSER_MODE", "xvfb")   # xvfb (visible through noVNC) | headless


class Browsers:
    def __init__(self, api_base: str, token: str):
        self.api_base = api_base
        self.token = token
        self.playwright = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.lock = asyncio.Lock()

    async def start(self) -> None:
        self.playwright = await async_playwright().start()

    async def context(self, name: str) -> BrowserContext:
        async with self.lock:
            if name in self.contexts:
                return self.contexts[name]
            profile = PROFILES[name]
            Path(profile["dir"]).mkdir(parents=True, exist_ok=True)
            for lock in ("SingletonLock", "SingletonCookie", "SingletonSocket"):   # left by a container that was killed
                Path(profile["dir"], lock).unlink(missing_ok=True)
            args = [f"--disable-extensions-except={EXTENSION}", f"--load-extension={EXTENSION}", f"--remote-debugging-port={profile['port']}",
                    "--disable-dev-shm-usage", "--no-first-run", "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                    "--disable-backgrounding-occluded-windows", "--disable-popup-blocking", "--window-size=1320,950"]
            args += [a for a in os.environ.get("BROWSER_EXTRA_ARGS", "").split("|") if a]
            context = await self.playwright.chromium.launch_persistent_context(
                profile["dir"], channel="chromium", headless=BROWSER_MODE == "headless", args=args, viewport=None,
                ignore_https_errors=bool(os.environ.get("BROWSER_IGNORE_HTTPS_ERRORS")), locale="pt-BR")
            await self._configure_extension(context)
            self.contexts[name] = context
            await _restart_mcp(name)
            for extra in MCP_COMPANIONS.get(name, []):
                await _restart_mcp(extra)
            log.info("browser %s started (%s)", name, BROWSER_MODE)
            return context

    async def _configure_extension(self, context: BrowserContext) -> None:
        """The copy of the extension in this browser reports to the backend, with the worker's token."""
        worker = context.service_workers[0] if context.service_workers else await context.wait_for_event("serviceworker", timeout=30000)
        await worker.evaluate("(cfg) => chrome.storage.local.set({ careeropsManaged: cfg, careeropsPaused: false })",
                              {"apiBase": self.api_base, "token": self.token})

    async def new_window(self, name: str) -> Page:
        """A page in a window of its own, so it stays visible to Chrome."""
        context = await self.context(name)
        anchor = context.pages[0] if context.pages else await context.new_page()
        session = await context.new_cdp_session(anchor)
        async with context.expect_page(timeout=15000) as info:
            await session.send("Target.createTarget", {"url": "about:blank", "newWindow": True})
        await session.detach()
        return await info.value

    async def close_browser(self, name: str) -> None:
        async with self.lock:
            context = self.contexts.pop(name, None)
        await _stop_mcp(name)
        for extra in MCP_COMPANIONS.get(name, []):
            await _stop_mcp(extra)
        if context:
            await context.close()
            log.info("browser %s closed", name)

    def is_open(self, name: str) -> bool:
        return name in self.contexts

    async def close_extra_pages(self, name: str, keep: set) -> None:
        """Tabs left behind (the Claude routine opens its own). The first page stays: a browser with no window exits."""
        context = self.contexts.get(name)
        if context:
            for page in context.pages[1:]:
                if page not in keep:
                    await page.close()

    async def stop(self) -> None:
        for name in list(self.contexts):
            await self.close_browser(name)
        if self.playwright:
            await self.playwright.stop()
