import os
import json
import re
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.core.config import settings

class AIProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        pass

    @abstractmethod
    def list_models(self) -> List[Dict[str, Any]]:
        pass

class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, default_model: str, fallback_model: str = "gemini-1.5-flash"):
        import google.generativeai as genai
        self.genai = genai
        self.api_key = api_key
        self.default_model = default_model
        self.fallback_model = fallback_model
        self.genai.configure(api_key=self.api_key)

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            models = self.genai.list_models()
            return [{"id": m.name.replace("models/", ""), "name": m.display_name} for m in models if "generateContent" in m.supported_generation_methods]
        except Exception as e:
            return [{"id": self.default_model, "name": f"Default ({self.default_model})"}]

    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        model_name = model if model else self.default_model
        # Ensure model name has 'models/' prefix if needed by the SDK
        if not model_name.startswith("models/"):
            full_model_name = f"models/{model_name}"
        else:
            full_model_name = model_name
            
        try:
            gen_model = self.genai.GenerativeModel(full_model_name)
            response = gen_model.generate_content(
                prompt,
                generation_config=self.genai.types.GenerationConfig(temperature=temperature),
            )
            return response.text.strip() if response.text else ""
        except Exception as e:
            return f"Error: {str(e)}"

    def generate_json(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> Dict[str, Any]:
        model_name = model if model else self.default_model
        if not model_name.startswith("models/"):
            full_model_name = f"models/{model_name}"
        else:
            full_model_name = model_name
            
        try:
            gen_model = self.genai.GenerativeModel(full_model_name)
            response = gen_model.generate_content(
                prompt,
                generation_config=self.genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=temperature,
                ),
            )
            text = response.text.strip() if response.text else "{}"
            return json.loads(text)
        except Exception as e:
            error_msg = str(e)
            print(f"DEBUG: JSON generation failed for {model_name}: {error_msg}. Trying stable fallback...")
            
            # If it's a 404 or unsupported, try a known stable model
            if "404" in error_msg or "not supported" in error_msg.lower() or "not found" in error_msg.lower():
                stable_model = self.fallback_model
                try:
                    print(f"DEBUG: Falling back to {stable_model}")
                    gen_model = self.genai.GenerativeModel(f"models/{stable_model}")
                    response = gen_model.generate_content(
                        prompt,
                        generation_config=self.genai.types.GenerationConfig(
                            response_mime_type="application/json",
                            temperature=temperature,
                        ),
                    )
                    text = response.text.strip() if response.text else "{}"
                    return json.loads(text)
                except Exception as e2:
                    error_msg += f" | Fallback {stable_model} failed: {str(e2)}"
            
            try:
                # Last resort: normal text generation and manual extraction
                raw = self.generate_text(prompt, model=model, temperature=temperature)
                json_match = re.search(r'\{.*\}', raw, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
                return {"error": error_msg, "raw_text": raw}
            except Exception as e3:
                return {"error": f"{error_msg} | Manual extraction failed: {str(e3)}"}

class OpenAICompatibleProvider(AIProvider):
    def __init__(self, api_key: str, base_url: str, default_model: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.default_model = default_model

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            models = self.client.models.list()
            return [{"id": m.id, "name": m.id} for m in models]
        except:
            return [{"id": self.default_model, "name": self.default_model}]

    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        model_name = model or self.default_model
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    def generate_json(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> Dict[str, Any]:
        model_name = model or self.default_model
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": str(e)}

class AgyShimProvider(OpenAICompatibleProvider):
    """Antigravity CLI (`agy`) behind the OpenAI-compatible shim (mr-irrelevant/ops/agy_shim.py).

    The shim only knows agy model ids (e.g. `gemini-flash-latest`, `gemini-3.8-flash-low`); model names saved in
    settings for the Gemini API (e.g. `gemini-3.1-pro-preview`) fall back to the default. It has no JSON mode, so
    JSON is pulled out of the text answer.
    """
    _models_cache: Dict[str, Any] = {"ids": None, "at": 0.0}

    def _available(self) -> List[str]:
        import time
        cache = AgyShimProvider._models_cache
        if cache["ids"] is None or time.time() - cache["at"] > 3600:
            try:
                cache["ids"] = [m.id for m in self.client.models.list()]
            except Exception:
                cache["ids"] = []
            cache["at"] = time.time()
        return cache["ids"]

    def _model(self, model: Optional[str]) -> str:
        return model if model and model in self._available() else self.default_model

    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        return super().generate_text(prompt, model=self._model(model), temperature=temperature)

    def generate_json(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> Dict[str, Any]:
        raw = self.generate_text(prompt + "\n\nReturn ONLY the JSON object, with no text before or after it.",
                                 model=model, temperature=temperature)
        if raw.startswith("Error:"):
            return {"error": raw}
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return {"error": "AGY answer was not valid JSON", "raw_text": raw[:500]}

class AIService:
    @staticmethod
    def get_provider(model_key: Optional[str] = None) -> AIProvider:
        from app.services.settings_service import SettingsService
        # Load dynamic settings
        live_settings = SettingsService.get_settings()
        
        provider_type = os.getenv("AI_PROVIDER", "gemini").lower()
        api_key = live_settings.get("gemini_api_key") or settings.AI_API_KEY
        
        if provider_type == "gemini":
            # Using selectable models from settings based on model_key
            # Priority: 1. Exact model_key, 2. ai_model_chat, 3. hardcoded default
            model = "gemini-1.5-flash"
            if model_key and live_settings.get(model_key):
                model = live_settings.get(model_key)
            elif live_settings.get("ai_model_chat"):
                model = live_settings.get("ai_model_chat")
                
            fallback = live_settings.get("ai_model_fallback") or "gemini-1.5-pro"
            return GeminiProvider(api_key, model, fallback_model=fallback)
        elif provider_type == "agy":
            return AgyShimProvider(
                os.getenv("AGY_SHIM_TOKEN", ""),
                os.getenv("AGY_BASE_URL", "http://172.26.0.1:8787/v1"),
                os.getenv("AGY_MODEL", "gemini-flash-latest"),
            )
        elif provider_type in ["nvidia", "alibaba", "ollama", "openai"]:
            base_url = live_settings.get("openai_base_url") or settings.AI_BASE_URL
            api_key = live_settings.get("openai_api_key") or api_key
            
            # Use same logic for default model
            model = "gpt-4o" # or whatever is default for these providers
            if model_key and live_settings.get(model_key):
                model = live_settings.get(model_key)
            
            if not base_url:
                if provider_type == "nvidia": base_url = "https://integrate.api.nvidia.com/v1"
                elif provider_type == "alibaba": base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
                elif provider_type == "ollama": base_url = "http://localhost:11434/v1"
                elif provider_type == "openai": base_url = "https://api.openai.com/v1"
            return OpenAICompatibleProvider(api_key, base_url, model)
        else:
            raise ValueError(f"Unsupported AI provider: {provider_type}")

    @staticmethod
    def list_models() -> List[Dict[str, Any]]:
        return AIService.get_provider().list_models()
