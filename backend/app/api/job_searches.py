import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import require_approver
from app.services.job_search_service import JobSearchService

router = APIRouter(prefix="/job-searches", tags=["job-searches"])


@router.get("/catalog")
async def catalog():
    """The groups of titles and the places to look: the same ones the automatic search uses."""
    return JobSearchService.catalog()


# ── The other sources (discovery_service): health, the measure, switches ──
@router.get("/sources/stats", dependencies=[Depends(require_approver)])
async def source_stats(days: int = Query(7, ge=1, le=60)):
    from app.services.discovery_service import DiscoveryService
    return await asyncio.to_thread(DiscoveryService.stats, days)


@router.get("/sources", dependencies=[Depends(require_approver)])
async def sources(kind: Optional[str] = None):
    from app.services.discovery_service import DiscoveryService
    return {"items": await asyncio.to_thread(DiscoveryService.list_sources, kind)}


class KindIn(BaseModel):
    enabled: bool


@router.put("/sources/kinds/{kind}", dependencies=[Depends(require_approver)])
async def set_kind(kind: str, req: KindIn):
    from app.services.discovery_service import DiscoveryService
    try:
        return {"off": DiscoveryService.set_kind(kind, req.enabled)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/sources/{source_id}", dependencies=[Depends(require_approver)])
async def set_source(source_id: int, req: KindIn):
    from app.services.discovery_service import DiscoveryService
    row = DiscoveryService.set_source(source_id, req.enabled)
    if not row:
        raise HTTPException(status_code=404, detail="Fonte não encontrada")
    return row


class LinkIn(BaseModel):
    url: str = Field(..., min_length=10, max_length=1000)
    company: Optional[str] = Field(None, max_length=200)


@router.post("/sources", dependencies=[Depends(require_approver)])
async def add_source(req: LinkIn):
    from app.services.discovery_service import DiscoveryService
    try:
        return DiscoveryService.add_by_link(req.url, req.company)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/sources/run/{family}", dependencies=[Depends(require_approver)])
async def run_now(family: str):
    """A round right now (ats: company boards; board: job boards), in the background: the counts appear in Fontes."""
    from app.services.discovery_service import DiscoveryService
    if family not in ("ats", "board"):
        raise HTTPException(status_code=404, detail="ats ou board")

    async def go():
        try:
            await asyncio.to_thread(DiscoveryService.run_now, family)
        except ValueError:
            pass
    asyncio.create_task(go())
    return {"started": family}
