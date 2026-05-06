import sys

def patch_file(filepath, target, replacement):
    with open(filepath, 'r') as f:
        content = f.read()
    if target not in content:
        print(f"Target not found in {filepath}")
        return False
    new_content = content.replace(target, replacement)
    with open(filepath, 'w') as f:
        f.write(new_content)
    print(f"Successfully patched {filepath}")
    return True

# Patch JobService (Backend)
patch_file('/home/paulojr/linkedin_resume/backend/app/services/job_service.py', 
'''    @staticmethod
    def delete_job(job_id: int) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.job_listings WHERE id = %s", (job_id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()''',
'''    @staticmethod
    def delete_job(job_id: int) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.job_listings WHERE id = %s", (job_id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    def update_job_status(job_id: int, new_status: str) -> bool:
        VALID = {'scraped', 'new', 'applied', 'interviewing', 'offer', 'rejected', 'done', 'error'}
        if new_status not in VALID:
            return False
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.job_listings SET status = %s, updated_at = %s WHERE id = %s",
                    (new_status, datetime.now(timezone.utc), job_id)
                )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating job status: {e}")
            return False
        finally:
            conn.close()''')

# Patch Jobs API (Backend)
patch_file('/home/paulojr/linkedin_resume/backend/app/api/jobs.py',
'''@router.post("/manual")
async def add_manual_job(job: ManualJobCreate):
    success = JobService.insert_manual_job(
        job.title, job.company, job.location, job.url, job.description
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add manual job")
    return {"ok": True}''',
'''@router.post("/manual")
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
    return {"ok": True}''')

# Patch JobDetail (Frontend)
patch_file('/home/paulojr/linkedin_resume/frontend/src/components/JobDetail.tsx',
"alignItems: 'flex-start', justifyContent: 'center', padding: '2vh 1rem',",
"alignItems: 'center', justifyContent: 'center', padding: '2rem',")
