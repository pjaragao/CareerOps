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
    def _ensure_table_exists():
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.optimizer_analyses (
                        id SERIAL PRIMARY KEY,
                        analysis_type TEXT NOT NULL,
                        lang TEXT DEFAULT 'pt',
                        strategy_context JSONB,
                        results JSONB NOT NULL,
                        profile_snapshot JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_optimizer_analyses_type ON public.optimizer_analyses(analysis_type);
                    CREATE INDEX IF NOT EXISTS idx_optimizer_analyses_created ON public.optimizer_analyses(created_at DESC);
                """)
            conn.commit()
        except Exception as e:
            print(f"DEBUG: Error auto-creating table: {e}")
        finally:
            conn.close()

    @staticmethod
    def save_analysis(analysis_type: str, lang: str, strategy_context: Optional[dict], results: dict, profile_snapshot: dict):
        ProfileService._ensure_table_exists()
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.optimizer_analyses (analysis_type, lang, strategy_context, results, profile_snapshot, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (analysis_type, lang, json.dumps(strategy_context) if strategy_context else None, json.dumps(results), json.dumps(profile_snapshot)))
                
                # If it's a full audit, update the profile's last_audit_at timestamp
                if analysis_type == "full_audit":
                    cur.execute("UPDATE public.user_profiles SET last_audit_at = NOW() WHERE id = 1")
                    
            conn.commit()
        except Exception as e:
            print(f"DEBUG: Error saving analysis: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_latest_analysis(analysis_type: str) -> Optional[dict]:
        ProfileService._ensure_table_exists()
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("""
                    SELECT * FROM public.optimizer_analyses 
                    WHERE analysis_type = %s 
                    ORDER BY created_at DESC LIMIT 1
                """, (analysis_type,))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"DEBUG: Error fetching latest analysis: {e}")
            return None
        finally:
            conn.close()
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
    async def import_from_linkedin() -> dict:
        from app.services.scraper_service import ScraperService
        extracted = await ScraperService.scrape_own_profile()
        if extracted and not extracted.get("error"):
            # Merge with existing profile
            current = ProfileService.get_profile()
            current["personal"] = {**(current.get("personal", {})), **extracted.get("personal", {})}
            
            if "languages" not in current:
                current["languages"] = {}
                
            for lang in ["pt", "en"]:
                if extracted.get(lang):
                    if lang not in current["languages"]:
                        current["languages"][lang] = {}
                    for field in ["about", "experience", "skills", "education"]:
                        if extracted[lang].get(field):
                            current["languages"][lang][field] = extracted[lang][field]
            
            ProfileService.save_profile(current)
        return extracted

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
    def _format_strategy_context(strategy_context: Optional[dict] = None) -> str:
        if not strategy_context:
            return ""
        
        ctx_type = strategy_context.get("type")
        label = strategy_context.get("label", "")
        keywords = strategy_context.get("keywords", [])
        
        # Filter out None values that might come from undefined frontend fields
        safe_keywords = [str(k) for k in keywords if k]
        
        anti_hallucination = "\nCRITICAL RULE 1: Rely ONLY on the candidate's actual profile and the provided job keywords. DO NOT hallucinate or invent technologies/industries (e.g., Web3, blockchain) based on the target company's name.\nCRITICAL RULE 2: DO NOT mention the target company's name explicitly in your output. LinkedIn profiles must remain company-agnostic while still demonstrating strong synergy with the target role."
        
        if ctx_type == "strategy":
            return f"\nTARGET STRATEGY CONTEXT:\n- Target: {label}\n- Key Keywords to Include: {', '.join(safe_keywords)}\nMake sure to strongly align the content with this target strategy and include these keywords naturally.{anti_hallucination}"
        elif ctx_type == "job":
            return f"\nTARGET JOB CONTEXT:\n- Target Role/Company: {label}\n- Job Keywords/Description context: {', '.join(safe_keywords)}\nMake sure to strongly align the content with this specific job opportunity.{anti_hallucination}"
        elif ctx_type == "custom":
            return f"\nTARGET ROLE CONTEXT:\n- Target Role: {label}\nMake sure to strongly align the content to appeal to recruiters hiring for this role.{anti_hallucination}"
        
        return ""

    @staticmethod
    async def optimize_section(section: str, content: str, lang: str = "pt", strategy_context: Optional[dict] = None) -> str:
        lang_name = "Portuguese" if lang == "pt" else "English"
        context_prompt = ProfileService._format_strategy_context(strategy_context)
        
        return await SkillService.run_skill(
            "profile/optimize_section.md",
            {
                "section": section,
                "content": content,
                "lang_name": lang_name,
                "strategy_context_prompt": context_prompt
            },
            response_format="text"
        )

    @staticmethod
    async def get_profile_score(profile_md: str) -> Dict[str, Any]:
        """Calculates a profile score and saves it to DB."""
        result = await SkillService.run_skill(
            "profile/score_profile.md",
            {"profile_text": profile_md}
        )
        
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
        return await SkillService.run_skill(
            "profile/simulate_ssi.md",
            {"profile_summary": profile_md},
            response_format="text"
        )

    @staticmethod
    async def simulate_ssi(profile: dict, lang: str = "pt") -> Dict[str, Any]:
        """Simulates SSI score across 4 LinkedIn pillars based on profile completeness."""
        p = ProfileService._get_flattened_profile(profile, lang)
        
        profile_summary = json.dumps({
            "name": p.get("personal", {}).get("name"),
            "headline": p.get("personal", {}).get("headline"),
            "about": (p.get("about") or "")[:500],
            "experience_count": len(p.get("experience", [])),
            "skills_count": len(p.get("skills", [])),
            "education_count": len(p.get("education", [])),
            "has_photo": bool(p.get("personal", {}).get("name")),
            "has_linkedin": bool(p.get("personal", {}).get("linkedin")),
            "has_github": bool(p.get("personal", {}).get("github")),
        }, ensure_ascii=False)

        return await SkillService.run_skill(
            "profile/simulate_ssi.md",
            {"profile_summary": profile_summary}
        )

    @staticmethod
    async def analyze_skills(profile: dict, target_role: str, strategy_context: Optional[dict] = None, lang: str = "pt") -> Dict[str, Any]:
        """Analyzes skills gap vs target role and categorizes them."""
        p = ProfileService._get_flattened_profile(profile, lang)
        current_skills = p.get("skills", [])
        context_prompt = ProfileService._format_strategy_context(strategy_context)
        
        return await SkillService.run_skill(
            "profile/analyze_skills.md",
            {
                "target_role": target_role,
                "skills": current_skills,
                "strategy_context_prompt": context_prompt
            }
        )

    @staticmethod
    async def optimize_experience_bullets(experience_list: list, lang: str = "pt", strategy_context: Optional[dict] = None) -> List[Dict[str, Any]]:
        """Rewrites each experience with impact statements and action verbs."""
        lang_name = "Portuguese" if lang == "pt" else "English"
        context_prompt = ProfileService._format_strategy_context(strategy_context)
        
        results = []
        for exp in experience_list:
            result = await SkillService.run_skill(
                "profile/optimize_experience.md",
                {
                    "role": exp.get('role', ''),
                    "company": exp.get('company', ''),
                    "period": exp.get('period', ''),
                    "description": exp.get('description', ''),
                    "lang_name": lang_name,
                    "strategy_context_prompt": context_prompt
                }
            )
            results.append(result)
        return results

    @staticmethod
    async def restructure_experience_profile(lang: str = "pt", strategy_context: Optional[dict] = None) -> Dict[str, Any]:
        """Restructures the entire experience section by competency using Resume Base and STAR cases."""
        lang_name = "Portuguese" if lang == "pt" else "English"
        profile = ProfileService.get_profile()
        p = ProfileService._get_flattened_profile(profile, lang)
        
        experience_list = json.dumps(p.get("experience", []), ensure_ascii=False)
        resume_base = ProfileService.get_resume_base()
        
        results = await SkillService.run_skill(
            "profile/restructure_experience.md",
            {
                "experience_list": experience_list,
                "resume_base": resume_base,
                "lang_name": lang_name
            }
        )
        
        # Persist the results for later viewing
        ProfileService.save_analysis(
            "restructure_experience",
            lang,
            strategy_context,
            results,
            profile
        )
        
        return results

    @staticmethod
    async def generate_headline_variants(profile: dict, lang: str = "pt", count: int = 3, strategy_context: Optional[dict] = None) -> Dict[str, Any]:
        """Generates N optimized headline variants with character counts."""
        lang_name = "Portuguese" if lang == "pt" else "English"
        p = ProfileService._get_flattened_profile(profile, lang)
        
        personal = p.get("personal", {})
        skills = p.get("skills", [])[:15]
        experience = p.get("experience", [])
        current_role = experience[0].get("role", "") if experience else ""
        target_role = p.get("preferences", {}).get("target_role", current_role)
        context_prompt = ProfileService._format_strategy_context(strategy_context)
        
        result = await SkillService.run_skill(
            "profile/generate_headlines.md",
            {
                "count": count,
                "current_headline": personal.get('headline', 'Not set'),
                "current_role": current_role,
                "top_skills": skills,
                "target_role": target_role,
                "lang_name": lang_name,
                "strategy_context_prompt": context_prompt
            }
        )
        # Ensure char counts are accurate
        if isinstance(result.get("variants"), list):
            for v in result["variants"]:
                if isinstance(v, dict) and "text" in v:
                    v["chars"] = len(v["text"])
        return result

    @staticmethod
    async def analyze_ats_match(profile: dict, job_description: str, lang: str = "pt") -> Dict[str, Any]:
        """Compares profile keywords against a job description for ATS scoring."""
        p = ProfileService._get_flattened_profile(profile, lang)
        
        profile_text = " ".join([
            p.get("personal", {}).get("headline", ""),
            p.get("about", ""),
            " ".join(p.get("skills", [])),
            " ".join([
                f"{e.get('role','')} {e.get('description','')}"
                for e in p.get("experience", [])
            ])
        ])
        
        return await SkillService.run_skill(
            "profile/analyze_ats_match.md",
            {
                "profile_text": profile_text[:8000],
                "job_description": job_description[:4000]
            }
        )

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
