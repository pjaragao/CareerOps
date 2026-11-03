import re
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.auth import APPROVER, BOT, WORKER, require, require_approver, require_decider
from app.core.config import settings
from app.services import content_guard
from app.services.automation_service import AutomationService as Auto
from app.services.bot_service import BotService
from app.services.email_monitor_service import EmailMonitorService
from app.services.job_search_service import JobSearchService

router = APIRouter(prefix="/automation", tags=["automation"])
require_worker = require(WORKER)
require_any = require(APPROVER, WORKER, BOT)
require_bot = require(BOT)


def _found(item):
    if not item:
        raise HTTPException(status_code=404, detail="Não encontrado, ou o estado atual não permite esta ação")
    return item


# ── Who you are, and the state of everything ─────────────────────────────
@router.get("/status")
async def status(role: str = Depends(require_any)):
    return {"ok": True, "role": role, **Auto.status()}


class StateIn(BaseModel):
    mode: Optional[Literal["off", "dry_run", "live"]] = None
    account_kind: Optional[Literal["test", "main"]] = None
    allow_final_submit: Optional[bool] = None
    ramp_step: Optional[int] = Field(None, ge=0, le=2)
    ramp_auto: Optional[bool] = None


@router.patch("/state", dependencies=[Depends(require_approver)])
async def update_state(req: StateIn):
    return Auto.update_state(req.mode, req.account_kind, req.allow_final_submit, req.ramp_step, req.ramp_auto)


class HaltIn(BaseModel):
    reason: str = Field("Parado por você", max_length=500)


@router.post("/halt", dependencies=[Depends(require_decider)])
async def halt(req: HaltIn):
    return Auto.halt(req.reason)


@router.post("/resume", dependencies=[Depends(require_decider)])
async def resume():
    return Auto.resume()


class LimitIn(BaseModel):
    step0: int = Field(..., ge=0, le=200)
    step1: int = Field(..., ge=0, le=200)
    step2: int = Field(..., ge=0, le=200)


@router.put("/limits/{kind}", dependencies=[Depends(require_approver)])
async def set_limit(kind: str, req: LimitIn):
    return _found(Auto.set_limit(kind, req.step0, req.step1, req.step2))


# ── A new browser of yours: a one-time link instead of typing the token ──
@router.post("/login-links", dependencies=[Depends(require_approver)])
async def login_link():
    return {"url": Auto.login_link()}


class RedeemIn(BaseModel):
    code: str = Field(..., min_length=10, max_length=100)


@router.post("/login-links/redeem")
async def redeem_login(req: RedeemIn):
    token = Auto.redeem_login(req.code)
    if not token:
        raise HTTPException(status_code=410, detail="Link já usado ou expirado: peça outro")
    return {"token": token}


# ── What you decide ──────────────────────────────────────────────────────
@router.get("/inbox", dependencies=[Depends(require_decider)])
async def inbox():
    return Auto.inbox()


class ApproveIn(BaseModel):
    text: Optional[str] = Field(None, max_length=3000)
    run_now: bool = False   # True = does not wait for the time window


@router.post("/actions/{action_id}/approve", dependencies=[Depends(require_decider)])
async def approve(action_id: int, req: ApproveIn):
    try:
        return _found(Auto.approve(action_id, req.text, req.run_now))
    except (ValueError, content_guard.BlockedContent) as e:
        raise HTTPException(status_code=422, detail=str(e))


class ReviseIn(BaseModel):
    instruction: str = Field(..., min_length=2, max_length=1000)
    text: Optional[str] = Field(None, max_length=3000)


@router.post("/actions/{action_id}/revise", dependencies=[Depends(require_decider)])   # Lolo too: it only rewrites a draft that still waits for approval
async def revise(action_id: int, req: ReviseIn):
    """A comment still to approve, rewritten by the AI with your request; it waits for your approval again."""
    try:
        return _found(await Auto.revise(action_id, req.instruction.strip(), req.text))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class BatchIn(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=100)
    run_now: bool = False


