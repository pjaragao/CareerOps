import yaml
import asyncio
import os
import json
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor
from app.services.ai_service import AIService
from app.services.skill_service import SkillService

class ProfileService:
    @staticmethod
    def get_profile() -> dict:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT full_data as data, updated_at, last_audit_at FROM public.user_profiles WHERE id = 1")
                row = cur.fetchone()
                if row and row['data']:
                    data = row['data']
                    if "languages" not in data:
                        data["languages"] = {}
                    
                    # Inject metadata for frontend use
                    data["_metadata"] = {
                        "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None,
                        "last_audit_at": row['last_audit_at'].isoformat() if row['last_audit_at'] else None
                    }
                    return data
        except Exception as e:
            print(f"DEBUG: Error reading profile: {e}")
        finally:
            conn.close()
        
        return {"personal": {}, "languages": {}, "preferences": {}, "_metadata": {"updated_at": None, "last_audit_at": None}}

    @staticmethod
    def save_profile(profile: dict):
        conn = get_db_connection()
        try:
            # Remove metadata before saving if present
            save_data = {k: v for k, v in profile.items() if k != "_metadata"}
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.user_profiles (id, full_data, updated_at) 
                    VALUES (1, %s, NOW()) 
                    ON CONFLICT (id) DO UPDATE SET full_data = EXCLUDED.full_data, updated_at = NOW()
                """, (json.dumps(save_data),))
            conn.commit()
            
            # Optionally write back to YAML for local backup
            settings.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(settings.PROFILE_FILE, "w", encoding="utf-8") as f:
                yaml.dump(save_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        except Exception as e:
            print(f"DEBUG: Error saving profile to DB: {e}")
        finally:
            conn.close()

    @staticmethod
    def _resume_file(lang: str = "en"):
        return settings.RESUME_BASE_PT_FILE if (lang or "").lower().startswith("p") else settings.RESUME_BASE_FILE

    @staticmethod
    def get_resume_base(lang: str = "en") -> str:
        """Master CV: "en" = abroad (data, finance, modeling), "pt" = Brazil (engineering, sanitation, modeling)."""
        path = ProfileService._resume_file(lang)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    @staticmethod
    def save_resume_base(content: str, lang: str = "en"):
        ProfileService._resume_file(lang).write_text(content, encoding="utf-8")

    @staticmethod
    def get_latest_stats() -> Optional[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.profile_stats ORDER BY updated_at DESC LIMIT 1")
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    async def extract_info_from_resume(file_content: bytes, filename: str) -> dict:
        text = ""
        if filename.lower().endswith(".pdf"):
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_content))
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif filename.lower().endswith(".docx"):
            import io
            from docx import Document
            doc = Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            text = file_content.decode("utf-8", errors="ignore")

        provider = AIService.get_provider("ai_model_import")
        prompt = f"""
        Extract professional information from the following resume text and return it in a strictly valid JSON format.
        The JSON should have these sections:
        - personal: name, email, phone, location, linkedin, github, website
        - legal: visa_status, gender, ethnicity, disability, veteran, work_auth
        - preferences: target_role, min_salary, work_mode, experience_level
        - experience: [ { company, role, period, description } ]
        - education: [ { institution, degree, year } ]
        - skills: [ list of tech skills ]
        - keywords: [ list of search keywords ]

        Resume text:
        {text}
        """
        response_text = await asyncio.to_thread(provider.generate_text, prompt)
        
        # Robust JSON extraction
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)
        
        try:
            return json.loads(response_text)
        except Exception as e:
            print(f"AI parsing error: {e}")
            print(f"Raw response: {response_text}")
            return {"error": "Failed to parse AI response", "raw": response_text}
    @staticmethod
    def _get_flattened_profile(profile: dict, lang: str = "pt") -> dict:
        """Flattens a multi-language profile into a single structure for a specific language."""
        lang_data = profile.get("languages", {}).get(lang, {})
        flattened = {**profile}
        # Merge language specific data to root level for backward compatibility with AI prompts
        for field in ["about", "experience", "skills", "education"]:
            if lang_data.get(field):
                flattened[field] = lang_data[field]
        return flattened

    @staticmethod
    async def save_profile_from_extension(data: dict):
        current = ProfileService.get_profile()
        
        # Consolidate raw segments for robust AI processing
        # This reduces noise by focusing on relevant sections
        segmented_text = f"""
        NAME: {data.get('name', '')}
        HEADLINE: {data.get('headline', '')}
        ABOUT: {data.get('about_raw', '')}
        EXPERIENCE: {data.get('experience_raw', '')}
        EDUCATION: {data.get('education_raw', '')}
        SKILLS: {data.get('skills_raw', '')}
        FULL_PAGE_DUMP: {data.get('full_page_text', '')[:50000]}
        CONTACT_INFO: {data.get('email', '')} | {data.get('phone', '')}
        """
        
        print(f"DEBUG: Processing extension data for {data.get('name', 'Unknown')}")
        
        # Physical Audit Log: Save exactly what was received to a file
        try:
            log_dir = os.path.join(os.path.dirname(settings.CONFIG_DIR), "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "debug_payload.json")
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"DEBUG: Raw payload saved to {log_path}")
        except Exception as log_err:
            print(f"DEBUG: Failed to save audit log: {log_err}")
            
        try:
            ai_data = await ProfileService.import_profile_ai(segmented_text)
            if ai_data:
                print(f"DEBUG: AI returned experience count: {len(ai_data.get('experience', []))}")
                # Merge AI data into our structured data if extension didn't provide it
                for key in ["name", "headline"]:
                    val = ai_data.get(key)
                    if val and not data.get(key):
                        data[key] = val
                
                if ai_data.get("languages"):
                    data["languages"] = ai_data.get("languages")
        except Exception as e:
            print(f"DEBUG: AI Processing failed: {e}")

        # Mapping extension data to profile structure (Matching Frontend keys)
        current["personal"] = {
            "name": data.get("name") or current.get("personal", {}).get("name", ""),
            "email": data.get("email") or current.get("personal", {}).get("email", ""),
            "phone": data.get("phone") or current.get("personal", {}).get("phone", ""),
            "location": data.get("location") or current.get("personal", {}).get("location", ""),
            "linkedin": data.get("linkedin_url") or data.get("linkedin") or current.get("personal", {}).get("linkedin", ""),
            "github": data.get("github") or current.get("personal", {}).get("github", "")
        }
        
        if "languages" not in current:
            current["languages"] = {}
            
        ai_languages = data.get("languages", {})
        if not ai_languages:
            # Fallback if AI didn't format as languages
            if "pt" not in current["languages"]:
                current["languages"]["pt"] = {}
            current["languages"]["pt"]["about"] = data.get("about") or current["languages"]["pt"].get("about", "")
            current["languages"]["pt"]["experience"] = data.get("experience") or current["languages"]["pt"].get("experience", [])
            current["languages"]["pt"]["education"] = data.get("education") or current["languages"]["pt"].get("education", [])
            current["languages"]["pt"]["skills"] = data.get("skills") or current["languages"]["pt"].get("skills", [])
        else:
            for lang, lang_data in ai_languages.items():
                if lang not in current["languages"]:
                    current["languages"][lang] = {}
                current["languages"][lang]["about"] = lang_data.get("about") or current["languages"][lang].get("about", "")
                current["languages"][lang]["experience"] = lang_data.get("experience") or current["languages"][lang].get("experience", [])
                current["languages"][lang]["education"] = lang_data.get("education") or current["languages"][lang].get("education", [])
                current["languages"][lang]["skills"] = lang_data.get("skills") or current["languages"][lang].get("skills", [])
        
        ProfileService.save_profile(current)
        return current

    @staticmethod
    async def import_profile_ai(raw_text: str):
        if not raw_text or len(raw_text) < 50:
            return {}

        import re
        # Smarter HTML cleaning: replace tags with newlines to preserve structure
        clean_text = re.sub(r'<br\s*/?>', '\n', raw_text)
        clean_text = re.sub(r'</?(div|p|li|h1|h2|h3|section|article)[^>]*>', '\n', clean_text)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
        clean_text = re.sub(r'\n\s*\n', '\n', clean_text) # Remove excessive newlines
        clean_text = re.sub(r' {2,}', ' ', clean_text).strip()
        
        try:
            result = await SkillService.run_skill(
                "profile/import.md",
                {"raw_text": clean_text[:45000]}
            )
            
            if isinstance(result, list):
                result = result[0] if len(result) > 0 else {}
                
            # Ensure skills is a list
            languages = result.get("languages", {})
            for lang, lang_data in languages.items():
                if isinstance(lang_data.get("skills"), dict):
                    flat_skills = []
                    for k, v in lang_data["skills"].items():
                        if isinstance(v, list): flat_skills.extend(v)
                    lang_data["skills"] = flat_skills
            
            return result
        except Exception as e:
            print(f"AI Extraction error: {e}")
            return {}
