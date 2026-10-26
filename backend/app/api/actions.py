from fastapi import APIRouter, HTTPException, Response, BackgroundTasks
from typing import Dict, Any, Optional
import os
import re
import json
from pydantic import BaseModel
from app.services.job_service import JobService
from app.services.profile_service import ProfileService
from app.services.pdf_service import PDFService
from app.services.skill_service import SkillService
from app.services.ai_service import AIService
from app.services.ai_settings_service import detect_language
from app.core.config import settings

router = APIRouter(tags=["job-actions"])

class ActionOptions(BaseModel):
    tone: Optional[str] = "semi-formal"
    orientation: Optional[str] = ""
    message: Optional[str] = ""
    model: Optional[str] = None

@router.get("/models")
async def list_ai_models():
    return AIService.list_models()

def get_tone_instruction(tone: str) -> str:
    if tone == "informal":
        return "Tone: Informal, light, direct, friendly."
    elif tone == "formal":
        return "Tone: Very formal, strictly professional and polished."
    return "Tone: Semi-formal, balanced, professional but accessible."

def get_job_lang(job: dict) -> str:
    """Portuguese only for Portuguese job ads; English otherwise (ties and Spanish included)."""
    lang = job.get('language')
    if lang:
        return "Portuguese" if "pt" in lang.lower() else "English"
    text = f"{job.get('job_title') or ''} {job.get('description') or ''}"
    return "Portuguese" if detect_language(text) == "Portuguese" else "English"

@router.post("/{job_id}/generate-resume")
async def generate_resume(job_id: int, options: ActionOptions):
    job = JobService.get_job_by_id(job_id)
    if not job: raise HTTPException(status_code=404)
    
    # Brazilian (Portuguese) jobs start from the Brazil CV; everything else from the international one
    resume_base = ProfileService.get_resume_base("pt" if get_job_lang(job) == "Portuguese" else "en")
    
    response = await SkillService.run_skill(
        "jobs/resume.md",
        {
            "job_title": job['job_title'],
            "company": job['company'],
            "lang_name": get_job_lang(job),
            "job_description": job['description'][:10000],
            "resume_base": resume_base,
            "orientation": options.orientation
        }
    )
    
    result = response.get("resume_markdown", "")
    if result:
        JobService.update_job_ai_content(job_id, 'resume', result)
    return {"content": result}

@router.post("/{job_id}/generate-cover-letter")
async def generate_cover_letter(job_id: int, options: ActionOptions):
    job = JobService.get_job_by_id(job_id)
    if not job: raise HTTPException(status_code=404)
    profile = ProfileService.get_profile()
    p = ProfileService._get_flattened_profile(profile, "pt")
    profile_summary = f"Summary: {p.get('about','')}\nExperience: {json.dumps(p.get('experience',[]))}"
    
    tone_instr = get_tone_instruction(options.tone)
    
    result = await SkillService.run_skill(
        "jobs/cover_letter.md",
        {
            "lang_name": get_job_lang(job),
            "tone_instruction": tone_instr,
            "job_title": job['job_title'],
            "company": job['company'],
            "job_description": job['description'][:4000],
            "profile_summary": profile_summary,
            "orientation": options.orientation
        },
        response_format="text"
    )
    
    # Cleanup
    if result:
        result = re.sub(r'```markdown\n', '', result)
        result = re.sub(r'```', '', result)
        result = result.strip()
        JobService.update_job_ai_content(job_id, 'cover', result)
    return {"content": result}

@router.post("/{job_id}/chat")
async def chat_with_job(job_id: int, options: ActionOptions):
    job = JobService.get_job_by_id(job_id)
    if not job: raise HTTPException(status_code=404)
    profile = ProfileService.get_profile()
    p = ProfileService._get_flattened_profile(profile, "pt")
    profile_summary = f"Summary: {p.get('about','')}\nSkills: {', '.join(p.get('skills',[]))}"
    
    tone_instr = get_tone_instruction(options.tone)
    
    result = await SkillService.run_skill(
        "common/chat.md",
        {
            "tone_instruction": tone_instr,
            "lang_name": get_job_lang(job),
            "profile_summary": profile_summary,
            "job_title": job['job_title'],
            "company": job['company'],
            "job_description": job['description'][:3000],
            "orientation": options.orientation,
            "question": options.message
        },
        response_format="text"
    )
    return {"reply": result}

