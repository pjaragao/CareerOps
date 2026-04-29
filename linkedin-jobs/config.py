"""
Configuration module — loads .env and provides settings.
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Project root
PROJECT_DIR = Path(__file__).parent.resolve()

# Load .env
load_dotenv(PROJECT_DIR / ".env")


# --- Supabase / PostgreSQL ---
DB_HOST = os.getenv("SUPABASE_DB_HOST", "localhost")
DB_PORT = int(os.getenv("SUPABASE_DB_PORT", "5432"))
DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")
DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")

# --- AI Provider ---
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()
AI_API_KEY = os.getenv("AI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- Gotenberg ---
GOTENBERG_URL = os.getenv("GOTENBERG_URL", "http://localhost:3001")

# --- LinkedIn ---
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")

# --- Paths ---
OUTPUT_DIR = PROJECT_DIR / os.getenv("OUTPUT_DIR", "./output")
AUTH_DIR = PROJECT_DIR / "auth"
SESSION_FILE = AUTH_DIR / "linkedin_session.json"
RESUME_BASE_FILE = PROJECT_DIR / "resume_base.md"
PROMPT_FILE = PROJECT_DIR / "prompt_template.md"
CONFIG_DIR = PROJECT_DIR / "config"
PROFILE_FILE = CONFIG_DIR / "profile.yml"

# --- Scraping ---
SCRAPE_DELAY = int(os.getenv("SCRAPE_DELAY", "4"))
MAX_JOBS = int(os.getenv("MAX_JOBS", "20"))

# Ensure directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
AUTH_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_profile() -> dict:
    """Load user profile from config/profile.yml."""
    if PROFILE_FILE.exists():
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Could not load profile: {e}")
    return {}


def save_profile(profile: dict):
    """Save user profile to config/profile.yml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
