import asyncio
import json
import os
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ai_service import AIService
from app.services.ai_settings_service import (DEFAULT_MODELS, DEFAULT_STYLE, KINDS, LENGTHS, PRESETS, TASKS,
                                              AISettingsService)
from app.services.skill_service import SkillService

router = APIRouter(prefix="/ai-settings", tags=["ai-settings"])


@router.get("")
async def get_ai_settings():
    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    available = []
    if provider == "agy":
        try:
            available = [m["id"] for m in await asyncio.to_thread(AIService.get_provider().list_models)]
        except Exception:
            available = []
    return {
        "provider": provider,
        "kinds": KINDS, "presets": PRESETS, "lengths": {k: {n: list(r) for n, r in v.items()} for k, v in LENGTHS.items()},
        "style": AISettingsService.get_style(), "default_style": DEFAULT_STYLE,
        "tasks": TASKS, "models": AISettingsService.get_models(), "default_models": DEFAULT_MODELS,
        "available_models": available,
    }


@router.put("/style")
async def save_style(style: Dict[str, dict]):
    return {"style": AISettingsService.save_style(style)}


@router.put("/models")
async def save_models(models: Dict[str, str]):
    return {"models": AISettingsService.save_models(models)}


@router.get("/preview/{kind}")
async def preview(kind: str):
    """The instruction block the prompts receive for this kind (what the AI actually reads)."""
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail="Unknown kind")
    return {"text": AISettingsService.render(kind)}


class AdjustIn(BaseModel):
    kind: str
    instruction: str
    current: Optional[dict] = None


@router.post("/style/adjust")
async def adjust_style(req: AdjustIn):
    """Proposes new settings for one kind from a plain-language request. Nothing is saved here."""
    if req.kind not in KINDS:
        raise HTTPException(status_code=404, detail="Unknown kind")
    current = req.current or AISettingsService.get_style()[req.kind]
    prompt = await SkillService.render_prompt("settings/adjust_style.md", {
        "kind_label": KINDS[req.kind], "current": json.dumps(current, ensure_ascii=False), "presets": PRESETS,
        "instruction": req.instruction[:2000],
    })
    provider = AIService.get_provider("ai_model_style")
    result = await asyncio.to_thread(provider.generate_json, prompt)
    if not isinstance(result, dict) or result.get("error") or not isinstance(result.get("style"), dict):
        raise HTTPException(status_code=502, detail=f"AI adjust failed: {result}")
    proposed = {**current, **{k: v for k, v in result["style"].items() if k in ("preset", "tone", "formality", "length", "emojis", "hashtags", "custom")}}
    if proposed.get("preset") not in PRESETS:
        proposed["preset"] = current.get("preset", "direto")
    return {"style": proposed, "explanation": result.get("explanation", "")}
