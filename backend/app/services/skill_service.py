import os
import jinja2
from typing import Any, Dict, Optional
from app.services.ai_service import AIService

class SkillService:
    # Initialize Jinja2 environment
    # Inside container, skills are at /app/app/skills
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SKILLS_DIR = os.path.join(BASE_DIR, "skills")
    
    _env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(SKILLS_DIR),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True
    )

    @classmethod
    async def render_prompt(cls, skill_path: str, context: Dict[str, Any]) -> str:
        """Renders a Jinja2 template with the given context."""
        template = cls._env.get_template(skill_path)
        return template.render(**context)

    @classmethod
    async def run_skill(cls, skill_path: str, context: Dict[str, Any], response_format: str = "json") -> Any:
        """
        Executes an AI skill by rendering its prompt and calling the AI provider.
        Automatically routes to the correct model based on the skill category.
        """
        # Determine model domain from skill_path (e.g., 'profile/optimize.md' -> 'profile')
        domain = skill_path.split('/')[0] if '/' in skill_path else "chat"
        
        # Map directory domains to settings keys
        domain_mapping = {
            "profile": "optimizer",
            "onboarding": "import",
            "knowledge": "import",
            "jobs": "optimizer",
            "interview": "interview",
            "analytics": "optimizer"
        }
        
        target_domain = domain_mapping.get(domain, domain)
        model_key = f"ai_model_{target_domain}"
        
        provider = AIService.get_provider(model_key)
        prompt = await cls.render_prompt(skill_path, context)
        
        if response_format == "json":
            return provider.generate_json(prompt)
        else:
            return provider.generate_text(prompt)