@router.post("/{job_id}/outreach")
async def generate_outreach(job_id: int, type: str = "dm", options: ActionOptions = None):
    job = JobService.get_job_by_id(job_id)
    if not job: raise HTTPException(status_code=404)
    
    tone_instr = get_tone_instruction(options.tone if options else "semi-formal")
    
    profile = ProfileService.get_profile()
    p = ProfileService._get_flattened_profile(profile, "pt")
    profile_summary = f"Summary: {p.get('about','')}\nSkills: {', '.join(p.get('skills',[]))}"
    
    result = await SkillService.run_skill(
        "jobs/outreach.md",
        {
            "type": type,
            "profile_summary": profile_summary,
            "job_title": job['job_title'],
            "company": job['company'],
            "lang_name": get_job_lang(job),
            "tone_instruction": tone_instr,
            "orientation": options.orientation if options else "",
            "job_description": job['description'][:3000]
        },
        response_format="text"
    )
    if result and type == "dm":
        JobService.update_job_ai_content(job_id, 'dm', result)
    return {"content": result}

@router.post("/{job_id}/download-pdf")
async def download_pdf(job_id: int, data: Dict[str, str]):
    content = data.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="No content provided")
    
    pdf_bytes = PDFService.generate_pdf(content, f"resume_job_{job_id}.pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=resume_{job_id}.pdf"}
    )



class AutoApplyIn(BaseModel):
    tone: Optional[str] = "semi-formal"
    orientation: Optional[str] = ""
    regenerate: bool = False


@router.post("/{job_id}/auto-apply/prepare")
async def prepare_auto_apply(job_id: int, options: AutoApplyIn):
    """Everything the extension needs to apply: tailored resume and cover letter (generated only when missing,
    or again with regenerate), the job context and the URL to open. Applying itself happens in the browser."""
    job = JobService.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404)
    opts = ActionOptions(tone=options.tone, orientation=options.orientation)
    generated = []
    if options.regenerate or not job.get("resume_markdown"):
        await generate_resume(job_id, opts)
        generated.append("resume")
    if options.regenerate or not job.get("cover_letter"):
        await generate_cover_letter(job_id, opts)
        generated.append("cover")
    job = JobService.get_job_by_id(job_id)
    url = job.get("url") or ""
    if url and not url.startswith("http"):
        url = "https://" + url
    return {
        "job_id": job_id, "generated": generated, "apply_url": url,
        "is_linkedin": "linkedin.com/jobs" in url,
        "job": {"title": job.get("job_title"), "company": job.get("company"), "location": job.get("location"),
                "description": (job.get("description") or "")[:5000]},
        "resume_markdown": job.get("resume_markdown") or "", "cover_letter": job.get("cover_letter") or "",
        "language": get_job_lang(job),
    }


def _pdf_name(job: dict, kind: str) -> str:
    who = "Paulo-Aragao-Jr"
    company = re.sub(r"[^A-Za-z0-9]+", "-", job.get("company") or "").strip("-")[:40]
    label = ("CV" if get_job_lang(job) == "Portuguese" else "Resume") if kind == "resume" else (
        "Carta" if get_job_lang(job) == "Portuguese" else "Cover-Letter")
    return f"{who}-{label}{'-' + company if company else ''}.pdf"


@router.get("/{job_id}/document.pdf")
async def job_document_pdf(job_id: int, kind: str = "resume"):
    """The job's tailored resume (or cover letter) as a PDF — the file the extension attaches to the application."""
    job = JobService.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404)
    content = job.get("resume_markdown") if kind == "resume" else job.get("cover_letter")
    if not content:
        raise HTTPException(status_code=404, detail="Documento ainda não gerado")
    name = _pdf_name(job, kind)
    return Response(content=PDFService.generate_pdf(content, name), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
