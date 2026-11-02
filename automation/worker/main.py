"""CareerOps worker: asks the backend for the next action of each lane and runs it in the server browser. It decides nothing:
with the mode off the backend hands out nothing and this only waits. SIGTERM (a redeploy) finishes what is running first."""
import asyncio
import logging
import os
import shutil
import signal
import time
from pathlib import Path

import httpx

from .api import Api
from .browser import Browsers
from .handlers import ARTIFACTS, RUN_DIR, Runner, browser_of
from .safety import LINKEDIN_LOGGED_OUT
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

WORKER_ID = os.environ.get("WORKER_ID", "automation-1")
IDLE_SECONDS = {"off": 60, "halted": 30, "outside_window": 120, "gap": 30, "empty": 20, "lane_busy": 15, "max_windows": 15}
ATS_IDLE_SECONDS = 600
ARTIFACT_DAYS = 30


class Worker:
    def __init__(self):
        self.api = Api()
        self.browsers = Browsers(self.api.base, self.api.token)
        self.runner = Runner(self.api, self.browsers)
        self.stopping = asyncio.Event()
        self.ats_last_used = 0.0
        self.running = set()
        self.session_page = None

    async def lane_loop(self, lane: str) -> None:
        """Lanes are the backend's concurrency: when a lane allows two, the next claim gets the next action."""
        while not self.stopping.is_set():
            wait = 10
            try:
                claimed = await self.api.post("/automation/claim", {"lane": lane, "worker": WORKER_ID})
                action = claimed.get("action")
                if action:
                    task = asyncio.create_task(self.run_one(action))
                    self.running.add(task)
                    task.add_done_callback(self.running.discard)
                    wait = 2
                else:
                    wait = IDLE_SECONDS.get(claimed.get("reason"), 20)
            except httpx.HTTPError as e:
                log.warning("backend unreachable (%s): %s", lane, e)
                wait = 30
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=wait)
            except asyncio.TimeoutError:
                pass

    async def run_one(self, action: dict) -> None:
        if browser_of(action["lane"]) == "ats":
            self.ats_last_used = time.monotonic()
        log.info("action %s (%s, verify_only=%s)", action["id"], action["kind"], action.get("verify_only"))
        await self.runner.handle(action)

    async def session_loop(self) -> None:
        """A window at LinkedIn's login page while there is no session, for you to sign in through noVNC. Once signed in it
        closes and nothing visits LinkedIn just to check: any action that finds the session gone stops and reopens this."""
        while not self.stopping.is_set():
            try:
                state = await self.api.get("/automation/status")
                if state and state["state"].get("session_status") != "logged_in":
                    if self.session_page is None or self.session_page.is_closed():
                        self.session_page = await self.browsers.new_window("linkedin")
                        await self.session_page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
                    url = self.session_page.url
                    logged_out = bool(LINKEDIN_LOGGED_OUT.search(urlparse(url).path)) or "/checkpoint/" in url
                    await self.api.post("/automation/session", {"status": "logged_out" if logged_out else "logged_in"})
                    if not logged_out:
                        await self.session_page.close()
                        self.session_page = None
            except httpx.HTTPError as e:
                log.warning("backend unreachable (session): %s", e)
            except Exception as e:
                log.warning("session check failed: %s", e)
            await self._wait(20)

    async def _wait(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self.stopping.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def housekeeping_loop(self) -> None:
        """Company-site forms already handled; the second browser when it has been idle a while; old screenshots."""
        while not self.stopping.is_set():
            try:
                await self.runner.release_kept()
                state = await self.api.get("/automation/status")
                counts = state["counts"] if state else {}
                # The Claude routine reaches the browsers through their debugging ports: they must be up while it has work,
                # also after a restart (a redeploy, a crash), when nothing else would have opened them
                routine_work = counts.get("escalated") or counts.get("running_claude")
                if routine_work:
                    self.ats_last_used = time.monotonic()
                    await self.browsers.context("linkedin")
                    await self.browsers.context("ats")
                if self.browsers.is_open("ats") and not routine_work and not self.runner.kept and not self.running and time.monotonic() - self.ats_last_used > ATS_IDLE_SECONDS:
                    await self.browsers.close_browser("ats")
                if state and not self.running and not counts.get("running_claude"):
                    await self.browsers.close_extra_pages("linkedin", {self.session_page} if self.session_page else set())
                purge_artifacts()
            except Exception as e:
                log.warning("housekeeping failed: %s", e)
            await self._wait(60)

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.stopping.set)
        if not self.api.token:   # not switched on here yet: no browser, no visit to LinkedIn
            log.info("no CAREEROPS_WORKER_TOKEN: waiting, nothing runs")
            await self.stopping.wait()
            await self.api.close()
            return
        await self.browsers.start()
        loops = [self.lane_loop(lane) for lane in ("linkedin_read", "linkedin_write", "ats")]
        await asyncio.gather(*loops, self.session_loop(), self.housekeeping_loop())
        log.info("stopping: waiting for %d running action(s)", len(self.running))
        if self.running:
            await asyncio.wait(self.running, timeout=100)
        for task in list(self.running):
            task.cancel()
        await self.browsers.stop()
        await self.api.close()


def purge_artifacts() -> None:
    """Screenshots older than 30 days, and the documents of runs that ended long ago."""
    cutoff = time.time() - ARTIFACT_DAYS * 86400
    for root in (ARTIFACTS, RUN_DIR):
        if not root.is_dir():
            continue
        for folder in root.iterdir():
            if folder.is_dir() and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(Worker().run())
