from fastapi import APIRouter, HTTPException, Response, BackgroundTasks
from typing import Dict, Any, Optional
from app.services.ai_service import AIService
from app.services.job_service import JobService
from app.services.profile_service import ProfileService
from app.services.pdf_service import PDFService
from app.services.settings_service import SettingsService
from pydantic import BaseModel
from app.core.prompts import RESUME_ATS_PROMPT, CHAT_PROMPT, COVER_LETTER_PROMPT
from app.core.config import settings
import os

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

@router.post("/{job_id}/generate-resume")
async def generate_resume(job_id: int, options: ActionOptions):
    job = JobService.get_job_by_id(job_id)
    if not job: raise HTTPException(status_code=404)
    
    resume_base = ""
    if os.path.exists(settings.RESUME_BASE_FILE):
        with open(settings.RESUME_BASE_FILE, 'r') as f:
            resume_base = f.read()
    
    settings_ai = SettingsService.get_settings()
    model = options.model or settings_ai.get("ai_model_resume")
    
    provider = AIService.get_provider()
    prompt = RESUME_ATS_PROMPT.format(
        job_title=job['job_title'],
        company=job['company'],
        language=job.get('language', 'pt-BR'),
        description=job['description'][:10000],
        resume_base=resume_base
    )
    
    print(f"DEBUG: Generating resume for job {job_id} using model {model}")
    response = provider.generate_json(prompt, model=model)
    print(f"DEBUG: AI Response keys: {list(response.keys())}")
    if "error" in response:
        print(f"DEBUG: AI Error: {response['error']}")
    
    result = response.get("resume_markdown", "")
    if not result and "raw_text" in response: 
        # Robust parsing for JSON inside text
        raw = response["raw_text"]
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                result = parsed.get("resume_markdown", "")
            except:
                result = raw
        else:
            result = raw
            
    if result:
        print(f"DEBUG: Success! Saving {len(result)} chars to DB")
        JobService.update_job_ai_content(job_id, 'resume', result)
    else:
        print("DEBUG: Failed to get any result from AI")
        
    return {"content": result}

@router.post("/{job_id}/generate-cover-letter")
async def generate_cover_letter(job_id: int, options: ActionOptions):
    job = JobService.get_job_by_id(job_id)
    if not job: raise HTTPException(status_code=404)
    profile = ProfileService.get_profile()
    
    tone_instr = get_tone_instruction(options.tone)
    
    settings_ai = SettingsService.get_settings()
    model = options.model or settings_ai.get("ai_model_cover")
    
    provider = AIService.get_provider()
    prompt = COVER_LETTER_PROMPT.format(
        language=job.get('language', 'pt-BR'),
        tone_instruction=tone_instr,
        job_title=job['job_title'],
        company=job['company'],
        description=job['description'][:4000],
        profile_summary=profile,
        orientation=options.orientation
    )
    result = provider.generate_text(prompt, model=model)
    
    # Cleanup Cover Letter: Remove common AI fluff
    if result:
        # Remove patterns like "Since you did not provide...", "Note to User:", "Strategies for Success", etc.
        # This is a bit heuristic but effective.
        result = re.sub(r'(?i)Since you did not provide.*CV details.*?\n', '', result)
        result = re.sub(r'(?i)# Cover Letter Template.*?\n', '', result)
        result = re.sub(r'(?i)\*\*Note to User:\*\*.*?\n', '', result)
        result = re.sub(r'(?i)### 💡 Strategies for Success.*', '', result, flags=re.DOTALL)
        result = re.sub(r'(?i)To make this letter truly.*', '', result, flags=re.DOTALL)
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
    
    tone_instr = get_tone_instruction(options.tone)
    
    settings_ai = SettingsService.get_settings()
    model = options.model or settings_ai.get("ai_model_chat")
    
    provider = AIService.get_provider()
    prompt = CHAT_PROMPT.format(
        tone_instruction=tone_instr,
        language=job.get('language', 'pt-BR'),
        profile_summary=profile,
        job_title=job['job_title'],
        company=job['company'],
        description=job['description'][:3000],
        orientation=options.orientation,
        question=options.message
    )
    result = provider.generate_text(prompt, model=model)
    return {"reply": result}

@router.post("/{job_id}/outreach")
async def generate_outreach(job_id: int, type: str = "dm", options: ActionOptions = None):
    job = JobService.get_job_by_id(job_id)
    if not job: raise HTTPException(status_code=404)
    
    tone_instr = get_tone_instruction(options.tone if options else "semi-formal")
    
    settings_ai = SettingsService.get_settings()
    model = (options.model if options else None) or settings_ai.get("ai_model_outreach")
    
    provider = AIService.get_provider()
    if type == "dm":
        prompt = f"Generate a short LinkedIn DM (max 300 chars) for this job: {job['job_title']} at {job['company']}. {tone_instr} Instructions: {options.orientation if options else ''}"
    else:
        prompt = f"Generate a professional outreach email for this job: {job['job_title']} at {job['company']}. {tone_instr} Instructions: {options.orientation if options else ''}"
        
    result = provider.generate_text(prompt, model=model)
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

@router.post("/{job_id}/auto-apply")
async def auto_apply(job_id: int, background_tasks: BackgroundTasks):
    from app.services.scraper_service import ScraperService
    background_tasks.add_task(ScraperService.auto_apply, job_id)
    return {"message": "Auto-apply started in background"}
