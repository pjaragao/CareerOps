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

from . import ats_adapters, clicks, connect_engine, safety, verify
from .api import Api
from .browser import Browsers

log = logging.getLogger("worker.handlers")

ARTIFACTS = Path(os.environ.get("ARTIFACTS_DIR", "/app/output/automation"))
RUN_DIR = Path(os.environ.get("RUN_DIR", "/data/run"))
# How long an action may take with nothing new, in seconds. Waiting for your click has its own limit.
DEADLINES = {"apply": 480, "comment": 180, "follow": 120, "connect": 120, "search": 600, "check": 300, "feed_scan": 300, "follow_scan": 180, "saved_import": 600,
             "reply_scan": 180, "thread_read": 180, "reply": 180, "like": 120, "inbox_scan": 480, "message": 120}
CONFIRM_TIMEOUT = 1800
EXTERNAL_FORM_TIMEOUT = 300
POLL_SECONDS = 3
VERIFY_SETTLE_SECONDS = 6
HEARTBEAT_SECONDS = 30


DISCARD_LIKE = {"job_closed", "already_applied", "captcha"}
CLOSED_JOB_RE = re.compile(r"\b(?:no longer accepting applications|not currently accepting applications|this job (?:is )?(?:no longer|not) available|"
                           r"job posting (?:has )?(?:expired|been removed)|position has been filled|this (?:job|position) (?:has been|is) closed|"
                           r"vaga (?:encerrada|n[aã]o est[aá] mais dispon[ií]vel)|cette offre n['’]est plus disponible|"
                           r"la oferta (?:ya )?no est[aá] disponible|stelle (?:ist )?nicht mehr verf[uü]gbar)\b", re.I)
