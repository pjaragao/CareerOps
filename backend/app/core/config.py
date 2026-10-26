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

    # --- Paths ---
    OUTPUT_DIR: Path = PROJECT_DIR / os.getenv("OUTPUT_DIR", "./output")
    AUTH_DIR: Path = PROJECT_DIR / "auth"
    SESSION_FILE: Path = AUTH_DIR / "linkedin_session.json"
    RESUME_BASE_FILE: Path = PROJECT_DIR / "resume_base.md"
    PROMPT_FILE: Path = PROJECT_DIR / "prompt_template.md"
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
