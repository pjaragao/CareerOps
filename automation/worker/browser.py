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

PROFILES = {"linkedin": {"dir": "/data/profiles/linkedin", "port": 9222}, "ats": {"dir": "/data/profiles/ats", "port": 9223}}
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
