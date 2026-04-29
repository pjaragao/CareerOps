import json
import logging
from ai_provider import get_provider
import db

logger = logging.getLogger(__name__)

def analyze_job_gaps(job_id: int):
    """
    Analyzes the gap between the user profile and a specific job listing.
    """
    # 1. Get job details
    job = db.get_job_by_id(job_id)
    if not job or not job.get("description"):
        return {"error": "Job description missing"}
    
    # 2. Get user profile
    profile = db.get_user_profile()
    if not profile:
        return {"error": "User profile missing"}
    
    # 3. Prepare prompt
    provider = get_provider()
    
    prompt = f"""
    Analyze the gap between the User Profile and the Job Description.
    Be critical and objective.
    
    USER PROFILE:
    {json.dumps(profile, indent=2)}
    
    JOB DESCRIPTION:
    {job['description']}
    
    Return a JSON object with the following structure:
    {{
      "match_score": (integer 0-100),
      "gaps": [
        {{
          "skill": "Name of the skill or technology",
          "severity": "high" | "medium" | "low",
          "reason": "Why this is a gap"
        }}
      ],
      "missing_experience": [
        "Description of missing experience type or projects"
      ],
      "training_suggestions": [
        {{
          "topic": "What to learn",
          "priority": "high" | "medium" | "low",
          "action": "Concrete action (e.g. 'Build a project using X', 'Take a course on Y')"
        }}
      ],
      "summary": "Short professional summary of the fit"
    }}
    """
    
    try:
        result = provider.generate_json(prompt)
        
        # 4. Save analysis to database
        db.save_skill_gaps(job_id, result)
        
        return result
    except Exception as e:
        logger.error(f"Error analyzing skill gaps for job {job_id}: {e}")
        return {"error": str(e)}
