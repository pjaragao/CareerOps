from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from app.services.job_service import JobService
from pydantic import BaseModel

router = APIRouter(tags=["jobs"])

class ManualJobCreate(BaseModel):
    title: str
    company: str
    location: Optional[str] = ""
    url: Optional[str] = ""
    description: str

class MarkAppliedRequest(BaseModel):
    jobId: str

@router.post("/mark-applied")
async def mark_applied(req: MarkAppliedRequest):
    success = JobService.mark_job_applied(req.jobId)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to mark job as applied")
    return {"ok": True}
@router.get("/")
async def get_jobs(status: Optional[str] = Query("all"), limit: int = Query(200)):
    return {"jobs": JobService.get_jobs(status, limit)}

@router.get("/{job_id}")
async def get_job(job_id: int):
    job = JobService.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/linkedin/{linkedin_job_id}")
async def job_by_linkedin_id(linkedin_job_id: str):
    """The CareerOps job for a LinkedIn job id (Easy Apply uses it to attach the CV generated for that job)."""
    from app.db.session import get_db_connection, get_db_cursor
    conn = get_db_connection()
    try:
        with get_db_cursor(conn) as cur:
            cur.execute("""SELECT id, status, resume_markdown IS NOT NULL AND resume_markdown <> '' AS has_resume,
                                  cover_letter IS NOT NULL AND cover_letter <> '' AS has_cover
                             FROM public.job_listings WHERE linkedin_job_id = %s OR url LIKE %s ORDER BY id LIMIT 1""",
                        (linkedin_job_id, f"%/jobs/view/{linkedin_job_id}/%"))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Vaga ainda não está no CareerOps")
    return dict(row)

@router.post("/manual")
async def add_manual_job(job: ManualJobCreate):
    success = JobService.insert_manual_job(
        job.title, job.company, job.location, job.url, job.description
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add manual job")
    return {"ok": True}

class StatusUpdate(BaseModel):
    status: str

@router.patch("/{job_id}/status")
async def update_job_status(job_id: int, body: StatusUpdate):
    success = JobService.update_job_status(job_id, body.status)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update status")
    return {"ok": True}

@router.delete("/{job_id}")
async def delete_job(job_id: int):
    success = JobService.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete job")
    return {"ok": True}

@router.post("/import-extension")
async def import_job_extension(request: Request):
    try:
        import json
        import os
        from app.core.config import settings
        
        body_bytes = await request.body()
        data = json.loads(body_bytes.decode("utf-8"))
        
        # Physical Audit Log for Jobs
        try:
            log_dir = os.path.join(os.path.dirname(settings.CONFIG_DIR), "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "debug_job_payload.json")
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except: pass

        success = JobService.insert_manual_job(
            data.get("title", ""),
            data.get("company", ""),
            data.get("location", ""),
            data.get("url", ""),
            data.get("description", ""),
            linkedin_job_id=data.get("linkedin_job_id")
        )
        # Single-job import marks it applied (legacy behaviour); saved-jobs import sends status="new" and never
        # moves a job that is already further along (applied, interviewing...) back.
        if success:
            try:
                from app.db.session import get_db_connection
                conn = get_db_connection()
                with conn.cursor() as cur:
                    if data.get("status") == "new":
                        cur.execute("UPDATE public.job_listings SET status = 'new' WHERE (url = %s OR linkedin_job_id = %s) AND status IN ('scraped', 'archived')", (data.get("url"), data.get("linkedin_job_id")))
                    else:
                        cur.execute("UPDATE public.job_listings SET status = 'applied' WHERE url = %s OR linkedin_job_id = %s", (data.get("url"), data.get("linkedin_job_id")))
                conn.commit()
                conn.close()
            except: pass
            # "Meet the hiring team" on the job page: stored on the job and added to the prospects
            if data.get("hiringTeam"):
                try:
                    from app.services.linkedin_networking_service import NetworkingService
                    NetworkingService.save_hiring_team(data.get("linkedin_job_id"), data.get("url"), data["hiringTeam"])
                except Exception as e:
                    print(f"DEBUG: hiring team not saved: {e}")

        return {"ok": success}
    except Exception as e:
        print(f"DEBUG: Job import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import-universal")
async def import_job_universal(request: Request):
    try:
        import json
        body_bytes = await request.body()
        data = json.loads(body_bytes.decode("utf-8"))
        
        success = await JobService.import_job_universal_ai(
            data.get("raw_text", ""),
            data.get("url", "")
        )
        return {"ok": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{job_id}/evaluate")
async def evaluate_job(job_id: int):
    result = await JobService.evaluate_job(job_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to evaluate job")
    return result
