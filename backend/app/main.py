from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import jobs, interview, profile, strategies, pipeline, dashboard, auth, actions, companies, settings as settings_api, documents

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
app.include_router(strategies.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth")
app.include_router(companies.router, prefix="/api/companies")
app.include_router(settings_api.router, prefix="/api")
app.include_router(documents.router, prefix="/api/documents")

@app.get("/")
async def root():
    return {"message": "Welcome to LinkedIn Career Ops API v2"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

import uvicorn
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
