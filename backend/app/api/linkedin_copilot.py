import io
import json
import zipfile
from datetime import date, datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from urllib.parse import quote

from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.linkedin_api_service import LinkedInApiError, LinkedInApiService
from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot

router = APIRouter(prefix="/linkedin-copilot", tags=["linkedin-copilot"])


def _found(item):
    if not item:
        raise HTTPException(status_code=404, detail="Not found or not in a state that allows this action")
    return item


# ── OAuth / connection ───────────────────────────────────────────────────
@router.get("/status")
async def status():
    return LinkedInApiService.status()


@router.get("/oauth/start")
async def oauth_start():
    try:
        return {"url": LinkedInApiService.authorization_url()}
    except LinkedInApiError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/oauth/callback")
async def oauth_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None,
                         error_description: Optional[str] = None):
    target = f"{settings.FRONTEND_URL}/linkedin-copilot"
    if error or not code or not state:
        return RedirectResponse(f"{target}?linkedin=error&reason={quote(error_description or error or 'missing_code')}")
    try:
        LinkedInApiService.handle_callback(code, state)
    except LinkedInApiError as e:
        return RedirectResponse(f"{target}?linkedin=error&reason={quote(str(e)[:200])}")
    return RedirectResponse(f"{target}?linkedin=connected")


@router.post("/disconnect")
async def disconnect():
    LinkedInApiService.disconnect()
    return {"ok": True}


# ── Profile copy (field-by-field texts the extension fills into LinkedIn's edit forms) ──
@router.get("/profile-copy")
async def profile_copy():
    path = settings.CONFIG_DIR / "linkedin_profile.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="config/linkedin_profile.json not found — run international/build_linkedin_profile.py")
    return json.loads(path.read_text(encoding="utf-8"))


# ── Browser extension download (zip built from the extension folder baked into the image) ──
EXTENSION_FILES = ["manifest.json", "background.js", "content.js", "content.css", "profile_filler.js", "linkedin_assist.js", "urn_bridge.js", "apply_copilot.js", "popup.html", "popup.js"]


def _extension_dir():
    path = settings.PROJECT_DIR / "extension"
    if not (path / "manifest.json").exists():
        raise HTTPException(status_code=404, detail="Extension folder not found in the backend image")
    return path


@router.get("/extension/info")
async def extension_info():
    return {"version": json.loads((_extension_dir() / "manifest.json").read_text(encoding="utf-8"))["version"]}


@router.get("/extension/download")
async def extension_download():
    root = _extension_dir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # one top-level folder, so "Extract here" gives the folder to select in chrome://extensions
        for name in EXTENSION_FILES:
            z.write(root / name, f"careerops-extension/{name}")
        for icon in sorted((root / "icons").iterdir()):
            z.write(icon, f"careerops-extension/icons/{icon.name}")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="careerops-extension.zip"'})


# ── Posts ────────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    market: Literal["br", "intl"] = "intl"
    inspiration_id: Optional[int] = None
    count: int = Field(2, ge=1, le=5)
    pillar: Optional[str] = None
    topic: Optional[str] = None
    source_notes: Optional[str] = None


class PostUpdate(BaseModel):
    body: Optional[str] = None
    scheduled_for: Optional[datetime] = None


class ApproveRequest(BaseModel):
    scheduled_for: Optional[datetime] = None


@router.get("/posts")
async def list_posts(status: Optional[str] = None):
    return {"posts": Copilot.list_posts(status)}


@router.post("/posts/generate")
async def generate_posts(req: GenerateRequest):
    try:
        return {"posts": await Copilot.generate_posts(req.count, req.pillar, req.topic, req.source_notes, req.market, req.inspiration_id)}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.patch("/posts/{post_id}")
async def update_post(post_id: int, req: PostUpdate):
    return _found(Copilot.update_post(post_id, req.body, req.scheduled_for))


@router.post("/posts/{post_id}/approve")
async def approve_post(post_id: int, req: ApproveRequest):
    return _found(Copilot.approve_post(post_id, req.scheduled_for))


@router.post("/posts/{post_id}/unapprove")
async def unapprove_post(post_id: int):
    return _found(Copilot.unapprove_post(post_id))


@router.post("/posts/{post_id}/publish")
async def publish_post(post_id: int):
    try:
        return Copilot.publish_post(post_id)
    except LinkedInApiError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/posts/{post_id}/mark-published")
async def mark_published(post_id: int):
    return _found(Copilot.mark_published_manually(post_id))


@router.delete("/posts/{post_id}")
async def discard_post(post_id: int):
    return _found(Copilot.discard_post(post_id))


# ── Inspirations (topics of interest saved from the feed) ────────────────
class InspirationIn(BaseModel):
    post_text: str = Field(..., min_length=20)
    post_url: Optional[str] = None
    author_name: Optional[str] = None
    author_headline: Optional[str] = None
    note: Optional[str] = None


@router.get("/inspirations")
async def list_inspirations():
    return {"items": Copilot.list_inspirations()}


@router.post("/inspirations")
async def add_inspiration(req: InspirationIn):
    return Copilot.add_inspiration(req.post_text, req.post_url, req.author_name, req.author_headline, req.note)


@router.delete("/inspirations/{item_id}")
async def delete_inspiration(item_id: int):
    return _found(Copilot.delete_inspiration(item_id))


# ── Engagement ───────────────────────────────────────────────────────────
class EngagementIn(BaseModel):
    post_text: str = Field(..., min_length=20)
    post_url: Optional[str] = None
    author_name: Optional[str] = None
    author_headline: Optional[str] = None
    other_comments: Optional[str] = None
    instruction: Optional[str] = None
    regenerate: bool = False


