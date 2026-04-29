from typing import List, Dict
from app.db.session import get_db_connection
from app.services.profile_service import ProfileService
from app.services.ai_service import AIService
import json

class AnalyticsService:
    @staticmethod
    def get_skill_gaps() -> List[Dict]:
        """
        Analyzes all jobs in the database, extracts skills, 
        and compares with user profile to identify gaps.
        """
        profile = ProfileService.get_profile()
        user_skills = set([s.lower() for s in (profile.get('keywords', []) or [])])
        
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

        # Use AI to extract common skills from descriptions and find gaps
        provider = AIService.get_provider()
        prompt = f"""
        Analyze these job descriptions and the candidate's skills.
        Candidate Skills: {list(user_skills)}
        
        Descriptions (subset):
        {' '.join(descriptions)[:10000]}
        
        Identify the top 10 technologies or skills that are frequently required in these jobs but are NOT in the candidate's skills.
        Return a JSON array of objects:
        [
            {{"skill": "Docker", "frequency": 15, "priority": "high"}},
            {{"skill": "Kubernetes", "frequency": 12, "priority": "medium"}}
        ]
        """
        try:
            result = provider.generate_json(prompt)
            return result
        except:
            return []
