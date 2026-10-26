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
    lang: str = "pt"
    strategy_context: Optional[Dict[str, Any]] = None

class StrategyContextRequest(BaseModel):
    lang: str = "pt"
    strategy_context: Optional[Dict[str, Any]] = None

@router.get("")
async def get_profile():
    return ProfileService.get_profile()

@router.post("")
async def save_profile(profile: Dict[str, Any]):
    ProfileService.save_profile(profile)
    return {"ok": True}

@router.get("/resume")
async def get_resume(lang: str = "en"):
    return {"content": ProfileService.get_resume_base(lang)}

@router.post("/resume")
async def save_resume(data: ResumeUpdate, lang: str = "en"):
    ProfileService.save_resume_base(data.content, lang)
    return {"ok": True}

@router.get("/status")
async def get_status():
    stats = ProfileService.get_latest_stats()
    return {"stats": stats}

@router.post("/optimize")
async def optimize(req: OptimizeRequest):
    result = await ProfileService.optimize_section(req.section, req.content, req.lang, req.strategy_context)
    return {"result": result}

@router.get("/optimizer-analysis")
async def get_optimizer_analysis(type: str):
    analysis = ProfileService.get_latest_analysis(type)
    return {"analysis": analysis}

import asyncio

class FullAuditRequest(BaseModel):
    lang: str = "pt"
    strategy_context: Optional[Dict[str, Any]] = None

@router.post("/run-full-audit")
async def run_full_audit(req: FullAuditRequest):
    profile = ProfileService.get_profile()
    lang_profile = ProfileService._get_flattened_profile(profile, req.lang)
    content = json.dumps(lang_profile)
    
    # Define tasks for parallel execution
    score_task = ProfileService.get_profile_score(content)
    ssi_task = ProfileService.simulate_ssi(profile, req.lang)
    headlines_task = ProfileService.generate_headline_variants(profile, req.lang, 3, req.strategy_context)
    about_opt_task = ProfileService.optimize_section(f"LinkedIn About", lang_profile.get("about", ""), req.lang, req.strategy_context)
    
    # Comprehensive optimization includes Skills and Experience
    target_role = req.strategy_context.get("label") if req.strategy_context else lang_profile.get("preferences", {}).get("target_role", "Software Engineer")
    skills_task = ProfileService.analyze_skills(profile, target_role, req.strategy_context, req.lang)
    experience_task = ProfileService.optimize_experience_bullets(lang_profile.get("experience", []), req.lang, req.strategy_context)
    
    # Run all tasks in parallel
    score, ssi, headlines, about_opt, skills, experience = await asyncio.gather(
        score_task, ssi_task, headlines_task, about_opt_task, skills_task, experience_task
    )
    
    results = {
        "score": score,
        "ssi": ssi,
        "headlines": headlines,
        "about": {
            "original": lang_profile.get("about", ""),
            "optimized": about_opt
        },
        "skills": skills,
        "experience": experience
    }
    
    # Save the consolidated analysis
    ProfileService.save_analysis("full_audit", req.lang, req.strategy_context, results, profile)
    
    # Also update individual caches for UI consistency
    ProfileService.save_analysis("skills", req.lang, req.strategy_context, skills, profile)
    ProfileService.save_analysis("experience", req.lang, req.strategy_context, {"results": experience}, profile)
    
    return {"results": results}


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

class SkillsAnalysisRequest(StrategyContextRequest):
    target_role: str

@router.post("/analyze-skills")
async def analyze_skills(req: SkillsAnalysisRequest):
    profile = ProfileService.get_profile()
    results = await ProfileService.analyze_skills(profile, req.target_role, req.strategy_context, req.lang)
    ProfileService.save_analysis("skills", req.lang, req.strategy_context, results, profile)
    return results

class ExperienceOptimizeRequest(StrategyContextRequest):
    pass

@router.post("/optimize-experience")
async def optimize_experience(req: ExperienceOptimizeRequest):
    profile = ProfileService.get_profile()
    lang_profile = ProfileService._get_flattened_profile(profile, req.lang)
    experience = lang_profile.get("experience", [])
    if not experience:
        return {"results": []}
    results = await ProfileService.optimize_experience_bullets(experience, req.lang, req.strategy_context)
    ProfileService.save_analysis("experience", req.lang, req.strategy_context, {"results": results}, profile)
    return {"results": results}

@router.post("/restructure-experience")
async def restructure_experience(req: ExperienceOptimizeRequest):
    results = await ProfileService.restructure_experience_profile(req.lang, req.strategy_context)
    return results

class HeadlineVariantsRequest(StrategyContextRequest):
    count: int = 3

@router.post("/headline-variants")
async def headline_variants(req: HeadlineVariantsRequest):
    profile = ProfileService.get_profile()
    results = await ProfileService.generate_headline_variants(profile, req.lang, req.count, req.strategy_context)
    return results

@router.post("/ssi-simulate")
async def ssi_simulate(req: StrategyContextRequest):
    profile = ProfileService.get_profile()
    return await ProfileService.simulate_ssi(profile, req.lang)

class ATSMatchRequest(StrategyContextRequest):
    job_description: str

@router.post("/ats-match")
async def ats_match(req: ATSMatchRequest):
    profile = ProfileService.get_profile()
    results = await ProfileService.analyze_ats_match(profile, req.job_description, req.lang)
    ProfileService.save_analysis("ats_match", req.lang, req.strategy_context, results, profile)
    return results
