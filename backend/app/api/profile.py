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

class SkillsAnalysisRequest(BaseModel):
    target_role: str

@router.post("/analyze-skills")
async def analyze_skills(req: SkillsAnalysisRequest):
    profile = ProfileService.get_profile()
    return await ProfileService.analyze_skills(profile, req.target_role)

class ExperienceOptimizeRequest(BaseModel):
    lang: str = "pt"

@router.post("/optimize-experience")
async def optimize_experience(req: ExperienceOptimizeRequest):
    profile = ProfileService.get_profile()
    experience = profile.get("experience", [])
    if not experience:
        return {"results": []}
    results = await ProfileService.optimize_experience_bullets(experience, req.lang)
    return {"results": results}

class HeadlineVariantsRequest(BaseModel):
    lang: str = "pt"
    count: int = 3

@router.post("/headline-variants")
async def headline_variants(req: HeadlineVariantsRequest):
    profile = ProfileService.get_profile()
    return await ProfileService.generate_headline_variants(profile, req.lang, req.count)

@router.post("/ssi-simulate")
async def ssi_simulate():
    profile = ProfileService.get_profile()
    return await ProfileService.simulate_ssi(profile)

class ATSMatchRequest(BaseModel):
    job_description: str

@router.post("/ats-match")
async def ats_match(req: ATSMatchRequest):
    profile = ProfileService.get_profile()
    return await ProfileService.analyze_ats_match(profile, req.job_description)
