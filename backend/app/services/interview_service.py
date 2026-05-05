from typing import List, Optional, Dict, Any
import json
from app.db.session import get_db_connection, get_db_cursor
from app.services.skill_service import SkillService

class InterviewService:
    @staticmethod
    def get_stories() -> List[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.interview_stories ORDER BY updated_at DESC")
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def save_story(title: str, situation: str, task: str, action: str, result: str, tags: List[str] = None) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.interview_stories (title, situation, task, action, result, tags, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (title, situation, task, action, result, tags or []))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    async def generate_star_case(experience_description: str) -> Dict[str, str]:
        """Uses AI to generate a STAR case from a raw experience description."""
        return await SkillService.run_skill(
            "interview/stories.md",
            {
                "count": 1,
                "profile_summary": experience_description,
                "job_title": "N/A"
            }
        )

    @staticmethod
    async def generate_interview_stories(job_id: int) -> List[int]:
        """
        Generate STAR+R interview stories based on job description and candidate profile.
        """
        from app.services.job_service import JobService
        from app.services.profile_service import ProfileService

        job = JobService.get_job_by_id(job_id)
        if not job: return []
        
        profile = ProfileService.get_profile()
        
        # Flatten profile for simplicity in prompt
        p = ProfileService._get_flattened_profile(profile, "pt") # Default to pt or check job lang
        profile_summary = f"Summary: {p.get('about','')}\nSkills: {', '.join(p.get('skills',[]))}"

        try:
            result = await SkillService.run_skill(
                "interview/stories.md",
                {
                    "count": 5,
                    "job_title": job.get('job_title', 'Unknown'),
                    "job_description": job.get('description', ''),
                    "profile_summary": profile_summary
                }
            )
            stories = result if isinstance(result, list) else result.get("stories", [])

            created_ids = []
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    for story in stories:
                        cur.execute("""
                            INSERT INTO public.interview_stories (title, situation, task, action, result, reflection, tags, archetypes, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                            RETURNING id
                        """, (
                            story.get("title", ""),
                            story.get("situation", ""),
                            story.get("task", ""),
                            story.get("action", ""),
                            story.get("result", ""),
                            story.get("reflection", "") or story.get("relevance", ""),
                            story.get("tags", []),
                            story.get("archetypes", [])
                        ))
                        row = cur.fetchone()
                        if row:
                            created_ids.append(row[0])
                conn.commit()
            finally:
                conn.close()

            return created_ids

        except Exception as e:
            print(f"Error generating interview stories: {e}")
            return []

    @staticmethod
    def delete_story(story_id: int) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.interview_stories WHERE id = %s", (story_id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    async def simulate_interaction(job_id: int, answer: str, history: List[dict]) -> Dict[str, Any]:
        """Interactive interview simulation."""
        from app.services.job_service import JobService
        from app.services.profile_service import ProfileService
        
        job = JobService.get_job_by_id(job_id)
        profile = ProfileService.get_profile()
        p = ProfileService._get_flattened_profile(profile, "pt")
        profile_summary = f"Summary: {p.get('about','')}\nSkills: {', '.join(p.get('skills',[]))}"
        
        return await SkillService.run_skill(
            "interview/simulate.md",
            {
                "job_title": job['job_title'],
                "company": job['company'],
                "profile_summary": profile_summary,
                "history": history,
                "answer": answer
            }
        )
