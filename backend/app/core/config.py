import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Project root (backend folder)
BACKEND_DIR = Path(__file__).parent.parent.parent.resolve()
# In Docker, we want to stay within /app
if BACKEND_DIR == Path("/"):
    BACKEND_DIR = Path("/app")
PROJECT_DIR = BACKEND_DIR

# Load .env from project root
load_dotenv(PROJECT_DIR / ".env")

class Settings(BaseSettings):
    PROJECT_DIR: Path = PROJECT_DIR
    # --- Supabase / PostgreSQL ---
    DB_HOST: str = os.getenv("SUPABASE_DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("SUPABASE_DB_PORT", "5432"))
    DB_NAME: str = os.getenv("SUPABASE_DB_NAME", "postgres")
    DB_USER: str = os.getenv("SUPABASE_DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("SUPABASE_DB_PASSWORD", "")

    # --- AI Provider ---
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini").lower()
    AI_API_KEY: str = os.getenv("AI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "gemini-1.5-flash")
    AI_BASE_URL: Optional[str] = os.getenv("AI_BASE_URL")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # --- Gotenberg ---
    GOTENBERG_URL: str = os.getenv("GOTENBERG_URL", "http://localhost:3002")

    # --- LinkedIn ---
    LINKEDIN_EMAIL: str = os.getenv("LINKEDIN_EMAIL", "")
    # Official API (developer app with "Sign In with LinkedIn using OpenID Connect" + "Share on LinkedIn")
    LINKEDIN_CLIENT_ID: str = os.getenv("LINKEDIN_CLIENT_ID", "")
    LINKEDIN_CLIENT_SECRET: str = os.getenv("LINKEDIN_CLIENT_SECRET", "")
    LINKEDIN_REDIRECT_URI: str = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8005/api/linkedin-copilot/oauth/callback")
    # Versioned REST API (YYYYMM). Empty = previous month, which LinkedIn always supports.
    LINKEDIN_API_VERSION: str = os.getenv("LINKEDIN_API_VERSION", "")
    LINKEDIN_MAX_POSTS_PER_DAY: int = int(os.getenv("LINKEDIN_MAX_POSTS_PER_DAY", "2"))
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    # Day/week boundaries for the LinkedIn Copilot counters ("today", "this week")
    APP_TIMEZONE: str = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")

    # --- Access (core/auth.py): empty token = the routes of that role refuse everything ---
    CAREEROPS_APPROVER_TOKEN: str = os.getenv("CAREEROPS_APPROVER_TOKEN", "")
    CAREEROPS_WORKER_TOKEN: str = os.getenv("CAREEROPS_WORKER_TOKEN", "")
    # Lolo (the WhatsApp bot): approves and answers for you, never changes the mode, the account or the limits
    CAREEROPS_BOT_TOKEN: str = os.getenv("CAREEROPS_BOT_TOKEN", "")
    # Besides FRONTEND_URL, the addresses the app is opened from
    CAREEROPS_ALLOWED_ORIGINS: str = os.getenv(
        "CAREEROPS_ALLOWED_ORIGINS",
        "https://mpbflndsk201-wsl.tabby-broadnose.ts.net:5174,http://100.109.242.35:5173,http://localhost:5173,http://127.0.0.1:5173",
    )

    # A second lock on the final click of an application: it stays false anywhere the test account runs
    AUTOMATION_ALLOW_FINAL_SUBMIT: bool = os.getenv("AUTOMATION_ALLOW_FINAL_SUBMIT", "false").lower() == "true"
    # Where you see the server browser (login, verifications)
    CAREEROPS_NOVNC_URL: str = os.getenv("CAREEROPS_NOVNC_URL", "https://mpbflndsk201-wsl.tabby-broadnose.ts.net:6083/vnc.html")

    # --- Daily email monitor (Gmail app password, read-only use): empty = it does not run ---
    GMAIL_ADDRESS: str = os.getenv("GMAIL_ADDRESS", "")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
    GMAIL_IMAP_HOST: str = os.getenv("GMAIL_IMAP_HOST", "imap.gmail.com")

    # --- Paths ---
    OUTPUT_DIR: Path = PROJECT_DIR / os.getenv("OUTPUT_DIR", "./output")
    AUTH_DIR: Path = PROJECT_DIR / "auth"
    SESSION_FILE: Path = AUTH_DIR / "linkedin_session.json"
    # Master CVs (in config/, which is mounted into the container): abroad = English, Brazil = Portuguese
    RESUME_BASE_FILE: Path = PROJECT_DIR / "config" / "resume_en.md"
    RESUME_BASE_PT_FILE: Path = PROJECT_DIR / "config" / "resume_pt.md"
    CONFIG_DIR: Path = PROJECT_DIR / "config"
    PROFILE_FILE: Path = CONFIG_DIR / "profile.yml"

    # --- Scraping ---
    SCRAPE_DELAY: int = int(os.getenv("SCRAPE_DELAY", "4"))
    MAX_JOBS: int = int(os.getenv("MAX_JOBS", "20"))

    class Config:
        env_file = ".env"

settings = Settings()

# Ensure directories exist
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
settings.AUTH_DIR.mkdir(parents=True, exist_ok=True)
settings.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
