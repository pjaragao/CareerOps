"""One action in one window: open it, watch it, report it. The extension does the work on the page and tells the backend; this
side looks at every page for a stop sign, keeps the lease alive, proves what was written, and closes the window."""
import asyncio
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional

from playwright.async_api import Error as PlaywrightError, Page

from . import safety, verify
from .api import Api
from .browser import Browsers

log = logging.getLogger("worker.handlers")

ARTIFACTS = Path(os.environ.get("ARTIFACTS_DIR", "/app/output/automation"))
RUN_DIR = Path(os.environ.get("RUN_DIR", "/data/run"))
# How long an action may take with nothing new, in seconds. Waiting for your click has its own limit.
DEADLINES = {"apply": 480, "comment": 180, "follow": 120, "connect": 120, "search": 300, "check": 300, "feed_scan": 300, "follow_scan": 180, "saved_import": 600}
CONFIRM_TIMEOUT = 1800
EXTERNAL_FORM_TIMEOUT = 300
POLL_SECONDS = 3
VERIFY_SETTLE_SECONDS = 6
HEARTBEAT_SECONDS = 30


def browser_of(lane: str) -> str:
    return "ats" if lane == "ats" else "linkedin"


def run_url(action: dict) -> str:
    """The address with what lets the extension ask the backend about this action."""
    url = (action["target_url"] or "").split("#")[0]
    marker = f"careerops-run={action['id']}.{action['nonce']}"
    if action["lane"] == "ats":   # apply_copilot.js fills the form on company sites
        return f"{url}#careerops-apply={action['target_id']}&{marker}"
    return f"{url}#{marker}"


