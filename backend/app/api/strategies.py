from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from app.services.strategy_service import StrategyService
from app.services.scraper_service import ScraperService
from pydantic import BaseModel

router = APIRouter(prefix="/strategies", tags=["strategies"])

class StrategyBase(BaseModel):
    title: str
    keywords: List[str]
    locations: List[str]
    remote_only: Optional[bool] = True

@router.get("")
async def get_strategies():
    return {"strategies": StrategyService.get_strategies()}

@router.post("")
async def add_strategy(strat: StrategyBase):
    success = StrategyService.save_strategy(
        strat.title, strat.keywords, strat.locations, strat.remote_only
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save strategy")
    return {"ok": True}

@router.delete("/{strat_id}")
async def delete_strategy(strat_id: int):
    success = StrategyService.delete_strategy(strat_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete strategy")
    return {"ok": True}

@router.post("/{strat_id}/run")
async def run_strategy(strat_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(ScraperService.run_search_strategy, strat_id)
    return {"message": "Search started in background"}

@router.post("/run-all")
async def run_all_strategies(background_tasks: BackgroundTasks):
    background_tasks.add_task(ScraperService.run_all_strategies)
    return {"message": "All strategies search started in background"}