class EngagementUpdate(BaseModel):
    status: Optional[Literal["pending", "done", "skipped"]] = None
    comment_draft: Optional[str] = None


@router.get("/engagement")
async def engagement_queue():
    return Copilot.engagement_queue()


@router.post("/engagement")
async def add_engagement(req: EngagementIn):
    try:
        return await Copilot.add_engagement(req.post_text, req.post_url, req.author_name, req.author_headline,
                                            req.other_comments, req.instruction, req.regenerate)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


class ReplyIn(BaseModel):
    post_text: str = Field(..., min_length=10)
    target_text: str = Field(..., min_length=1)
    thread: Optional[str] = None
    target_author: Optional[str] = None
    my_comment: Optional[str] = None
    my_name: Optional[str] = None
    author_name: Optional[str] = None
    instruction: Optional[str] = None
    previous_draft: Optional[str] = None


@router.post("/engagement/reply")
async def draft_reply(req: ReplyIn):
    """Drafts an answer to a reply in a comment thread (not stored: the extension inserts it and you send it)."""
    try:
        return await Copilot.draft_reply(**req.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.patch("/engagement/{item_id}")
async def update_engagement(item_id: int, req: EngagementUpdate):
    return _found(Copilot.update_engagement(item_id, req.status, req.comment_draft))


# ── Prospects ────────────────────────────────────────────────────────────
class ProspectIn(BaseModel):
    profile_text: str = Field(..., min_length=20)
    profile_url: Optional[str] = None
    name: Optional[str] = None
    headline: Optional[str] = None
    company: Optional[str] = None


class ProspectUpdate(BaseModel):
    status: Optional[Literal["to_contact", "invited", "accepted", "replied", "skipped"]] = None
    note_draft: Optional[str] = None
    notes: Optional[str] = None


@router.get("/prospects")
async def list_prospects(status: Optional[str] = None):
    return Copilot.list_prospects(status)


@router.post("/prospects")
async def add_prospect(req: ProspectIn):
    try:
        return await Copilot.add_prospect(req.profile_text, req.profile_url, req.name, req.headline, req.company)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


class PersonIn(BaseModel):
    profile_url: str
    name: Optional[str] = None
    headline: Optional[str] = None


class PeopleBatchIn(BaseModel):
    people: List[PersonIn] = Field(..., min_length=1, max_length=40)
    topic: Optional[str] = Field(None, max_length=600)   # the saved post they were found on


@router.post("/prospects/batch")
async def score_people(req: PeopleBatchIn):
    """Scores the people visible on a LinkedIn list page (search, My Network) and stores them as prospects."""
    try:
        return {"items": await Copilot.score_people([p.model_dump() for p in req.people], req.topic)}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


class SeenPerson(BaseModel):
    name: Optional[str] = Field(None, max_length=300)
    profile_url: Optional[str] = None
    replied: bool = False


class ProspectCheckIn(BaseModel):
    connections: List[SeenPerson] = Field(default_factory=list, max_length=1000)
    conversations: List[SeenPerson] = Field(default_factory=list, max_length=500)
    sent: List[SeenPerson] = Field(default_factory=list, max_length=1000)


@router.post("/prospects/check")
async def check_prospects(req: ProspectCheckIn):
    """Prospects found among your sent invitations → invited; in your connections → accepted; replying in Messaging →
    replied. The extension reads those three lists on LinkedIn (no profile is opened, nothing is clicked)."""
    dump = lambda people: [p.model_dump() for p in people]
    return Copilot.check_prospects(dump(req.connections), dump(req.conversations), dump(req.sent))


@router.patch("/prospects/{item_id}")
async def update_prospect(item_id: int, req: ProspectUpdate):
    return _found(Copilot.update_prospect(item_id, req.status, req.note_draft, req.notes))


# ── Capture from the browser extension (user-triggered only) ─────────────
class CaptureIn(BaseModel):
    url: str
    text: str = Field(..., min_length=20)
    title: Optional[str] = None


class EasyApplyField(BaseModel):
    key: str
    type: Literal["text", "textarea", "number", "select", "radio", "checkbox"] = "text"
    label: str = ""
    options: List[str] = []
    current: Optional[str] = None


class EasyApplyIn(BaseModel):
    job: dict = {}
    fields: List[EasyApplyField] = Field(..., max_length=40)


@router.post("/easy-apply/answers")
async def easy_apply_answers(req: EasyApplyIn):
    """Answers for one step of a LinkedIn Easy Apply form. The extension fills them in; the user reviews and submits."""
    try:
        return await Copilot.easy_apply_answers(req.job, [f.model_dump() for f in req.fields])
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/capture")
async def capture(req: CaptureIn):
    try:
        return await Copilot.capture(req.url, req.text, req.title)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Weekly metrics ───────────────────────────────────────────────────────
class WeeklyMetricsIn(BaseModel):
    profile_views: Optional[int] = None
    search_appearances: Optional[int] = None
    post_impressions: Optional[int] = None
    recruiter_messages: Optional[int] = None
    interviews: Optional[int] = None
    notes: Optional[str] = None


@router.get("/metrics")
async def weekly_metrics(weeks: int = 8):
    return {"weeks": Copilot.weekly_summary(min(max(weeks, 1), 26))}


@router.put("/metrics/{week_start}")
async def save_weekly_metrics(week_start: date, req: WeeklyMetricsIn):
    return Copilot.save_weekly_metrics(week_start, req.model_dump())