class Runner:
    def __init__(self, api: Api, browsers: Browsers):
        self.api = api
        self.browsers = browsers
        # Company-site forms stay open for the Claude routine, which picks them up with what was filled in
        self.kept: Dict[int, Page] = {}

    async def _page_state(self, page: Page) -> tuple:
        try:
            return page.url, await page.title(), await page.evaluate("() => (document.body && document.body.innerText) || ''")
        except PlaywrightError:   # navigating right now
            return page.url, "", ""

    async def stop_sign(self, page: Page, http_status: Optional[int] = None) -> Optional[str]:
        url, title, text = await self._page_state(page)
        return safety.classify(url, title, text, http_status)

    async def artifact(self, page: Page, action_id: int, label: str) -> Optional[str]:
        """A screenshot and the page without its scripts, for you to see what happened. Kept 30 days (main.purge_artifacts)."""
        folder = ARTIFACTS / str(action_id)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            name = f"{int(time.time())}-{label}"
            await page.screenshot(path=str(folder / f"{name}.png"), timeout=15000)
        except (PlaywrightError, OSError) as e:
            log.info("no screenshot for %s: %s", action_id, e)
            return None
        try:   # the screenshot stands on its own: the page may be navigating, and then there is no HTML to read
            html = re.sub(r"(?is)<script.*?</script>", "", await page.content())
            (folder / f"{name}.html").write_text(html, encoding="utf-8")
        except (PlaywrightError, OSError) as e:
            log.info("no page copy for %s: %s", action_id, e)
        return f"{name}.png"

    async def prepare_documents(self, action: dict) -> None:
        """The CV and cover letter where the browser tools can reach them, in case the Claude routine has to finish this."""
        folder = RUN_DIR / str(action["id"])
        folder.mkdir(parents=True, exist_ok=True)
        for kind in ("resume", "cover"):
            doc = await self.api.download(f"/jobs/{action['target_id']}/document.pdf?kind={kind}")
            if doc:
                (folder / Path(doc[0]).name).write_bytes(doc[1])

    async def report_stop(self, page: Page, action: dict, code: str, text: str = "") -> None:
        shot = await self.artifact(page, action["id"], code)
        await self.api.post(f"/automation/actions/{action['id']}/escalate", {"code": code, "text": text, "source": "worker", "screenshot": shot})

    async def run_verify(self, page: Page, action: dict) -> None:
        proof, evidence = await verify.prove(page, action)
        stop = await self.stop_sign(page)
        if stop and action["lane"] != "ats":
            await self.report_stop(page, action, stop, "Página de verificação do LinkedIn")
            return
        shot = await self.artifact(page, action["id"], "proof" if proof else "no-proof")
        await self.api.post(f"/automation/actions/{action['id']}/verify", {"proof": proof, "evidence": {**evidence, "screenshot": shot}})

    async def handle(self, action: dict) -> None:
        """Runs one claimed action to its end. Whatever goes wrong here, the backend's lease decides what it means."""
        page = self.kept.pop(action["id"], None) if action.get("verify_only") else None
        if page is None:
            try:
                page = await self.browsers.new_window(browser_of(action["lane"]))
            except Exception as e:   # the browser is not up: nothing happened on any page, and nothing is assumed
                log.warning("action %s: no browser: %s", action["id"], e)
                await self.api.post(f"/automation/actions/{action['id']}/abort", {"reason": "no browser", "retry_after": 120})
                return
        try:
            if action.get("verify_only"):
                await self.run_verify(page, action)
                return
            if action["kind"] == "apply":
                await self.prepare_documents(action)
            external = asyncio.Queue()
            page.on("popup", lambda p: external.put_nowait(p))
            response = await self.open(page, action)
            stop = await self.stop_sign(page, response.status if response else None)
            if stop:
                await self.report_stop(page, action, stop)
                return
            await self.keep_marker(page, action)
            await self.watch(page, action, external)
        except PlaywrightError as e:
            log.warning("action %s: browser error: %s", action["id"], e)
            if action.get("verify_only"):   # looking failed, so nothing is known yet: look again later
                await self.api.post(f"/automation/actions/{action['id']}/abort", {"reason": "verify failed", "retry_after": 120})
            else:
                await self.api.post(f"/automation/actions/{action['id']}/escalate", {"code": "unexpected_layout", "text": str(e)[:500], "source": "worker"})
        except Exception:
            log.exception("action %s failed in the worker", action["id"])
            await self.api.post(f"/automation/actions/{action['id']}/abort", {"reason": "worker error", "retry_after": 120})
        finally:
            if page is not None and not page.is_closed() and action["id"] not in self.kept:
                await page.close()

    async def open(self, page: Page, action: dict):
        """Opens the action's page, also when the page redirects itself while loading."""
        url = run_url(action)
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightError as e:
            # a redirect done by the page itself aborts the first navigation: what matters is where it landed
            if "ERR_ABORTED" not in str(e) or not page.url.startswith("http"):
                raise
            response = None
            await page.wait_for_load_state("domcontentloaded", timeout=60000)
        return response

    async def keep_marker(self, page: Page, action: dict) -> None:
        """LinkedIn's newer pages rewrite their address as they load (the job search goes to /jobs/search-results/ and
        drops the #fragment): the marker is put back for the extension, which listens for it. Only after the page was
        checked for a warning, so a checkpoint page never gets the extension started on it."""
        target, marker = run_url(action).split("#", 1)
        await page.wait_for_timeout(2500)
        # only when the page itself changed its address: the extension also drops the marker once it has started (and a
        # page reloaded by a click is the same address), and starting it twice must never happen
        if marker not in page.url and page.url.split("#")[0] != target:
            log.info("action %s: the page dropped its #fragment; putting it back", action["id"])
            await page.evaluate("m => { location.hash = m }", marker)

    async def watch(self, page: Page, action: dict, external: asyncio.Queue) -> None:
        action_id = action["id"]
        started = time.monotonic()
        last_heartbeat = 0.0
        waiting_since = None
        form_since = time.monotonic()
        while True:
            await asyncio.sleep(POLL_SECONDS)
            now = time.monotonic()
            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                info = await self.api.post(f"/automation/actions/{action_id}/heartbeat")
                last_heartbeat = now
            else:
                info = await self.api.get(f"/automation/actions/{action_id}/run")
            if not info:
                return
            if info["halted"]:   # you stopped it, or a warning stopped the lane: the window closes now
                await self.artifact(page, action_id, "halted")
                await self.api.post(f"/automation/actions/{action_id}/abort", {"reason": "halted"})
                return
            status = info["status"]
            if status == "verifying":   # said right before the final click: give it time to land before looking
                await asyncio.sleep(VERIFY_SETTLE_SECONDS)
                await self.run_verify(page, action)
                return
            # the form stays open for the Claude routine; also when the routine was quicker than this loop and already sent it
            # (unknown_outcome): the page that proves it is this one, and the check that follows picks it up from self.kept
            if status in ("escalated", "running_claude", "unknown_outcome") and action["lane"] == "ats":
                self.kept[action_id] = page
                return
            if status == "awaiting_confirm":
                waiting_since = waiting_since or now
                if now - waiting_since > CONFIRM_TIMEOUT:
                    await self.report_stop(page, action, "confirm_timeout", "Sem confirmação em 30 minutos: nada foi enviado")
                    return
                continue
            if status != "running_ext":   # done, in the queue again, or with you
                if status in ("needs_user", "escalated") and page.url and not page.is_closed():
                    await self.artifact(page, action_id, status)
                return
            stop = await self.stop_sign(page)
            if stop:
                await self.report_stop(page, action, stop)
                return
            if not external.empty():   # "Apply" on the company site opened a window: its address goes to the queue
                popup = await external.get()
                try:
                    await popup.wait_for_load_state("domcontentloaded", timeout=30000)
                    target = popup.url
                finally:
                    await popup.close()
                if safety.is_linkedin(target):
                    continue
                await self.api.post(f"/automation/actions/{action_id}/handoff", {"url": target})
                return
            if action["lane"] == "ats" and now - form_since > EXTERNAL_FORM_TIMEOUT:
                await self.report_stop(page, action, "external_form_unfinished", "O preenchimento não terminou a tempo")
                self.kept[action_id] = page
                return
            if now - started > DEADLINES.get(action["kind"], 300):
                await self.report_stop(page, action, "step_stuck", "A extensão não terminou a tempo")
                return

    async def release_kept(self) -> None:
        """Forms the Claude routine already handled, or that left the queue."""
        for action_id, page in list(self.kept.items()):
            info = await self.api.get(f"/automation/actions/{action_id}/run")
            if not info or info["status"] not in ("escalated", "running_claude", "unknown_outcome", "verifying"):
                self.kept.pop(action_id, None)
                if not page.is_closed():
                    await page.close()
