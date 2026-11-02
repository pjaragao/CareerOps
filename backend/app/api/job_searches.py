from fastapi import APIRouter

from app.services.job_search_service import JobSearchService

router = APIRouter(prefix="/job-searches", tags=["job-searches"])


@router.get("/catalog")
async def catalog():
    """The groups of titles and the places to look: the same ones the automatic search uses."""
    return JobSearchService.catalog()
