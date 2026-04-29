"""
AI Provider Abstraction Layer

Supports multiple AI providers via a unified interface:
- Gemini (Google)
- NVIDIA NIM (OpenAI-compatible)
- Alibaba DashScope (OpenAI-compatible)
- Ollama (local, OpenAI-compatible)
- Any OpenAI-compatible endpoint

Usage:
    from ai_provider import get_provider
    provider = get_provider()
    result = provider.generate_text(prompt)
    result = provider.generate_json(prompt)
"""
import os
import json
import re
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)

# Provider constants
PROVIDER_GEMINI = "gemini"
PROVIDER_NVIDIA = "nvidia"
PROVIDER_ALIBABA = "alibaba"
PROVIDER_OLLAMA = "ollama"
PROVIDER_OPENAI = "openai"
PROVIDER_CUSTOM = "custom"

VALID_PROVIDERS = [PROVIDER_GEMINI, PROVIDER_NVIDIA, PROVIDER_ALIBABA, PROVIDER_OLLAMA, PROVIDER_OPENAI, PROVIDER_CUSTOM]

# Default models per provider
DEFAULT_MODELS = {
    PROVIDER_GEMINI: "gemini-2.0-flash",
    PROVIDER_NVIDIA: "meta/llama-3.1-70b-instruct",
    PROVIDER_ALIBABA: "qwen-max",
    PROVIDER_OLLAMA: "llama3.1:8b",
    PROVIDER_OPENAI: "gpt-4o-mini",
    PROVIDER_CUSTOM: "",
}

# NVIDIA NIM models (free tier available)
NVIDIA_MODELS = [
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.2-3b-instruct",
    "mistralai/mistral-large-2-instruct",
    "mistralai/mixtral-8x22b-instruct-v0.1",
    "nvidia/nemotron-4-340b-instruct",
    "google/gemma-2-27b-it",
    "google/codegemma-1.1-7b",
    "microsoft/phi-3-mini-128k-instruct",
    "microsoft/phi-3-medium-128k-instruct",
]

# Alibaba DashScope models (free tier available)
ALIBABA_MODELS = [
    "qwen-max",
    "qwen-plus",
    "qwen-turbo",
    "qwen-long",
    "qwen-vl-max",
    "qwen-coder-plus",
]

