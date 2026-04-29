import json
from typing import List, Dict, Optional
from app.services.ai_service import AIService
from app.services.job_service import JobService
from app.services.profile_service import ProfileService
from app.services.settings_service import SettingsService
from app.db.session import get_db_connection, get_db_cursor

ARCHETYPES = [
    "Backend Engineer",
    "Full Stack Developer",
    "Frontend Engineer",
    "DevOps/SRE",
    "AI/ML Engineer",
    "Data Engineer",
    "Data Scientist",
    "Product Manager",
    "Solutions Architect",
    "Security Engineer",
    "Mobile Developer",
    "QA/Test Engineer",
    "Engineering Manager",
    "Other",
]

class JobEvaluationService:
    @staticmethod
    def detect_archetype(job: dict) -> str:
        """Detect job archetype from title and description."""
        title = (job.get("job_title", "") or "").lower()
        description = (job.get("description", "") or "").lower()
        combined = f"{title} {description}"

        archetype_signals = {
            "Backend Engineer": ["backend", "api", "server", "microservice", "database", "sql", "python", "java", "go", "node"],
            "Full Stack Developer": ["full stack", "fullstack", "frontend and backend", "end-to-end", "react", "django", "flask"],
            "Frontend Engineer": ["frontend", "front-end", "react", "vue", "angular", "css", "html", "ui", "ux"],
            "DevOps/SRE": ["devops", "sre", "site reliability", "kubernetes", "docker", "ci/cd", "terraform", "aws", "gcp", "azure", "infrastructure"],
            "AI/ML Engineer": ["machine learning", "deep learning", "llm", "ai", "nlp", "computer vision", "pytorch", "tensorflow", "transformer", "rag"],
            "Data Engineer": ["data pipeline", "etl", "data warehouse", "spark", "airflow", "kafka", "data lake", "big data"],
            "Data Scientist": ["data science", "statistical", "analytics", "a/b test", "experiment", "hypothesis"],
            "Product Manager": ["product manager", "product owner", "roadmap", "stakeholder", "prd", "user story", "agile"],
            "Solutions Architect": ["solutions architect", "system design", "architecture", "enterprise", "integration", "consulting"],
            "Security Engineer": ["security", "penetration", "vulnerability", "compliance", "soc", "siem", "zero trust"],
            "Mobile Developer": ["mobile", "ios", "android", "swift", "kotlin", "react native", "flutter"],
            "QA/Test Engineer": ["qa", "quality assurance", "test automation", "selenium", "cypress", "testing"],
            "Engineering Manager": ["engineering manager", "tech lead", "team lead", "manage engineers", "people manager"],
        }

        scores = {}
        for archetype, signals in archetype_signals.items():
            score = sum(1 for signal in signals if signal in combined)
            scores[archetype] = score

        best_match = max(scores, key=scores.get)
        if scores[best_match] == 0:
            return "Other"
        return best_match

    @staticmethod
    async def evaluate_job(job_id: int, job: dict = None) -> dict:
        """
        Evaluate a job using AI provider and return scoring results.
        """
        if job is None:
            job = JobService.get_job_by_id(job_id)
            if not job:
                return {"error": "Job not found"}

        profile = ProfileService.get_profile()
        settings_ai = SettingsService.get_settings()
        model = settings_ai.get("ai_model_evaluator")
        provider = AIService.get_provider("ai_model_evaluator")

        archetype = JobEvaluationService.detect_archetype(job)
        
        target_roles = profile.get("target_roles", [])
        skills = profile.get("skills", {})
        deal_breakers = profile.get("deal_breakers", [])
        salary = profile.get("salary", {})
        work_prefs = profile.get("work_preferences", {})

        profile_context = f"""
# Candidate Profile

## Target Roles
{', '.join(target_roles) if target_roles else 'Not specified'}

## Skills
Technical: {', '.join(skills.get('technical', []))}
Soft: {', '.join(skills.get('soft', []))}

## Deal Breakers
{chr(10).join('- ' + d for d in deal_breakers) if deal_breakers else 'None specified'}

## Salary Expectations
Currency: {salary.get('currency', 'USD')}
Target: {salary.get('target_annual', 'Not specified')}
Min: {salary.get('min_annual', 'Not specified')}

## Work Preferences
Remote only: {work_prefs.get('remote_only', False)}
Languages: {', '.join(work_prefs.get('languages', []))}
"""

        job_context = f"""
# Job Details

Title: {job.get('job_title', 'Unknown')}
Company: {job.get('company', 'Unknown')}
Location: {job.get('location', 'Unknown')}
Easy Apply: {job.get('easy_apply', False)}

Description:
{job.get('description', '')[:10000]}

Company Description:
{job.get('company_description', 'Not available')[:3000]}
"""

        prompt = f"""You are an expert job evaluator. Evaluate the following job against the candidate's profile.

{profile_context}

{job_context}

Evaluate the job on these dimensions (score 1-5 for each):

1. **Match Score**: How well do the candidate's skills and experience match the job requirements?
   - 5 = Perfect match, all skills align
   - 4 = Strong match, minor gaps
   - 3 = Decent match, some gaps
   - 2 = Weak match, significant gaps
   - 1 = Poor match, very different

2. **North Star Score**: How well does this role align with the candidate's target roles and career goals?
   - 5 = Exactly what they're looking for
   - 4 = Very aligned
   - 3 = Somewhat aligned
   - 2 = Slightly aligned
   - 1 = Not aligned at all

3. **Comp Score**: Based on available compensation information (or market estimates):
   - 5 = Top quartile, well above target
   - 4 = Above market rate
   - 3 = Market rate
   - 2 = Below market
   - 1 = Well below market or no info + likely low

4. **Cultural Score**: Company culture, remote policy, growth potential:
   - 5 = Excellent culture, great fit
   - 4 = Good culture
   - 3 = Average
   - 2 = Some concerns
   - 1 = Major red flags

5. **Red Flags**: List any concerns or blockers.

Also identify the job archetype from: {', '.join(ARCHETYPES)}

Respond with valid JSON only:
{{
  "match_score": 4.0,
  "north_star_score": 3.5,
  "comp_score": 3.0,
  "cultural_score": 4.0,
  "overall_score": 3.6,
  "archetype": "Backend Engineer",
  "red_flags": ["No salary listed", "On-site only"],
  "analysis": "Detailed justification of scores..."
}}
"""

        try:
            result = provider.generate_json(prompt, model=model, temperature=0.3)
            
            overall = float(result.get("overall_score", 0))
            match_s = float(result.get("match_score", 0))
            north_s = float(result.get("north_star_score", 0))
            comp_s = float(result.get("comp_score", 0))
            cultural_s = float(result.get("cultural_score", 0))
            red_flags = result.get("red_flags", [])
            analysis = result.get("analysis", "")
            detected_archetype = result.get("archetype", archetype)

            if isinstance(red_flags, list):
                red_flags = ", ".join(red_flags)

            conn = get_db_connection()
            try:
                with get_db_cursor(conn) as cur:
                    # Insert evaluation
                    cur.execute("""
                        INSERT INTO public.job_evaluations 
                        (job_id, overall_score, match_score, north_star_score, comp_score, cultural_score, red_flags, analysis, archetype, ai_provider, ai_model)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (job_id) DO UPDATE SET
                        overall_score = EXCLUDED.overall_score,
                        match_score = EXCLUDED.match_score,
                        north_star_score = EXCLUDED.north_star_score,
                        comp_score = EXCLUDED.comp_score,
                        cultural_score = EXCLUDED.cultural_score,
                        red_flags = EXCLUDED.red_flags,
                        analysis = EXCLUDED.analysis,
                        archetype = EXCLUDED.archetype,
                        ai_provider = EXCLUDED.ai_provider,
                        ai_model = EXCLUDED.ai_model,
                        evaluated_at = CURRENT_TIMESTAMP
                    """, (job_id, overall, match_s, north_s, comp_s, cultural_s, red_flags, analysis, detected_archetype, AIService.list_models().get(model, "unknown"), model))
                    
                    # Update job archetype and score
                    cur.execute("UPDATE public.job_listings SET archetype = %s, score = %s WHERE id = %s", (detected_archetype, overall, job_id))
                conn.commit()
            finally:
                conn.close()

            return {
                "job_id": job_id,
                "overall_score": overall,
                "match_score": match_s,
                "north_star_score": north_s,
                "comp_score": comp_s,
                "cultural_score": cultural_s,
                "red_flags": red_flags,
                "analysis": analysis,
                "archetype": detected_archetype
            }

        except Exception as e:
            return {"error": str(e), "job_id": job_id}

    @staticmethod
    async def evaluate_batch(job_ids: List[int] = None) -> List[dict]:
        """Evaluate multiple jobs in batch."""
        if not job_ids:
            conn = get_db_connection()
            try:
                with get_db_cursor(conn) as cur:
                    cur.execute("SELECT id FROM public.job_listings WHERE status = 'scraped' LIMIT 20")
                    job_ids = [row[0] for row in cur.fetchall()]
            finally:
                conn.close()

        if not job_ids:
            return []

        results = []
        for jid in job_ids:
            result = await JobEvaluationService.evaluate_job(jid)
            results.append(result)

        return results
