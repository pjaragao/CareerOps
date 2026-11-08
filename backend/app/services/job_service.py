from datetime import datetime, timezone
from typing import List, Optional, Set
import re
import json
from app.db.session import get_db_connection, get_db_cursor
import uuid
from app.services.skill_service import SkillService

class JobService:
    @staticmethod
    def get_jobs(status: Optional[str] = None, limit: int = 200) -> List[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                query = """
                    SELECT j.*, c.name as company_name, c.logo_url, c.company_type, c.career_site_url
                    FROM public.job_listings j
                    LEFT JOIN public.companies c ON j.company_id = c.id
                """
                params = []
                if status and status != 'all':
                    query += " WHERE j.status = %s"
                    params.append(status)
                else:
                    # 'discovered': found by a search, waits in Automação until you approve it
                    query += " WHERE j.status NOT IN ('removed', 'archived', 'discovered')"
                
                query += " ORDER BY j.created_at DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_jobs_by_company(company_id: int) -> List[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                query = """
                    SELECT * FROM public.job_listings
                    WHERE company_id = %s
                    ORDER BY created_at DESC
                """
                cur.execute(query, (company_id,))
                return [dict(row) for row in cur.fetchall()]
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
        if not linkedin_job_id and url:
            # the same link added again updates that job instead of creating a copy
            conn_check = get_db_connection()
            try:
                with conn_check.cursor() as cur:
                    cur.execute("SELECT linkedin_job_id FROM public.job_listings WHERE url = %s ORDER BY id LIMIT 1", (url,))
                    row = cur.fetchone()
                    linkedin_job_id = row[0] if row else None
            finally:
                conn_check.close()
        if not linkedin_job_id:
            if 'linkedin.com/jobs/view/' in url:
                match = re.search(r'/view/(\d+)', url)
                linkedin_job_id = match.group(1) if match else f"manual_{uuid.uuid4().hex[:8]}"
            else:
                linkedin_job_id = f"manual_{uuid.uuid4().hex[:8]}"
        
        # Link to company
        from app.services.company_service import CompanyService
        company_id = CompanyService.get_or_create_company(company, url)
        
        try:
            with conn.cursor() as cur:
                # We use COALESCE to keep existing data if the new data is empty
                # and ON CONFLICT (linkedin_job_id) to prevent duplicates
                cur.execute("""
                    INSERT INTO public.job_listings
                        (linkedin_job_id, url, job_title, company, location, description, status, scraped_at, company_id)
                    VALUES (%s, %s, %s, %s, %s, %s, 'scraped', %s, %s)
                    ON CONFLICT (linkedin_job_id) DO UPDATE SET
                        url = EXCLUDED.url,
                        job_title = EXCLUDED.job_title,
                        company = EXCLUDED.company,
                        location = EXCLUDED.location,
                        description = EXCLUDED.description,
                        -- re-importing never moves a job back from an application stage
                        status = CASE WHEN job_listings.status IN ('applied', 'interviewing', 'offer', 'rejected', 'done')
                                      THEN job_listings.status ELSE 'scraped' END,
                        scraped_at = EXCLUDED.scraped_at,
                        company_id = EXCLUDED.company_id,
                        -- a new description is read again (eligibility check, then CV and cover letter if missing)
                        eligibility_checked_at = CASE WHEN job_listings.description IS DISTINCT FROM EXCLUDED.description
                                                      THEN NULL ELSE job_listings.eligibility_checked_at END,
                        auto_docs_at = CASE WHEN job_listings.description IS DISTINCT FROM EXCLUDED.description
                                            THEN NULL ELSE job_listings.auto_docs_at END
                    WHERE public.job_listings.status != 'applied'
                """, (linkedin_job_id, url, job_title, company, location, description, datetime.now(timezone.utc), company_id))
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
    def update_job_status(job_id: int, new_status: str) -> bool:
        VALID = {'discovered', 'scraped', 'new', 'applied', 'interviewing', 'offer', 'rejected', 'archived', 'done', 'error'}
        if new_status not in VALID:
            return False
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.job_listings SET status = %s, updated_at = %s WHERE id = %s",
                    (new_status, datetime.now(timezone.utc), job_id)
                )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating job status: {e}")
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
            if content_type == 'resume' and content:
                # every CV carries this job's own portfolio link (contact line only; content unchanged)
                from app.services.portfolio_service import PortfolioService
                content = PortfolioService.attach(job_id, content)
            
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
        from app.services.profile_service import ProfileService
        
        job = JobService.get_job_by_id(job_id)
        if not job: return
        
        profile = ProfileService.get_profile()
        p = ProfileService._get_flattened_profile(profile, "pt")
        profile_summary = f"Summary: {p.get('about','')}\nExperience: {json.dumps(p.get('experience',[]))}\nSkills: {', '.join(p.get('skills',[]))}"

        archetype = JobService.detect_archetype(job['job_title'], job['description'])
        
        try:
            result = await SkillService.run_skill(
                "jobs/evaluate.md",
                {
                    "profile_summary": profile_summary,
                    "job_title": job['job_title'],
                    "job_description": job['description'][:5000]
                }
            )
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
        try:
            result = await SkillService.run_skill(
                "jobs/extract.md",
                {"raw_text": raw_text[:15000]}
            )
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
