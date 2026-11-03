import os
import jinja2
from typing import Any, Callable, Dict, Optional
from app.services import content_guard
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

    # Every template can call {{ writing_style("comment") }} etc. (Configurações → Estilo e modelos)
    @staticmethod
    def _writing_style(kind: str) -> str:
        from app.services.ai_settings_service import AISettingsService
        try:
            return AISettingsService.render(kind)
        except Exception:
            return ""

    _env.globals["writing_style"] = _writing_style.__func__

    # {{ line_of_thought(text) }}: the professional's positions and what they already said on topics close to text
    @staticmethod
    def _line_of_thought(text: str = "") -> str:
        from app.services.linkedin_voice_service import VoiceService
        try:
            return VoiceService.prompt_block(text or "")
        except Exception:
            return ""

    _env.globals["line_of_thought"] = _line_of_thought.__func__

    # Skills that write text people will read use the "writing" model; the rest use the default one
    WRITING_SKILLS = {"jobs/resume.md", "resumes/improve.md", "jobs/cover_letter.md", "jobs/outreach.md", "interview/stories.md", "interview/simulate.md"}

    # Skills whose text reaches other people: they go through the content guard (config/automation.yml)
    OUTGOING_SKILLS = {
        "jobs/resume.md", "jobs/cover_letter.md", "jobs/outreach.md", "resumes/improve.md", "resumes/form_suggestions.md",
        "onboarding/update_resume.md", "linkedin/easy_apply.md", "linkedin/engagement_comment.md", "linkedin/engagement_reply.md",
        "linkedin/post_drafts.md", "linkedin/prospect_note.md", "linkedin/prospect_message.md", "linkedin/networking_plan.md",
    }

    @classmethod
    async def render_prompt(cls, skill_path: str, context: Dict[str, Any]) -> str:
        """Renders a Jinja2 template with the given context."""
        template = cls._env.get_template(skill_path)
        prompt = template.render(**context)
        return prompt + content_guard.prompt_rule(prompt) if skill_path in cls.OUTGOING_SKILLS else prompt

    @classmethod
    def generate_checked(cls, skill_path: str, prompt: str, generate: Callable[[str], Any]) -> Any:
        """Calls the AI. A text to be sent that cites a forbidden subject is written once more; if it still does, the sentences
        that cite it are dropped; if that would cut too much, it is refused."""
        result = generate(prompt)
        if skill_path not in cls.OUTGOING_SKILLS:
            return result
        found = content_guard.forbidden_in(result)
        if found:
            result = content_guard.scrub(generate(prompt + content_guard.retry_rule(found)))
            content_guard.ensure_clean(result, "O texto gerado")
        return result

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
            "resumes": "optimizer",
            "interview": "interview",
            "analytics": "optimizer",
            "linkedin": "outreach"
        }
        
        target_domain = domain_mapping.get(domain, domain)
        model_key = "ai_model_writing" if skill_path in cls.WRITING_SKILLS else f"ai_model_{target_domain}"
        
        provider = AIService.get_provider(model_key)
        prompt = await cls.render_prompt(skill_path, context)
        
        generate = provider.generate_json if response_format == "json" else provider.generate_text
        return cls.generate_checked(skill_path, prompt, generate)
