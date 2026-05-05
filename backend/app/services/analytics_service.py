import asyncio
from typing import List, Dict
from app.db.session import get_db_connection
from app.services.profile_service import ProfileService
from app.services.skill_service import SkillService
import json

class AnalyticsService:
    @staticmethod
    async def get_skill_gaps() -> List[Dict]:
        """
        Analyzes all jobs in the database, extracts skills, 
        and compares with user profile to identify gaps.
        """
        profile = ProfileService.get_profile()
        p = ProfileService._get_flattened_profile(profile, "pt")
        user_skills = p.get('skills', [])
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Get all job descriptions
                cur.execute("SELECT description FROM public.job_listings WHERE description IS NOT NULL LIMIT 50")
                descriptions = [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

        if not descriptions:
            return []

        try:
            return await SkillService.run_skill(
                "analytics/skill_gaps.md",
                {
                    "user_skills": user_skills,
                    "descriptions_text": ' '.join(descriptions)[:10000]
                }
            )
        except:
            return []
