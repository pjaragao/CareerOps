from fastapi import APIRouter, HTTPException
from app.services.settings_service import SettingsService
from typing import Dict, Any

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("")
async def get_settings():
    return SettingsService.get_settings()

@router.post("")
async def update_settings(settings: Dict[str, Any]):
    success = SettingsService.update_settings(settings)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update settings")
    return {"ok": True}
