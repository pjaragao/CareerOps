from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from app.services.pipeline_service import PipelineService
from app.services.scraper_service import ScraperService
from pydantic import BaseModel

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

class UrlBase(BaseModel):
    url: str
    source: Optional[str] = "manual"

@router.get("/")
async def get_urls(status: str = "pending"):
    return {"urls": PipelineService.get_urls(status)}

@router.post("/")
async def add_url(data: UrlBase):
    success = PipelineService.add_url(data.url, data.source)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add URL to pipeline")
    return {"ok": True}

@router.delete("/{url_id}")
async def delete_url(url_id: int):
    success = PipelineService.delete_url(url_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete URL from pipeline")
    return {"ok": True}

@router.post("/process")
async def process_pipeline(background_tasks: BackgroundTasks):
    background_tasks.add_task(ScraperService.process_pipeline)
    return {"message": "Pipeline processing started in background"}
