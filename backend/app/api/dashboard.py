from fastapi import APIRouter
from app.services.dashboard_service import DashboardService
from app.services.job_service import JobService
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/stats/")
async def get_stats():
    return DashboardService.get_stats()

@router.get("/skill-gaps/")
async def get_skill_gaps():
    return await AnalyticsService.get_skill_gaps()
