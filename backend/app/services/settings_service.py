import json
import os
from pathlib import Path
from typing import Dict, Any
from app.core.config import settings

class SettingsService:
    @staticmethod
    def get_settings_path() -> Path:
        path = Path(settings.CONFIG_DIR) / "settings.json"
        if not path.exists():
            # Initialize with defaults from env
            defaults = {
                "gemini_api_key": settings.GEMINI_API_KEY,
                "linkedin_email": settings.LINKEDIN_EMAIL,
                "scrape_delay": settings.SCRAPE_DELAY,
                "max_jobs": settings.MAX_JOBS,
                "openai_api_key": os.getenv("AI_API_KEY", ""),
                "openai_base_url": os.getenv("AI_BASE_URL", ""),
                "ai_model_resume": settings.AI_MODEL,
                "ai_model_cover": settings.AI_MODEL,
                "ai_model_chat": settings.AI_MODEL,
                "ai_model_outreach": settings.AI_MODEL,
                "ai_model_fallback": "gemini-1.5-flash"
            }
            path.write_text(json.dumps(defaults, indent=2))
        return path

    @staticmethod
    def get_settings() -> Dict[str, Any]:
        path = SettingsService.get_settings_path()
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                # Ensure all keys exist
                defaults = {
                    "gemini_api_key": settings.GEMINI_API_KEY,
                    "linkedin_email": settings.LINKEDIN_EMAIL,
                    "scrape_delay": settings.SCRAPE_DELAY,
                    "max_jobs": settings.MAX_JOBS,
                    "ai_model_resume": settings.AI_MODEL,
                    "ai_model_cover": settings.AI_MODEL,
                    "ai_model_chat": settings.AI_MODEL,
                    "ai_model_outreach": settings.AI_MODEL,
                    "ai_model_fallback": "gemini-1.5-flash"
                }
                for k, v in defaults.items():
                    if k not in data: data[k] = v
                return data
        except Exception as e:
            print(f"Error loading settings: {e}")
            return {}

    @staticmethod
    def update_settings(new_settings: Dict[str, Any]) -> bool:
        path = SettingsService.get_settings_path()
        try:
            current = SettingsService.get_settings()
            current.update(new_settings)
            with open(path, 'w') as f:
                json.dump(current, f, indent=2)
            
            # Update live settings in memory if possible
            # Note: This only affects the current process. 
            # In Docker with reload, it might help.
            if "gemini_api_key" in new_settings:
                os.environ["GEMINI_API_KEY"] = new_settings["gemini_api_key"]
                
            return True
        except Exception as e:
            print(f"Error updating settings: {e}")
            return False
