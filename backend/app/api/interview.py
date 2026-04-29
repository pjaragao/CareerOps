from fastapi import APIRouter, HTTPException
from typing import List, Optional
from app.services.interview_service import InterviewService
from pydantic import BaseModel

router = APIRouter(prefix="/interview", tags=["interview"])

class StoryBase(BaseModel):
    title: str
    situation: str
    task: str
    action: str
    result: str
    tags: Optional[List[str]] = []

class GenerateRequest(BaseModel):
    description: str

@router.get("/stories")
async def get_stories():
    return {"stories": InterviewService.get_stories()}

@router.post("/stories")
async def add_story(story: StoryBase):
    success = InterviewService.save_story(
        story.title, story.situation, story.task, story.action, story.result, story.tags
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save story")
    return {"ok": True}

@router.post("/generate-star")
async def generate_star(req: GenerateRequest):
    result = await InterviewService.generate_star_case(req.description)
    return result

@router.delete("/stories/{story_id}")
async def delete_story(story_id: int):
    success = InterviewService.delete_story(story_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete story")
    return {"ok": True}

class SimulationRequest(BaseModel):
    job_id: int
    answer: str
    history: List[dict] = []

@router.post("/simulate")
async def simulate_interview(req: SimulationRequest):
    return await InterviewService.simulate_interaction(req.job_id, req.answer, req.history)