# Ollama popular models
OLLAMA_MODELS = [
    "llama3.1:8b",
    "llama3.1:70b",
    "llama3.2:3b",
    "mistral:7b",
    "mixtral:8x7b",
    "qwen2.5:7b",
    "qwen2.5:72b",
    "gemma2:9b",
    "phi3:3.8b",
    "deepseek-coder:6.7b",
]


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        """Generate text from a prompt."""
        pass

    @abstractmethod
    def generate_json(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> dict:
        """Generate JSON output from a prompt."""
        pass

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available models for this provider."""
        pass

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Test connection to the provider. Returns (success, message)."""
        pass


class GeminiProvider(AIProvider):
    """Google Gemini provider using google-generativeai library."""

    def __init__(self, api_key: str, default_model: Optional[str] = None):
        import google.generativeai as genai
        self.genai = genai
        self.api_key = api_key
        self.default_model = default_model or DEFAULT_MODELS[PROVIDER_GEMINI]
        self.genai.configure(api_key=self.api_key)

    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        model_name = model or self.default_model
        try:
            gen_model = self.genai.GenerativeModel(model_name)
            response = gen_model.generate_content(
                prompt,
                generation_config=self.genai.types.GenerationConfig(
                    temperature=temperature,
                ),
            )
            return response.text.strip() if response.text else ""
        except Exception as e:
            logger.error(f"Gemini text generation error: {e}")
            return f"Error: {str(e)}"

    def generate_json(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> dict:
        model_name = model or self.default_model
        try:
            gen_model = self.genai.GenerativeModel(model_name)
            response = gen_model.generate_content(
                prompt,
                generation_config=self.genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=temperature,
                ),
            )
            text = response.text.strip() if response.text else "{}"
            return self._extract_json(text)
        except Exception as e:
            logger.error(f"Gemini JSON generation error: {e}")
            return {"error": str(e)}

    def list_models(self) -> list[str]:
        try:
            models = []
            for m in self.genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    name = m.name.replace("models/", "")
                    models.append(name)
            return models
        except Exception as e:
            logger.error(f"Gemini list models error: {e}")
            return [DEFAULT_MODELS[PROVIDER_GEMINI]]

    def test_connection(self) -> tuple[bool, str]:
        try:
            models = self.list_models()
            if models:
                return True, f"Connected. {len(models)} models available."
            return False, "No models found."
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def _extract_json(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
        return {"raw_text": text}


class OpenAICompatibleProvider(AIProvider):
    """Provider for any OpenAI-compatible API (NVIDIA, Alibaba, Ollama, custom)."""

    def __init__(self, api_key: str, base_url: str, default_model: Optional[str] = None, provider_name: str = "OpenAI Compatible"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model or "default"
        self.provider_name = provider_name

    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        model_name = model or self.default_model
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            return response.choices[0].message.content.strip() if response.choices else ""
        except Exception as e:
            logger.error(f"{self.provider_name} text generation error: {e}")
            return f"Error: {str(e)}"

    def generate_json(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> dict:
        model_name = model or self.default_model
        json_prompt = prompt + "\n\nRespond ONLY with valid JSON. No markdown, no explanation."
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": json_prompt}],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content.strip() if response.choices else "{}"
            return json.loads(text)
        except Exception as e:
            logger.error(f"{self.provider_name} JSON generation error: {e}")
            return {"error": str(e)}

    def list_models(self) -> list[str]:
        try:
            response = self.client.models.list()
            return [m.id for m in response.data] if response.data else [self.default_model]
        except Exception as e:
            logger.error(f"{self.provider_name} list models error: {e}")
            return [self.default_model]

    def test_connection(self) -> tuple[bool, str]:
        try:
            response = self.client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "Say 'OK' in one word."}],
                max_tokens=10,
            )
            if response.choices:
                return True, f"Connected to {self.provider_name} ({self.default_model})."
            return False, "No response from model."
        except Exception as e:
            return False, f"Connection failed: {str(e)}"


def create_provider(provider_type: Optional[str] = None,
                    api_key: Optional[str] = None,
                    base_url: Optional[str] = None,
                    model: Optional[str] = None) -> AIProvider:
    """
    Factory function to create an AI provider instance.

    Args:
        provider_type: One of 'gemini', 'nvidia', 'alibaba', 'ollama', 'openai', 'custom'
        api_key: API key (not needed for Ollama local)
        base_url: Base URL for OpenAI-compatible providers
        model: Model name to use

    Returns:
        AIProvider instance
    """
    ptype = (provider_type or os.getenv("AI_PROVIDER", PROVIDER_GEMINI)).lower().strip()
    key = api_key or os.getenv("AI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    burl = base_url or os.getenv("AI_BASE_URL", "")
    mdl = model or os.getenv("AI_MODEL", "")

    if ptype == PROVIDER_GEMINI:
        if not mdl:
            mdl = DEFAULT_MODELS[PROVIDER_GEMINI]
        return GeminiProvider(api_key=key, default_model=mdl)

    elif ptype == PROVIDER_NVIDIA:
        if not burl:
            burl = "https://integrate.api.nvidia.com/v1"
        if not mdl:
            mdl = DEFAULT_MODELS[PROVIDER_NVIDIA]
        return OpenAICompatibleProvider(api_key=key, base_url=burl, default_model=mdl, provider_name="NVIDIA NIM")

    elif ptype == PROVIDER_ALIBABA:
        if not burl:
            burl = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        if not mdl:
            mdl = DEFAULT_MODELS[PROVIDER_ALIBABA]
        return OpenAICompatibleProvider(api_key=key, base_url=burl, default_model=mdl, provider_name="Alibaba DashScope")

    elif ptype == PROVIDER_OLLAMA:
        if not burl:
            burl = "http://localhost:11434/v1"
        if not mdl:
            mdl = DEFAULT_MODELS[PROVIDER_OLLAMA]
        ollama_key = key or "ollama"
        return OpenAICompatibleProvider(api_key=ollama_key, base_url=burl, default_model=mdl, provider_name="Ollama")

    elif ptype == PROVIDER_OPENAI:
        if not mdl:
            mdl = DEFAULT_MODELS[PROVIDER_OPENAI]
        return OpenAICompatibleProvider(api_key=key, base_url=burl or "https://api.openai.com/v1", default_model=mdl, provider_name="OpenAI")

    elif ptype == PROVIDER_CUSTOM:
        if not burl:
            raise ValueError("AI_BASE_URL is required for custom provider")
        if not mdl:
            raise ValueError("AI_MODEL is required for custom provider")
        return OpenAICompatibleProvider(api_key=key, base_url=burl, default_model=mdl, provider_name="Custom")

    else:
        raise ValueError(f"Unknown provider: {ptype}. Valid: {VALID_PROVIDERS}")


_provider_cache: dict[str, AIProvider] = {}


def get_provider(refresh: bool = False) -> AIProvider:
    """
    Get or create the AI provider singleton.
    Caches the provider based on environment config.
    """
    cache_key = os.getenv("AI_PROVIDER", PROVIDER_GEMINI)
    if not refresh and cache_key in _provider_cache:
        return _provider_cache[cache_key]

    provider = create_provider()
    _provider_cache[cache_key] = provider
    return provider


def get_available_models(provider_type: Optional[str] = None) -> dict[str, list[str]]:
    """
    Get available models for all providers or a specific provider.
    Returns dict of {provider_name: [models]}.
    """
    all_models = {}

    if provider_type and provider_type != PROVIDER_GEMINI:
        all_models[provider_type] = _get_static_models(provider_type)
        return all_models

    if provider_type == PROVIDER_GEMINI or not provider_type:
        try:
            provider = create_provider(PROVIDER_GEMINI)
            all_models[PROVIDER_GEMINI] = provider.list_models()
        except Exception:
            all_models[PROVIDER_GEMINI] = [DEFAULT_MODELS[PROVIDER_GEMINI]]

    all_models[PROVIDER_NVIDIA] = NVIDIA_MODELS
    all_models[PROVIDER_ALIBABA] = ALIBABA_MODELS
    all_models[PROVIDER_OLLAMA] = OLLAMA_MODELS
    all_models[PROVIDER_OPENAI] = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

    return all_models


def _get_static_models(provider_type: str) -> list[str]:
    """Get static model list for a provider (no API call needed)."""
    return {
        PROVIDER_NVIDIA: NVIDIA_MODELS,
        PROVIDER_ALIBABA: ALIBABA_MODELS,
        PROVIDER_OLLAMA: OLLAMA_MODELS,
        PROVIDER_OPENAI: ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    }.get(provider_type, [])


def get_provider_info() -> dict:
    """Get current provider configuration info."""
    ptype = os.getenv("AI_PROVIDER", PROVIDER_GEMINI)
    model = os.getenv("AI_MODEL", DEFAULT_MODELS.get(ptype, ""))
    base_url = os.getenv("AI_BASE_URL", "")
    has_key = bool(os.getenv("AI_API_KEY", "") or os.getenv("GEMINI_API_KEY", ""))

    return {
        "provider": ptype,
        "model": model,
        "base_url": base_url if ptype != PROVIDER_GEMINI else "N/A",
        "has_api_key": has_key,
        "valid_providers": VALID_PROVIDERS,
    }
