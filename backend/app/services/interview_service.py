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
        provider = AIService.get_provider("ai_model_interview")
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
    async def generate_interview_stories(job_id: int) -> List[int]:
        """
        Generate STAR+R interview stories based on job description and candidate profile.
        """
        from app.services.job_service import JobService
        from app.services.profile_service import ProfileService
        from app.services.settings_service import SettingsService

        job = JobService.get_job_by_id(job_id)
        if not job: return []
        
        profile = ProfileService.get_profile()
        settings_ai = SettingsService.get_settings()
        model = settings_ai.get("ai_model_interview")
        provider = AIService.get_provider("ai_model_interview")

        proof_points = profile.get("proof_points", [])
        professional_summary = profile.get("professional_summary", "")

        prompt = f"""Based on the candidate's background and the job description, generate 3-5 interview stories using the STAR+R framework.

STAR+R = Situation, Task, Action, Result, Reflection

# Candidate Background
Summary: {professional_summary}

Proof Points:
{json.dumps(proof_points, indent=2)}

# Job Description
Title: {job.get('job_title', 'Unknown')}
Company: {job.get('company', 'Unknown')}
{job.get('description', '')[:5000]}

Generate stories that would be relevant for behavioral interview questions for this role.
Each story should be specific, measurable, and highlight different competencies.

Respond with valid JSON array:
[
  {{
    "title": "Leading Migration to Microservices",
    "situation": "Company was struggling with monolithic deployment...",
    "task": "I was tasked with leading the migration...",
    "action": "Designed event-driven architecture using...",
    "result": "Reduced deployment time by 80%, zero downtime...",
    "reflection": "Learned the importance of incremental migration...",
    "tags": ["leadership", "architecture", "microservices"],
    "archetypes": ["Backend Engineer", "Solutions Architect"]
  }}
]
"""
        try:
            result = provider.generate_json(prompt, model=model, temperature=0.7)
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
                            story.get("reflection", ""),
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
        provider = AIService.get_provider("ai_model_interview")
        
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
