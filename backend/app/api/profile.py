from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from typing import List, Optional, Dict, Any
from app.services.profile_service import ProfileService
from pydantic import BaseModel
import json

router = APIRouter(prefix="/profile", tags=["profile"])

@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    content = await file.read()
    extracted = await ProfileService.extract_info_from_resume(content, file.filename)
    return extracted

class ProfileUpdate(BaseModel):
    profile: Dict[str, Any]

class ResumeUpdate(BaseModel):
    content: str

class OptimizeRequest(BaseModel):
    section: str
    content: str

@router.get("")
async def get_profile():
    return ProfileService.get_profile()

@router.post("")
async def save_profile(profile: Dict[str, Any]):
    ProfileService.save_profile(profile)
    return {"ok": True}

@router.get("/resume")
async def get_resume():
    return {"content": ProfileService.get_resume_base()}

@router.post("/resume")
async def save_resume(data: ResumeUpdate):
    ProfileService.save_resume_base(data.content)
    return {"ok": True}

@router.get("/status")
async def get_status():
    stats = ProfileService.get_latest_stats()
    return {"stats": stats}

@router.post("/optimize")
async def optimize(req: OptimizeRequest):
    result = await ProfileService.optimize_section(req.section, req.content)
    return {"result": result}

@router.post("/import-linkedin")
async def import_linkedin():
    extracted = await ProfileService.import_from_linkedin()
    return extracted

class ContentRequest(BaseModel):
    content: str

@router.post("/score")
async def score_profile(req: ContentRequest):
    return await ProfileService.get_profile_score(req.content)

@router.post("/ssi")
async def ssi_plan(req: ContentRequest):
    result = await ProfileService.generate_ssi_plan(req.content)
    return {"result": result}

@router.post("/import-extension-ai")
async def import_extension_ai(data: Dict[str, Any]):
    try:
        await ProfileService.import_profile_ai(data.get("raw_text", ""))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/import-extension")
async def import_extension(request: Request):
    try:
        # Manually parse body to be resilient to missing Content-Type (CORS bypass)
        body_bytes = await request.body()
        data = json.loads(body_bytes.decode("utf-8"))
        await ProfileService.save_profile_from_extension(data)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
