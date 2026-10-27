import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import jobs, interview, profile, actions, settings as settings_api, documents, linkedin_copilot, ai_settings
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

app.include_router(actions.router, prefix="/api/jobs")
app.include_router(jobs.router, prefix="/api/jobs")
app.include_router(interview.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(documents.router, prefix="/api/documents")
app.include_router(linkedin_copilot.router, prefix="/api")
app.include_router(ai_settings.router, prefix="/api")


async def _publish_scheduled_posts():
    """Every minute: publish approved LinkedIn posts whose scheduled time has come."""
    while True:
        try:
            await asyncio.to_thread(LinkedInCopilotService.publish_due)
        except Exception as e:
            logging.getLogger("linkedin_copilot").warning("scheduler tick failed: %s", e)
        await asyncio.sleep(60)


async def _auto_drafts():
    """Every 30 min: a draft from the newest unused saved theme when fewer than two drafts are waiting."""
    while True:
        await asyncio.sleep(1800)
        try:
            await LinkedInCopilotService.auto_draft()
        except Exception as e:
            logging.getLogger("linkedin_copilot").warning("auto draft failed: %s", e)


@app.on_event("startup")
async def start_scheduler():
    try:
        from app.services.linkedin_voice_service import ensure_schema
        await asyncio.to_thread(ensure_schema)   # migrations_v12: line of thought and networking plans
    except Exception as e:
        logging.getLogger("linkedin_copilot").warning("migrations_v12 not applied: %s", e)
    app.state.linkedin_scheduler = asyncio.create_task(_publish_scheduled_posts())
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