@router.post("/approve-batch", dependencies=[Depends(require_decider)])
async def approve_batch(req: BatchIn):
    approved, refused = [], []
    for action_id in req.ids:
        try:
            (approved if Auto.approve(action_id, run_now=req.run_now) else refused).append(action_id)
        except (ValueError, content_guard.BlockedContent):
            refused.append(action_id)
    return {"approved": approved, "refused": refused}


@router.post("/actions/{action_id}/reject", dependencies=[Depends(require_decider)])
async def reject(action_id: int):
    return _found(Auto.reject(action_id))


@router.post("/actions/{action_id}/approve-docs", dependencies=[Depends(require_decider)])
async def approve_docs(action_id: int):
    return _found(Auto.approve_docs(action_id))


@router.post("/actions/{action_id}/confirm-submit", dependencies=[Depends(require_decider)])
async def confirm_submit(action_id: int):
    return _found(Auto.confirm_submit(action_id))


@router.post("/actions/{action_id}/cancel", dependencies=[Depends(require_decider)])
async def cancel(action_id: int):
    return _found(Auto.cancel(action_id))


@router.post("/actions/{action_id}/retry", dependencies=[Depends(require_decider)])
async def retry(action_id: int):
    return _found(Auto.retry(action_id))


@router.post("/jobs/{job_id}/recover", dependencies=[Depends(require_decider)])
async def recover_job(job_id: int):
    return _found(Auto.recover_job(job_id))


@router.get("/needs-user", dependencies=[Depends(require_decider)])
async def needs_user():
    return {"items": Auto.needs_user()}


class AnswerIn(BaseModel):
    question: str = Field(..., max_length=500)
    answer: str = Field(..., max_length=3000)
    field_type: str = "text"
    save: bool = True


class AnswersIn(BaseModel):
    answers: List[AnswerIn] = Field(default_factory=list, max_length=50)


@router.post("/needs-user/{action_id}/answer", dependencies=[Depends(require_decider)])
async def answer(action_id: int, req: AnswersIn):
    return _found(Auto.answer(action_id, [a.model_dump() for a in req.answers]))


@router.get("/answers", dependencies=[Depends(require_approver)])
async def answers():
    return {"items": Auto.answers_list()}


@router.delete("/answers/{answer_id}", dependencies=[Depends(require_approver)])
async def delete_answer(answer_id: int):
    return _found(Auto.delete_answer(answer_id))


@router.get("/running", dependencies=[Depends(require_decider)])   # read-only: Lolo shows what is approved and waiting
async def running():
    return {"items": Auto.running()}


@router.get("/history", dependencies=[Depends(require_decider)])
async def history(limit: int = Query(100, ge=1, le=500)):
    return {"items": Auto.history(limit)}


@router.get("/actions/{action_id}/events", dependencies=[Depends(require_decider)])
async def events(action_id: int):
    return {"items": Auto.events(action_id)}


@router.get("/searches", dependencies=[Depends(require_approver)])
async def searches():
    return {"items": JobSearchService.list_searches()}


class SearchToggle(BaseModel):
    enabled: bool


@router.patch("/searches/{search_id}", dependencies=[Depends(require_approver)])
async def toggle_search(search_id: int, req: SearchToggle):
    return _found(JobSearchService.set_enabled(search_id, req.enabled))


# ── Your saved jobs on LinkedIn: when they are read (Configurações), and now (the button, or Lolo) ─────
class SavedImportIn(BaseModel):
    enabled: bool = True
    day_start: int = Field(8, ge=0, le=23)
    day_end: int = Field(24, ge=1, le=24)
    day_every: int = Field(1, ge=1, le=24)
    night_every: int = Field(2, ge=0, le=24)   # 0: nothing outside the day hours


@router.get("/saved-import", dependencies=[Depends(require_decider)])
async def saved_import():
    return Auto.saved_import_overview()


@router.put("/saved-import", dependencies=[Depends(require_approver)])
async def set_saved_import(req: SavedImportIn):
    return Auto.set_saved_import(req.enabled, req.day_start, req.day_end, req.day_every, req.night_every)