TITLE_STOP = {"senior", "junior", "lead", "manager", "engineer", "analyst", "specialist", "remote", "hybrid", "full", "time",
              "with", "and", "the", "for", "all", "genders", "from", "home", "global", "team", "role"}


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

    async def precheck(self, page: Page, action: dict, code: str) -> Optional[tuple]:
        """Before a company form goes to the Claude routine (token plan, phase 0): a closed job or a page that is plainly
        another job is decided here, with no model run. Returns (code, text) to report instead, or None."""
        if action["lane"] != "ats" or action["kind"] != "apply" or code in DISCARD_LIKE:
            return None
        _, title, text = await self._page_state(page)
        body = f"{title}\n{text}"[:20000]
        if CLOSED_JOB_RE.search(body):
            return "job_closed", "A página informa que a vaga foi encerrada (checado antes do Claude)."
        payload = action.get("payload") or {}
        if code != "external_form_unfinished" or len(text) < 800:
            return None   # a login or account page carries no job title: nothing to compare
        low = body.lower()
        company = str(payload.get("company") or "").strip().lower()
        words = [w for w in re.findall(r"[a-zà-ÿ0-9&+#]{4,}", str(payload.get("title") or "").lower()) if w not in TITLE_STOP]
        if company and company in low:
            return None
        if words and sum(w in low for w in words) == 0:
            return "wrong_page", (f"A página aberta não menciona a vaga ({payload.get('title') or ''} · {payload.get('company') or ''}): "
                                  "confira o link antes de gastar uma execução do Claude.")
        return None

    async def report_stop(self, page: Page, action: dict, code: str, text: str = "") -> None:
        checked = await self.precheck(page, action, code)
        if checked:
            code, text = checked
        shot = await self.artifact(page, action["id"], code)
        await self.api.post(f"/automation/actions/{action['id']}/escalate", {"code": code, "text": text, "source": "worker", "screenshot": shot})

    async def run_verify(self, page: Page, action: dict, engine: bool = False) -> None:
        proof, evidence = await verify.prove(page, action)
        # the extension's flow reached the final click and nothing shows: when the profile still offers Connect, nothing went
        # out, and the worker sends it itself (connect_engine: Playwright and the mouse). Only right after that click, once
        if not proof and engine and action["kind"] == "connect" and action["lane"] != "ats" and not await self.stop_sign(page):
            said, offered = await connect_engine.fallback(page, action)
            await self.api.post(f"/automation/actions/{action['id']}/events", {"source": "worker", "event": "connect_engine", "data": {"said": said}})
            if said.startswith("sent") or offered:
                if said.startswith("sent"):
                    await page.wait_for_timeout(VERIFY_SETTLE_SECONDS * 1000)
                proof, evidence = await verify.prove(page, action)
                evidence = {**evidence, "engine": said[:300]}
                # the profile was reloaded, the sent list read, and Connect is still offered: nothing went out, also after
                # the engine's own click. Said so, and the backend sends it to the Claude routine instead of asking you to look
                if not proof and (await connect_engine.offers_connect(page, clicks.profile_slug(action["target_url"])))[0]:
                    evidence = {**evidence, "not_sent": True}
        stop = await self.stop_sign(page)
        if stop and action["lane"] != "ats":
            await self.report_stop(page, action, stop, "Página de verificação do LinkedIn")
            return
        shot_page = page
        if action["lane"] == "ats" and (not getattr(page, "url", "") or page.url == "about:blank"):
            ctx = getattr(page, "context", None)
            if ctx is not None:
                target_url = evidence.get("url")
                candidates = [
                    p for p in reversed(list(getattr(ctx, "pages", ())))
                    if not (hasattr(p, "is_closed") and p.is_closed()) and getattr(p, "url", "") and p.url != "about:blank"
                ]
                same = [p for p in candidates if verify.same_site(p.url, action.get("target_url") or "")]
                shot_page = next((p for p in same if target_url and p.url == target_url), same[0] if same else page)
        shot = await self.artifact(shot_page, action["id"], "proof" if proof else "no-proof")
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
                if action["lane"] == "ats" and stop in ("account_required", "email_verification"):
                    self.kept[action["id"]] = page
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
        clicked: set = set()   # the real clicks the extension asked for (clicks.py): each at most once
        form = {"sig": None, "steps": 0, "since": None, "recipe": None, "labels": []}   # deterministic ATS navigation
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
                await self.settle(page, action, clicked)
                # the page as the click left it (a dialog still open, a warning): the check reloads it and that is lost
                await self.artifact(page, action_id, "after-click")
                await self.run_verify(page, action, engine=True)
                return
            # the form stays open for the Claude routine; also when the routine was quicker than this loop and already sent it
            # (unknown_outcome): the page that proves it is this one, and the check that follows picks it up from self.kept
            if status in ("escalated", "running_claude", "unknown_outcome") and action["lane"] == "ats":
                await self._remove_copilot_overlay(page)
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
                if action["lane"] == "ats" and stop in ("account_required", "email_verification"):
                    await self._remove_copilot_overlay(page)
                    self.kept[action["id"]] = page
                await self.report_stop(page, action, stop)
                return
            await clicks.serve(page, action, status, clicked)
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
            if action["lane"] == "ats" and action["kind"] == "apply":
                outcome = await self.drive_form(page, action, info, form)
                if outcome == "stop":
                    return
                if outcome == "progress":
                    form_since = time.monotonic()
            if action["lane"] == "ats" and now - form_since > EXTERNAL_FORM_TIMEOUT:
                await self.report_stop(page, action, "external_form_unfinished", "O preenchimento não terminou a tempo")
                await self._remove_copilot_overlay(page)
                self.kept[action_id] = page
                return
            if now - started > DEADLINES.get(action["kind"], 300):
                await self.report_stop(page, action, "step_stuck", "A extensão não terminou a tempo")
                return

    async def drive_form(self, page: Page, action: dict, info: dict, form: dict) -> Optional[str]:
        """After the extension filled a step with nothing pending, presses Next / Submit itself (ats_adapters.py), with
        no LLM. Returns "progress" after a Next, "stop" once it handed the form on (submitted, or escalated), else None.
        A step it cannot move on goes to the Claude routine with the form kept open, as before."""
        action_id = action["id"]
        state = await ats_adapters.ready_state(page)
        idle = form["since"] is not None and time.monotonic() - form["since"] > 15
        if state is None and not idle:
            return None
        if state is not None and state.get("sig") == form["sig"] and not idle:
            return None
        if state is not None:
            form["sig"] = state.get("sig")
            if state.get("pending") or not int(state.get("filled") or 0):
                return None   # fields left, or none found: the extension escalates it (managedFilled), never a Submit here
        elif form["steps"] == 0:
            return None   # the idle path is only for a step reached by a Next of ours (a review page with no fields)
        if form["recipe"] is None:
            host = ats_adapters.host_of(page.url)
            form["recipe"] = (await self.api.get(f"/automation/recipes/{host}") or {}).get("recipe") or {}
        ad = ats_adapters.adapter_for(page.url, form["recipe"])
        res = await ats_adapters.step(page, ad)
        if res.outcome == "stuck":
            await self._hand_on(page, action, f"{res.reason}" + (f": {'; '.join(res.errors)[:300]}" if res.errors else ""))
            return "stop"
        if res.outcome == "next":
            here = (page.url.split("#")[0], res.label)
            if form.get("last") == here:   # the same button on the same page again: it does not move the form on
                await self._hand_on(page, action, f"o botão \"{res.label}\" não avançou o formulário")
                return "stop"
            form["last"] = here
            if form["steps"] >= 12:
                await self._hand_on(page, action, "o formulário passou de 12 etapas sem chegar ao envio")
                return "stop"
            await res.element.click(timeout=8000)
            form["steps"] += 1
            form["labels"].append(("next", res.label))
            form["since"] = time.monotonic()
            await self.api.post(f"/automation/actions/{action_id}/events", {"source": "worker", "event": "ats_next", "data": {"adapter": ad.name, "label": res.label, "step": form["steps"]}})
            return "progress"
        # Submit: only with the final click allowed and nothing waiting for your confirmation
        if not info.get("allow_final") or (info.get("confirm_required") and not info.get("confirmed")):
            await self._hand_on(page, action, "Formulário pronto para enviar; o envio final não está liberado para o worker")
            return "stop"
        await res.element.click(timeout=8000)
        await page.wait_for_timeout(VERIFY_SETTLE_SECONDS * 1000)
        errors = await ats_adapters.page_errors(page)
        if errors:
            await self._hand_on(page, action, f"o envio mostrou erro na página: {'; '.join(errors)[:300]}")
            return "stop"
        form["labels"].append(("submit", res.label))
        host = ats_adapters.host_of(page.url)
        await self.api.post(f"/automation/recipes/{host}", {"adapter": ad.name, "next": [l for k, l in form["labels"] if k == "next"],
                                                             "submit": [l for k, l in form["labels"] if k == "submit"]})
        await self.api.post(f"/automation/actions/{action_id}/complete", {"outcome": "executed", "source": "worker",
                                                                          "data": {"engine": "ats_adapter", "adapter": ad.name, "steps": form["steps"]}})
        return None   # the loop sees "verifying" and proves it on this page

    async def _hand_on(self, page: Page, action: dict, text: str) -> None:
        """The form goes to the Claude routine as it is, kept open (the old way, now only for what the adapter cannot do)."""
        await self._remove_copilot_overlay(page)
        self.kept[action["id"]] = page
        await self.report_stop(page, action, "external_form_unfinished", text)

    async def settle(self, page: Page, action: dict, clicked: set) -> None:
        """The wait after the final click. The extension may still ask for the real click that sends (clicks.py): done here,
        and then the full wait again before the page is looked at."""
        end = time.monotonic() + VERIFY_SETTLE_SECONDS
        while time.monotonic() < end:
            await asyncio.sleep(1)
            if await clicks.serve(page, action, "verifying", clicked):
                end = time.monotonic() + VERIFY_SETTLE_SECONDS

    async def _remove_copilot_overlay(self, page: Page) -> None:
        """Removes the copilot overlay from all frames before handing the tab to Playwright MCP."""
        for frame in page.frames:
            try:
                await frame.evaluate("document.getElementById('careerops-apply-copilot')?.remove()")
            except Exception:
                pass

    async def release_kept(self) -> None:
        """Forms the Claude routine already handled, or that left the queue."""
        for action_id, page in list(self.kept.items()):
            info = await self.api.get(f"/automation/actions/{action_id}/run")
            if not info or info["status"] not in ("escalated", "running_claude", "unknown_outcome", "verifying"):
                self.kept.pop(action_id, None)
                if not page.is_closed():
                    await page.close()
