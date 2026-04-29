import yaml
import os
import json
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor
from app.services.ai_service import AIService

class ProfileService:
    @staticmethod
    def get_profile() -> dict:
        print(f"DEBUG: Reading profile from {settings.PROFILE_FILE}")
        if settings.PROFILE_FILE.exists():
            try:
                with open(settings.PROFILE_FILE, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    print(f"DEBUG: Loaded data: {data.get('personal', {}).get('name', 'NAME_NOT_FOUND')}")
                    return data
            except Exception as e:
                print(f"DEBUG: Error reading profile: {e}")
        else:
            print("DEBUG: Profile file does not exist!")
        return {}

    @staticmethod
    def save_profile(profile: dict):
        settings.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(settings.PROFILE_FILE, "w", encoding="utf-8") as f:
            yaml.dump(profile, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    @staticmethod
    def get_resume_base() -> str:
        if settings.RESUME_BASE_FILE.exists():
            return settings.RESUME_BASE_FILE.read_text(encoding="utf-8")
        return ""

    @staticmethod
    def save_resume_base(content: str):
        settings.RESUME_BASE_FILE.write_text(content, encoding="utf-8")

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

        provider = AIService.get_provider()
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
        response_text = provider.generate_text(prompt)
        
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
    async def import_from_linkedin() -> dict:
        from app.services.scraper_service import ScraperService
        extracted = await ScraperService.scrape_own_profile()
        if extracted and not extracted.get("error"):
            # Merge with existing profile
            current = ProfileService.get_profile()
            current["personal"] = {**(current.get("personal", {})), **extracted.get("personal", {})}
            
            # Use PT as primary but fallback to EN if empty
            current["about"] = extracted.get("pt", {}).get("about") or extracted.get("en", {}).get("about") or current.get("about", "")
            current["experience"] = extracted.get("experience", [])
            current["skills"] = extracted.get("skills", [])
            
            ProfileService.save_profile(current)
        return extracted

    @staticmethod
    async def optimize_section(section: str, content: str) -> str:
        provider = AIService.get_provider()
        prompt = f"""
        You are a career consultant expert in LinkedIn and Resume optimization.
        Optimize the following '{section}' section of a professional profile.
        Make it more impactful, results-oriented, and include relevant keywords for Applicant Tracking Systems (ATS).
        Use professional language and maintain the original language (PT or EN).
        
        Original Content:
        {content}
        
        Return ONLY the optimized text, without explanations.
        """
        return provider.generate_text(prompt)

    @staticmethod
    async def get_profile_score(profile_md: str) -> Dict[str, Any]:
        """Calculates a profile score and saves it to DB."""
        provider = AIService.get_provider()
        prompt = f"""
        Score the following candidate profile from 0 to 100.
        Profile MD: {profile_md}
        
        Respond with JSON:
        {{
            "score": 0-100,
            "reason": "summary of strengths and weaknesses",
            "tips": ["tip1", "tip2"]
        }}
        """
        result = provider.generate_json(prompt)
        
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.profile_stats (score, analysis, updated_at)
                VALUES (%s, %s, NOW())
            """, (result['score'], result['reason']))
        conn.commit()
        conn.close()
        return result

    @staticmethod
    async def generate_ssi_plan(profile_md: str) -> str:
        """Generates a Social Selling Index (SSI) improvement plan."""
        provider = AIService.get_provider()
        prompt = f"""
        Generate a detailed weekly plan to improve the Social Selling Index (SSI) for this profile.
        Profile: {profile_md}
        Focus on: Establishing professional brand, finding the right people, engaging with insights, and building relationships.
        """
        return provider.generate_text(prompt)

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
                for key in ["name", "headline", "about", "experience", "education", "skills"]:
                    val = ai_data.get(key)
                    # If extension didn't send structured list, or it's empty, use AI results
                    if val and (not data.get(key) or (isinstance(data.get(key), list) and len(data.get(key)) == 0)):
                        data[key] = val
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
        current["about"] = data.get("about") or current.get("about", "")
        current["experience"] = data.get("experience") or current.get("experience", [])
        current["education"] = data.get("education") or current.get("education", [])
        current["skills"] = data.get("skills") or current.get("skills", [])
        
        ProfileService.save_profile(current)
        return current

    @staticmethod
    async def import_profile_ai(raw_text: str):
        if not raw_text or len(raw_text) < 50:
            return {}

        from app.services.ai_service import AIService
        provider = AIService.get_provider()
        
        import re
        # Smarter HTML cleaning: replace tags with newlines to preserve structure
        clean_text = re.sub(r'<br\s*/?>', '\n', raw_text)
        clean_text = re.sub(r'</?(div|p|li|h1|h2|h3|section|article)[^>]*>', '\n', clean_text)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
        clean_text = re.sub(r'\n\s*\n', '\n', clean_text) # Remove excessive newlines
        clean_text = re.sub(r' {2,}', ' ', clean_text).strip()
        
        prompt = f"""
        Extract professional information from this LinkedIn profile (Raw Dump) and return it as JSON.
        
        CRITICAL RULES:
        1. YOU MUST EXTRACT EVERY SINGLE ROLE AND EDUCATION ENTRY. No summaries.
        2. Separate roles at the same company into separate experience objects.
        3. The text is messy (extracted from HTML). Look for patterns like "Company Name", "Role", "Date Range".
        
        JSON Structure:
        - name: Full name
        - headline: Current professional headline
        - about: Professional summary
        - experience: Array of {{ "company": "...", "role": "...", "period": "...", "description": "..." }}
        - education: Array of {{ "institution": "...", "degree": "...", "year": "..." }}
        - skills: A FLAT ARRAY of strings
        
        Profile Content:
        {clean_text[:45000]}
        """
        
        try:
            result = provider.generate_json(prompt)
            # Ensure skills is a list
            if isinstance(result.get("skills"), dict):
                # Flatten skills if it came back as an object
                flat_skills = []
                for k, v in result["skills"].items():
                    if isinstance(v, list): flat_skills.extend(v)
                result["skills"] = flat_skills
            
            return result
        except Exception as e:
            print(f"AI Extraction error: {e}")
            return {}