@router.post("/saved-import/run", dependencies=[Depends(require_decider)])
async def run_saved_import():
    return {**Auto.run_saved_import(), "mode": Auto.state().get("mode")}


# ── What the executors report ────────────────────────────────────────────
class ClaimIn(BaseModel):
    lane: Literal["linkedin_read", "linkedin_write", "ats"]
    worker: str = Field("worker", max_length=100)


@router.post("/claim", dependencies=[Depends(require_worker)])
async def claim(req: ClaimIn):
    return Auto.claim(req.lane, req.worker)


@router.get("/actions/{action_id}/run", dependencies=[Depends(require_worker)])
async def run_info(action_id: int, nonce: Optional[str] = None):
    return _found(Auto.run_info(action_id, nonce))


@router.post("/actions/{action_id}/heartbeat", dependencies=[Depends(require_worker)])
async def heartbeat(action_id: int):
    return _found(Auto.heartbeat(action_id))


class EventIn(BaseModel):
    source: str = Field("extension", max_length=30)
    event: str = Field(..., max_length=100)
    data: dict = {}
    level: Literal["info", "warning", "error"] = "info"
    screenshot: Optional[str] = Field(None, max_length=500)


@router.post("/actions/{action_id}/events", dependencies=[Depends(require_worker)])
async def add_event(action_id: int, req: EventIn):
    Auto.add_event(action_id, req.source, req.event, req.data, req.level, req.screenshot)
    return {"ok": True}


class ReadyIn(BaseModel):
    fields: list = []


@router.post("/actions/{action_id}/ready", dependencies=[Depends(require_worker)])
async def ready(action_id: int, req: ReadyIn):
    return _found(Auto.ready_to_submit(action_id, req.fields))


class CompleteIn(BaseModel):
    outcome: Literal["executed", "dry_run", "read"]
    data: dict = {}
    source: str = Field("extension", max_length=30)


@router.post("/actions/{action_id}/complete", dependencies=[Depends(require_worker)])
async def complete(action_id: int, req: CompleteIn):
    return _found(Auto.complete(action_id, req.outcome, req.data, req.source))


class VerifyIn(BaseModel):
    proof: bool
    evidence: dict = {}


@router.post("/actions/{action_id}/verify", dependencies=[Depends(require_worker)])
async def verify(action_id: int, req: VerifyIn):
    return _found(Auto.verify(action_id, req.proof, req.evidence))


class EscalateIn(BaseModel):
    code: str = Field(..., max_length=60)
    text: str = Field("", max_length=2000)
    questions: list = []
    source: str = Field("extension", max_length=30)
    screenshot: Optional[str] = Field(None, max_length=500)


@router.post("/actions/{action_id}/escalate", dependencies=[Depends(require_worker)])
async def escalate(action_id: int, req: EscalateIn):
    return _found(Auto.escalate(action_id, req.code, req.text, req.questions, req.source, req.screenshot))


class AbortIn(BaseModel):
    reason: str = Field("stopped", max_length=200)
    retry_after: int = Field(0, ge=0, le=3600)


@router.post("/actions/{action_id}/abort", dependencies=[Depends(require_worker)])
async def abort(action_id: int, req: AbortIn):
    return _found(Auto.abort(action_id, req.reason, req.retry_after))


class HandoffIn(BaseModel):
    url: str = Field(..., max_length=2000)


@router.post("/actions/{action_id}/handoff", dependencies=[Depends(require_worker)])
async def handoff(action_id: int, req: HandoffIn):
    return _found(Auto.handoff(action_id, req.url))


class IdsIn(BaseModel):
    ids: List[str] = Field(..., max_length=100)


@router.post("/discovered/unseen", dependencies=[Depends(require_worker)])
async def unseen(req: IdsIn):
    return JobSearchService.unseen(req.ids)


