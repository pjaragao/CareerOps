from datetime import datetime, timezone
from typing import List, Optional, Set
import re
from app.db.session import get_db_connection, get_db_cursor
import uuid

class JobService:
    @staticmethod
    def get_jobs(status: Optional[str] = None, limit: int = 200) -> List[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                query = "SELECT * FROM public.job_listings"
                params = []
                if status and status != 'all':
                    query += " WHERE status = %s"
                    params.append(status)
                else:
                    query += " WHERE status != 'removed'"
                
                query += " ORDER BY created_at DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_job_by_id(job_id: int) -> Optional[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.job_listings WHERE id = %s", (job_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def insert_manual_job(job_title: str, company: str, location: str, url: str, description: str, linkedin_job_id: Optional[str] = None) -> bool:
        conn = get_db_connection()
        # If no LinkedIn ID, generate a synthetic one from URL or UUID
        if not linkedin_job_id:
            if 'linkedin.com/jobs/view/' in url:
                match = re.search(r'/view/(\d+)', url)
                linkedin_job_id = match.group(1) if match else f"manual_{uuid.uuid4().hex[:8]}"
            else:
                linkedin_job_id = f"manual_{uuid.uuid4().hex[:8]}"
        
        try:
            with conn.cursor() as cur:
                # We use COALESCE to keep existing data if the new data is empty
                # and ON CONFLICT (linkedin_job_id) to prevent duplicates
                cur.execute("""
                    INSERT INTO public.job_listings
                        (linkedin_job_id, url, job_title, company, location, description, status, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'scraped', %s)
                    ON CONFLICT (linkedin_job_id) DO UPDATE SET
                        url = EXCLUDED.url,
                        job_title = EXCLUDED.job_title,
                        company = EXCLUDED.company,
                        location = EXCLUDED.location,
                        description = EXCLUDED.description,
                        status = 'scraped',
                        scraped_at = EXCLUDED.scraped_at
                    WHERE public.job_listings.status != 'applied'
                """, (linkedin_job_id, url, job_title, company, location, description, datetime.now(timezone.utc)))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting manual job: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def mark_job_applied(linkedin_job_id: str) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE public.job_listings 
                    SET status = 'applied', updated_at = %s 
                    WHERE linkedin_job_id = %s OR url LIKE %s
                """, (datetime.now(timezone.utc), linkedin_job_id, f'%{linkedin_job_id}%'))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error marking job as applied: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def delete_job(job_id: int) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.job_listings WHERE id = %s", (job_id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
    @staticmethod
    def update_job_ai_content(job_id: int, content_type: str, content: str) -> bool:
        conn = get_db_connection()
        try:
            column_map = {
                'resume': 'resume_markdown',
                'cover': 'cover_letter',
                'dm': 'linkedin_dm_draft'
            }
            column = column_map.get(content_type)
            if not column: return False
            
            with conn.cursor() as cur:
                cur.execute(f"UPDATE public.job_listings SET {column} = %s, updated_at = %s WHERE id = %s", 
                           (content, datetime.now(timezone.utc), job_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating AI content: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def detect_archetype(title: str, description: str) -> str:
        """Detect job archetype from title and description."""
        combined = f"{title} {description}".lower()
        archetype_signals = {
            "Backend Engineer": ["backend", "api", "server", "microservice", "database", "sql", "python", "java", "go", "node"],
            "Full Stack Developer": ["full stack", "fullstack", "frontend and backend", "react", "django", "flask"],
            "Frontend Engineer": ["frontend", "front-end", "react", "vue", "angular", "css", "html", "ui", "ux"],
            "DevOps/SRE": ["devops", "sre", "site reliability", "kubernetes", "docker", "ci/cd", "terraform", "aws", "gcp", "azure"],
            "AI/ML Engineer": ["machine learning", "deep learning", "llm", "ai", "nlp", "pytorch", "tensorflow"],
            "Data Engineer": ["data pipeline", "etl", "data warehouse", "spark", "airflow", "kafka"],
            "Product Manager": ["product manager", "product owner", "roadmap", "stakeholder", "prd"],
            "Engineering Manager": ["engineering manager", "tech lead", "team lead"],
        }
        scores = {arch: sum(1 for sig in sigs if sig in combined) for arch, sigs in archetype_signals.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "Other"

    @staticmethod
    async def evaluate_job(job_id: int):
        """AI-powered job scoring."""
        from app.services.ai_service import AIService
        from app.services.profile_service import ProfileService
        
        job = JobService.get_job_by_id(job_id)
        if not job: return
        
        profile = ProfileService.get_profile()
        provider = AIService.get_provider("ai_model_resume")
        
        archetype = JobService.detect_archetype(job['job_title'], job['description'])
        
        prompt = f"""
        Evaluate the following job against the candidate's profile.
        Candidate Profile: {json.dumps(profile)}
        Job Title: {job['job_title']}
        Job Description: {job['description'][:5000]}
        
        Respond with valid JSON:
        {{
            "match_score": 1-5,
            "north_star_score": 1-5,
            "comp_score": 1-5,
            "cultural_score": 1-5,
            "overall_score": 1-5,
            "red_flags": ["list", "of", "concerns"],
            "analysis": "detailed justification"
        }}
        """
        try:
            result = provider.generate_json(prompt)
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.job_evaluations 
                        (job_id, overall_score, match_score, north_star_score, comp_score, cultural_score, red_flags, analysis, archetype)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (job_id) DO UPDATE SET
                        overall_score = EXCLUDED.overall_score,
                        analysis = EXCLUDED.analysis,
                        archetype = EXCLUDED.archetype
                """, (
                    job_id, result['overall_score'], result['match_score'], 
                    result['north_star_score'], result['comp_score'], result['cultural_score'],
                    ", ".join(result.get('red_flags', [])), result['analysis'], archetype
                ))
            conn.commit()
            conn.close()
            return result
        except Exception as e:
            print(f"Evaluation error: {e}")
            return None
    @staticmethod
    async def import_job_universal_ai(raw_text: str, url: str) -> bool:
        """Use AI to extract job details from a raw text dump from any website."""
        from app.services.ai_service import AIService
        provider = AIService.get_provider("ai_model_import")
        
        prompt = f"""
        Extract job details from the following raw text dump from a job posting website ({url}).
        
        RAW TEXT:
        {raw_text[:15000]}
        
        Respond with valid JSON:
        {{
            "title": "Job Title",
            "company": "Company Name",
            "location": "Location (if found)",
            "description": "Full cleaned job description with requirements and benefits"
        }}
        """
        try:
            result = provider.generate_json(prompt)
            if not result.get('title') or not result.get('description'):
                return False
                
            return JobService.insert_manual_job(
                result['title'],
                result['company'] or "Unknown",
                result.get('location', ""),
                url,
                result['description']
            )
        except Exception as e:
            print(f"Universal import error: {e}")
            return False
