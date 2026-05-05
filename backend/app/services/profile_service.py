import yaml
import asyncio
import os
import json
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor
from app.services.ai_service import AIService

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
            
            # Use PT as primary but fallback to EN if empty
            current["about"] = extracted.get("pt", {}).get("about") or extracted.get("en", {}).get("about") or current.get("about", "")
            current["experience"] = extracted.get("experience", [])
            current["skills"] = extracted.get("skills", [])
            
            ProfileService.save_profile(current)
        return extracted

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
        provider = AIService.get_provider("ai_model_optimizer")
        lang_name = "Portuguese" if lang == "pt" else "English"
        context_prompt = ProfileService._format_strategy_context(strategy_context)
        
        prompt = f"""
        You are a career consultant expert in LinkedIn and Resume optimization.
        Optimize the following '{section}' section of a professional profile.
        Make it more impactful, results-oriented, and include relevant keywords for Applicant Tracking Systems (ATS).
        Use professional language.{context_prompt}
        
        RESPOND ENTIRELY IN {lang_name.upper()}.
        
        Original Content:
        {content}
        
        Return ONLY the optimized text, without explanations.
        """
        return await asyncio.to_thread(provider.generate_text, prompt)

    @staticmethod
    async def get_profile_score(profile_md: str) -> Dict[str, Any]:
        """Calculates a profile score and saves it to DB."""
        provider = AIService.get_provider("ai_model_optimizer")
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
        result = await asyncio.to_thread(provider.generate_json, prompt)
        
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
        provider = AIService.get_provider("ai_model_optimizer")
        prompt = f"""
        Generate a detailed weekly plan to improve the Social Selling Index (SSI) for this profile.
        Profile: {profile_md}
        Focus on: Establishing professional brand, finding the right people, engaging with insights, and building relationships.
        """
        return await asyncio.to_thread(provider.generate_text, prompt)

    @staticmethod
    async def simulate_ssi(profile: dict) -> Dict[str, Any]:
        """Simulates SSI score across 4 LinkedIn pillars based on profile completeness."""
        provider = AIService.get_provider("ai_model_optimizer")
        profile_summary = json.dumps({
            "name": profile.get("personal", {}).get("name"),
            "headline": profile.get("personal", {}).get("headline"),
            "about": (profile.get("about") or "")[:500],
            "experience_count": len(profile.get("experience", [])),
            "skills_count": len(profile.get("skills", [])),
            "education_count": len(profile.get("education", [])),
            "has_photo": bool(profile.get("personal", {}).get("name")),
            "has_linkedin": bool(profile.get("personal", {}).get("linkedin")),
            "has_github": bool(profile.get("personal", {}).get("github")),
        }, ensure_ascii=False)
        prompt = f"""
        Based on this LinkedIn profile summary, simulate a LinkedIn SSI (Social Selling Index) score.
        The SSI has 4 pillars, each scored 0-25 (total 0-100).

        Profile: {profile_summary}

        Return JSON:
        {{
            "total": 0-100,
            "brand": {{"score": 0-25, "label": "Establish Your Brand", "tip": "specific tip"}},
            "people": {{"score": 0-25, "label": "Find the Right People", "tip": "specific tip"}},
            "insights": {{"score": 0-25, "label": "Engage with Insights", "tip": "specific tip"}},
            "relationships": {{"score": 0-25, "label": "Build Relationships", "tip": "specific tip"}},
            "weekly_plan": ["action1", "action2", "action3", "action4", "action5"]
        }}
        """
        return await asyncio.to_thread(provider.generate_json, prompt)

    @staticmethod
    async def analyze_skills(profile: dict, target_role: str, strategy_context: Optional[dict] = None) -> Dict[str, Any]:
        """Analyzes skills gap vs target role and categorizes them."""
        provider = AIService.get_provider("ai_model_optimizer")
        current_skills = profile.get("skills", [])
        context_prompt = ProfileService._format_strategy_context(strategy_context)
        
        prompt = f"""
        You are a technical recruiter expert in LinkedIn profile optimization.
        Analyze the candidate's current skills vs their target role.{context_prompt}

        Target Role: {target_role}
        Current Skills: {json.dumps(current_skills, ensure_ascii=False)}

        Return JSON with exactly this structure:
        {{
            "keep_and_pin": [{{"skill": "name", "reason": "why important"}}],
            "add": [{{"skill": "name", "reason": "why missing", "priority": "high|medium"}}],
            "remove": [{{"skill": "name", "reason": "why remove"}}],
            "top_3_pin": ["skill1", "skill2", "skill3"],
            "assessments": ["LinkedIn Assessment name 1", "LinkedIn Assessment name 2"],
            "summary": "2-sentence analysis"
        }}
        """
        return await asyncio.to_thread(provider.generate_json, prompt)

    @staticmethod
    async def optimize_experience_bullets(experience_list: list, lang: str = "pt", strategy_context: Optional[dict] = None) -> List[Dict[str, Any]]:
        """Rewrites each experience with impact statements and action verbs."""
        provider = AIService.get_provider("ai_model_optimizer")
        lang_name = "Portuguese" if lang == "pt" else "English"
        context_prompt = ProfileService._format_strategy_context(strategy_context)
        
        results = []
        for exp in experience_list:
            prompt = f"""
            You are a career coach expert in LinkedIn optimization.
            Rewrite the following work experience description using:
            1. Strong action verbs (Led, Built, Reduced, Increased, Delivered, Architected...)
            2. Quantified achievements (%, $, numbers, timeframes)
            3. Keywords relevant to ATS systems
            4. Impact-first format: [Verb] + [Action] + [Result]{context_prompt}
            
            RESPOND ENTIRELY IN {lang_name.upper()}.

            Role: {exp.get('role', '')} at {exp.get('company', '')}
            Period: {exp.get('period', '')}
            Original description: {exp.get('description', '')}

            Return JSON:
            {{
                "company": "{exp.get('company', '')}",
                "role": "{exp.get('role', '')}",
                "period": "{exp.get('period', '')}",
                "original": "{exp.get('description', '')}",
                "optimized": "rewritten description with bullet points",
                "action_verbs_used": ["verb1", "verb2"],
                "has_metrics": true/false,
                "impact_score": 0-10
            }}
            """
            result = await asyncio.to_thread(provider.generate_json, prompt)
            results.append(result)
        return results

    @staticmethod
    async def generate_headline_variants(profile: dict, lang: str = "pt", count: int = 3, strategy_context: Optional[dict] = None) -> Dict[str, Any]:
        """Generates N optimized headline variants with character counts."""
        provider = AIService.get_provider("ai_model_optimizer")
        lang_name = "Portuguese" if lang == "pt" else "English"
        personal = profile.get("personal", {})
        skills = profile.get("skills", [])[:15]
        experience = profile.get("experience", [])
        current_role = experience[0].get("role", "") if experience else ""
        context_prompt = ProfileService._format_strategy_context(strategy_context)
        
        prompt = f"""
        You are a LinkedIn optimization expert.
        Generate {count} different optimized LinkedIn headline variants.
        
        RESPOND ENTIRELY IN {lang_name.upper()}.

        LinkedIn headline rules:
        - Maximum 220 characters
        - Use | to separate sections
        - Formula: [Your Core Professional Identity] | [Key Skills matching the target] | [Value Proposition]
        - Include relevant keywords for recruiter searches
        - Be specific, not generic
        - CRITICAL: DO NOT copy the exact target job title. Your headline must demonstrate SYNERGY with the target role by showing how your unique background and skills make you ideal for it.
        - CRITICAL: DO NOT claim to already work for the target company or explicitly name the target company.{context_prompt}

        Candidate info:
        - Current headline: {personal.get('headline', 'Not set')}
        - Most recent role: {current_role}
        - Top skills: {', '.join(skills)}
        - Target role: {profile.get('preferences', {}).get('target_role', current_role)}

        Return JSON:
        {{
            "variants": [
                {{"text": "headline text", "chars": 0, "focus": "what this variant emphasizes"}}
            ],
            "best_pick": 0,
            "tips": ["tip about headline optimization"]
        }}
        """
        result = await asyncio.to_thread(provider.generate_json, prompt)
        # Ensure char counts are accurate
        if isinstance(result.get("variants"), list):
            for v in result["variants"]:
                if isinstance(v, dict) and "text" in v:
                    v["chars"] = len(v["text"])
        return result

    @staticmethod
    async def analyze_ats_match(profile: dict, job_description: str) -> Dict[str, Any]:
        """Compares profile keywords against a job description for ATS scoring."""
        provider = AIService.get_provider("ai_model_optimizer")
        profile_text = " ".join([
            profile.get("personal", {}).get("headline", ""),
            profile.get("about", ""),
            " ".join(profile.get("skills", [])),
            " ".join([
                f"{e.get('role','')} {e.get('description','')}"
                for e in profile.get("experience", [])
            ])
        ])
        prompt = f"""
        You are an ATS (Applicant Tracking System) expert.
        Analyze how well this LinkedIn/Resume profile matches the job description.

        Profile Text:
        {profile_text[:8000]}

        Job Description:
        {job_description[:4000]}

        Return JSON:
        {{
            "match_score": 0-100,
            "matched_keywords": ["keyword1", "keyword2"],
            "missing_keywords": [{{"keyword": "word", "section": "where to add it", "priority": "high|medium|low"}}],
            "strengths": ["strength 1", "strength 2"],
            "gaps": ["gap 1", "gap 2"],
            "recommendation": "overall advice in 2-3 sentences"
        }}
        """
        return await asyncio.to_thread(provider.generate_json, prompt)

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
        provider = AIService.get_provider("ai_model_import")
        
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
            result = await asyncio.to_thread(provider.generate_json, prompt)
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