class DiscoveredJob(BaseModel):
    linkedin_job_id: str = Field(..., max_length=50)
    title: Optional[str] = Field(None, max_length=500)
    company: Optional[str] = Field(None, max_length=300)
    location: Optional[str] = Field(None, max_length=300)
    description: str = Field("", max_length=30000)
    posted: Optional[str] = Field(None, max_length=100)
    easy_apply: bool = False


class DiscoveredIn(BaseModel):
    jobs: List[DiscoveredJob] = Field(..., max_length=50)
    search: Optional[str] = Field(None, max_length=100)


@router.post("/discovered", dependencies=[Depends(require_worker)])
async def discovered(req: DiscoveredIn):
    return {"added": JobSearchService.add_discovered([j.model_dump() for j in req.jobs], req.search)}


class SavedJobsIn(BaseModel):
    jobs: List[DiscoveredJob] = Field(..., max_length=60)
    ids: List[str] = Field(..., max_length=200)


@router.post("/saved-jobs", dependencies=[Depends(require_worker)])
async def saved_jobs(req: SavedJobsIn):
    return JobSearchService.add_saved([j.model_dump() for j in req.jobs], req.ids)


class FollowTarget(BaseModel):
    url: str = Field(..., pattern=r"^https://www\.linkedin\.com/(in|company)/[^/?#]+")
    name: Optional[str] = Field(None, max_length=300)
    why: Optional[str] = Field("", max_length=500)
    market: Optional[str] = Field(None, max_length=10)


class FollowTargetsIn(BaseModel):
    targets: List[FollowTarget] = Field(..., max_length=10)


@router.post("/follow-targets", dependencies=[Depends(require_worker)])
async def follow_targets(req: FollowTargetsIn):
    made = [Auto.follow_target(t.url, t.name or "", t.why or "", t.market) for t in req.targets]
    return {"proposed": sum(bool(m) for m in made)}


@router.get("/worker-config", dependencies=[Depends(require_worker)])
async def worker_config():
    from app.services.automation_service import config
    cfg = config()
    return {"lanes": (cfg.get("automation") or {}).get("lanes") or {}, "external_apply": bool((cfg.get("jobs") or {}).get("external_apply"))}


class SessionIn(BaseModel):
    status: Literal["logged_in", "logged_out"]


@router.post("/session", dependencies=[Depends(require_worker)])
async def session(req: SessionIn):
    Auto.set_session(req.status)
    return {"ok": True}


@router.get("/actions/{action_id}/artifacts/{name}", dependencies=[Depends(require_decider)])
async def artifact(action_id: int, name: str):
    """A screenshot the worker kept of this action (the folder is shared with the backend)."""
    if not re.fullmatch(r"[\w.-]+\.(png|html)", name):
        raise HTTPException(status_code=404)
    path = settings.OUTPUT_DIR / "automation" / str(action_id) / name
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path)


class ClaudeClaimIn(BaseModel):
    runner: str = Field("claude-runner", max_length=100)


@router.post("/escalated/claim", dependencies=[Depends(require_worker)])
async def claude_claim(req: ClaudeClaimIn):
    return Auto.claude_claim(req.runner)


class ClaudeResultIn(BaseModel):
    run_id: int
    status: Literal["done", "needs_user", "failed"]
    summary: str = Field("", max_length=3000)
    questions: list = []
    audit_flags: list = []
    cost_usd: Optional[float] = None
    transcript: dict = {}


@router.post("/actions/{action_id}/claude-result", dependencies=[Depends(require_worker)])
async def claude_result(action_id: int, req: ClaudeResultIn):
    return _found(Auto.claude_result(action_id, req.run_id, req.status, req.summary, req.questions, req.audit_flags, req.cost_usd, req.transcript))


# ── Answers by email ─────────────────────────────────────────────────────
@router.get("/email/events", dependencies=[Depends(require_decider)])
async def email_events(limit: int = Query(100, ge=1, le=500)):
    return EmailMonitorService.events_view(limit)


@router.get("/email/funnel", dependencies=[Depends(require_decider)])
async def email_funnel():
    return EmailMonitorService.funnel()


class EmailReview(BaseModel):
    classification: Optional[str] = Field(None, max_length=30)
    job_id: Optional[int] = None


