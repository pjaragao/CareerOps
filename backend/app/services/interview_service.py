from typing import List, Optional, Dict, Any
from app.db.session import get_db_connection, get_db_cursor
from app.services.ai_service import AIService
import json

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
        provider = AIService.get_provider()
        prompt = f"""
        Transform the following professional experience into a structured STAR method story.
        S - Situation: Set the scene and give the necessary details of your example.
        T - Task: Describe what your responsibility was in that situation.
        A - Action: Explain exactly what steps you took to address it.
        R - Result: Share what outcomes your actions achieved.

        Experience: {experience_description}

        Respond ONLY with a JSON object:
        {{
            "title": "Short catchy title",
            "situation": "...",
            "task": "...",
            "action": "...",
            "result": "..."
        }}
        """
        result = provider.generate_json(prompt)
        return result

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
        provider = AIService.get_provider()
        
        prompt = f"""
        You are an interviewer for the position of {job['job_title']} at {job['company']}.
        Candidate Profile: {json.dumps(profile)}
        Interview History: {json.dumps(history)}
        Latest Answer from Candidate: "{answer}"
        
        Instruction:
        - If history is empty, introduce yourself and ask the first question.
        - If user answered, provide brief professional feedback and ask the NEXT question.
        - If the simulation should end, set "is_over": true.
        
        Respond ONLY with JSON:
        {{
            "feedback": "...",
            "next_question": "...",
            "is_over": false
        }}
        """
        return provider.generate_json(prompt)
