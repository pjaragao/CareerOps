
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.services.company_service import CompanyService
from pydantic import BaseModel

router = APIRouter(tags=["companies"])

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    career_site_url: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    industry: Optional[str] = None
    tech_stack: Optional[str] = None
    remote_policy: Optional[str] = None
    domain: Optional[str] = None
    company_type: Optional[str] = None

@router.get("/")
async def get_companies(type: Optional[str] = Query(None)):
    return {"companies": CompanyService.get_companies(type)}

@router.get("/{company_id}/")
async def get_company(company_id: int):
    company = CompanyService.get_company_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@router.put("/{company_id}/")
async def update_company(company_id: int, data: CompanyUpdate):
    success = CompanyService.update_company(company_id, data.dict(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update company")
    return {"ok": True}
@router.get("/{company_id}/jobs/")
async def get_company_jobs(company_id: int):
    from app.services.job_service import JobService
    return {"jobs": JobService.get_jobs_by_company(company_id)}