@router.post("/email/events/{event_id}/review", dependencies=[Depends(require_decider)])
async def email_review(event_id: int, req: EmailReview):
    return _found(EmailMonitorService.review(event_id, req.classification, req.job_id))


@router.post("/email/run", dependencies=[Depends(require_approver)])
async def email_run():
    import asyncio
    return await asyncio.to_thread(EmailMonitorService.run)


class IngestMessage(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=500)
    thread_id: Optional[str] = Field(None, max_length=500)
    sender: str = Field("", max_length=500)
    subject: str = Field("", max_length=1000)
    received_at: Optional[str] = Field(None, max_length=40)
    body: str = Field("", max_length=20000)


class IngestIn(BaseModel):
    messages: List[IngestMessage] = Field(..., max_length=300)
    source: str = Field("lolo", max_length=30)
    baseline: Optional[bool] = None   # the sender's first read, in parts: none of them changes a status


@router.post("/email/ingest", dependencies=[Depends(require_decider)])
async def email_ingest(req: IngestIn):
    """Messages Lolo read from Gmail with its own access: the same filter and reading as the IMAP check."""
    import asyncio
    return await asyncio.to_thread(EmailMonitorService.ingest, [m.model_dump() for m in req.messages], req.source, req.baseline)


class ArchivedIn(BaseModel):
    message_ids: List[str] = Field(..., min_length=1, max_length=300)


@router.post("/email/archived", dependencies=[Depends(require_decider)])
async def email_archived(req: ArchivedIn):
    """Lolo archived these in Gmail: they are not handed back to it again."""
    return {"marked": EmailMonitorService.mark_archived(req.message_ids)}


@router.get("/email/gmail-query", dependencies=[Depends(require_decider)])
async def email_gmail_query(days: int = Query(2, ge=1, le=60)):
    return {"query": EmailMonitorService.gmail_query(days)}


# ── Suggestions from the e-mails (grouped by theme) ──────────────────────
@router.get("/suggestions", dependencies=[Depends(require_decider)])
async def suggestions(status: Literal["new", "accepted", "dismissed"] = "new"):
    return {"groups": BotService.suggestions(status), "text": BotService.suggestions_text() if status == "new" else ""}


class SuggestionIn(BaseModel):
    status: Literal["new", "accepted", "dismissed"]


@router.patch("/suggestions/{suggestion_id}", dependencies=[Depends(require_decider)])
async def set_suggestion(suggestion_id: int, req: SuggestionIn):
    return _found(BotService.set_suggestion(suggestion_id, req.status))


# ── Lolo (WhatsApp) ──────────────────────────────────────────────────────
@router.get("/bot/notifications", dependencies=[Depends(require_bot)])
async def bot_notifications(limit: int = Query(20, ge=1, le=50)):
    return {"items": BotService.pending(limit)}


class AckIn(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=100)


@router.post("/bot/notifications/ack", dependencies=[Depends(require_bot)])
async def bot_ack(req: AckIn):
    return {"acked": BotService.ack(req.ids)}


@router.get("/bot/overview", dependencies=[Depends(require_decider)])
async def bot_overview():
    return {"text": BotService.overview_text()}


@router.get("/bot/inbox", dependencies=[Depends(require_decider)])
async def bot_inbox():
    return {"text": BotService.inbox_text()}


class CommentLinkIn(BaseModel):
    url: str = Field(..., max_length=1000)
    suggestion: str = Field("", max_length=1500)
    post_text: str = Field("", max_length=8000)
    author: str = Field("", max_length=200)


@router.post("/bot/comment-link", dependencies=[Depends(require_decider)])
async def bot_comment_link(req: CommentLinkIn):
    """A post you sent to be commented: the draft comes back and waits for your OK, like any other comment."""
    try:
        return await BotService.comment_link(req.url, req.suggestion, req.post_text, req.author)
    except (ValueError, content_guard.BlockedContent) as e:
        raise HTTPException(status_code=422, detail=str(e))
