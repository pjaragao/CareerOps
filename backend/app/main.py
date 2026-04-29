from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import jobs, interview, profile, strategies, pipeline, dashboard, auth, actions, settings as settings_api

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
app.include_router(settings_api.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to LinkedIn Career Ops API v2"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

import uvicorn
import subprocess
import os

def start_xvfb():
    if os.name == 'posix' and os.environ.get('DISPLAY') == ':99':
        try:
            # Check if Xvfb is already running on :99
            subprocess.run(['xdpyinfo', '-display', ':99'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print("Xvfb is already running on :99")
        except:
            print("Starting Xvfb on :99...")
            # Use a lock file or check for existing process to be safe
            subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1280x1024x24', '-ac'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Give it a second to start
            import time
            time.sleep(1)

if __name__ == "__main__":
    start_xvfb()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
