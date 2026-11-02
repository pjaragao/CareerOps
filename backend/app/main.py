import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.auth import origin_guard
from app.api import jobs, interview, profile, actions, settings as settings_api, documents, linkedin_copilot, ai_settings, general_resumes, automation, job_searches
from app.services.linkedin_copilot_service import LinkedInCopilotService

app = FastAPI(
    title="LinkedIn Career Ops API",
    description="API for managing LinkedIn job applications, resumes, and interview prep.",
    version="2.0.0"
)

# Set up CORS - Permissive for extension development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False, # Changed to False to allow wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last, so it runs first: other sites' pages never reach the routes that act on your behalf
app.middleware("http")(origin_guard)

app.include_router(actions.router, prefix="/api/jobs")
app.include_router(jobs.router, prefix="/api/jobs")
app.include_router(interview.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(documents.router, prefix="/api/documents")
app.include_router(linkedin_copilot.router, prefix="/api")
app.include_router(ai_settings.router, prefix="/api")
app.include_router(general_resumes.router, prefix="/api")
app.include_router(automation.router, prefix="/api")
app.include_router(job_searches.router, prefix="/api")


async def _publish_scheduled_posts():
    """Every minute: publish approved LinkedIn posts whose scheduled time has come."""
    while True:
        try:
            await asyncio.to_thread(LinkedInCopilotService.publish_due)
        except Exception as e:
            logging.getLogger("linkedin_copilot").warning("scheduler tick failed: %s", e)
        await asyncio.sleep(60)


async def _job_pipeline():
    """On startup and every 10 min: eligibility check, then CV and cover letter, for jobs still waiting (imported
    while the app was down, or whose AI call failed). New jobs are handled right away by the import endpoints."""
    from app.services.job_pipeline_service import JobPipelineService
    while True:
        try:
            await asyncio.to_thread(JobPipelineService.run_pending)
        except Exception as e:
            logging.getLogger("job_pipeline").warning("pipeline tick failed: %s", e)
        await asyncio.sleep(600)


async def _auto_drafts():
    """Every 30 min: a draft from the newest unused saved theme when fewer than two drafts are waiting."""
    while True:
        await asyncio.sleep(1800)
        try:
            await LinkedInCopilotService.auto_draft()
        except Exception as e:
            logging.getLogger("linkedin_copilot").warning("auto draft failed: %s", e)


async def _automation():
    """Every minute: the books of the Autopilot queue. While it is off, nothing else happens."""
    from app.services.automation_service import AutomationService
    while True:
        try:
            await asyncio.to_thread(AutomationService.tick)
        except Exception as e:
            logging.getLogger("automation").warning("automation tick failed: %s", e)
        await asyncio.sleep(60)


async def _email_monitor():
    """Every 5 minutes: is today's reading of the mailbox due?"""
    from app.services.email_monitor_service import EmailMonitorService
    while True:
        try:
            if await asyncio.to_thread(EmailMonitorService.due):
                await asyncio.to_thread(EmailMonitorService.run)
        except Exception as e:
            logging.getLogger("email_monitor").warning("email tick failed: %s", e)
        await asyncio.sleep(300)


@app.on_event("startup")
async def start_scheduler():
    try:
        from app.services.linkedin_voice_service import ensure_schema
        await asyncio.to_thread(ensure_schema)   # migrations_v12: line of thought and networking plans
    except Exception as e:
        logging.getLogger("linkedin_copilot").warning("migrations_v12 not applied: %s", e)
    try:
        from app.services.job_pipeline_service import ensure_schema as ensure_jobs_schema
        await asyncio.to_thread(ensure_jobs_schema)   # migrations_v13: eligibility check of jobs
    except Exception as e:
        logging.getLogger("job_pipeline").warning("migrations_v13 not applied: %s", e)
    try:
        from app.services.general_resume_service import ensure_schema as ensure_resumes_schema
        await asyncio.to_thread(ensure_resumes_schema)   # migrations_v14: general CVs for job boards
    except Exception as e:
        logging.getLogger("general_resumes").warning("migrations_v14 not applied: %s", e)
    try:
        from app.services.automation_service import ensure_schema as ensure_automation_schema
        from app.services.job_search_service import JobSearchService
        await asyncio.to_thread(ensure_automation_schema)   # migrations_v15: Autopilot and email monitor
        await asyncio.to_thread(JobSearchService.ensure_seeds)
    except Exception as e:
        logging.getLogger("automation").warning("migrations_v15 not applied: %s", e)
    app.state.automation = asyncio.create_task(_automation())
    app.state.email_monitor = asyncio.create_task(_email_monitor())
    app.state.linkedin_scheduler = asyncio.create_task(_publish_scheduled_posts())
    app.state.job_pipeline = asyncio.create_task(_job_pipeline())
    app.state.linkedin_drafts = asyncio.create_task(_auto_drafts())

@app.get("/")
async def root():
    return {"message": "Welcome to LinkedIn Career Ops API v2"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

import uvicorn
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
