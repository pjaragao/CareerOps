"""
Job Evaluator — AI-powered job scoring system based on career-ops patterns.

Evaluates jobs on multiple dimensions:
- Match with CV/skills
- North Star alignment (target roles)
- Compensation
- Cultural signals
- Red flags

Returns score 1-5 with detailed analysis.
"""
import json
import re
from datetime import datetime, timezone

from ai_provider import get_provider, get_provider_info
from config import load_profile
import db

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
        "Product Manager": ["product manager", "product owner", "roadmap", "stakeholder", "prD", "user story", "agile"],
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


def evaluate_job(job_id: int, job: dict = None) -> dict:
    """
    Evaluate a job using AI provider and return scoring results.
    
    Returns dict with:
    - overall_score: 1-5
    - match_score: 1-5 (skills/CV match)
    - north_star_score: 1-5 (role alignment)
    - comp_score: 1-5 (compensation)
    - cultural_score: 1-5 (culture fit)
    - red_flags: list of concerns
    - analysis: detailed justification
    - archetype: detected job type
    """
    if job is None:
        jobs = db.get_jobs_by_ids([job_id])
        if not jobs:
            return {"error": "Job not found"}
        job = jobs[0]

    profile = load_profile()
    provider = get_provider()
    provider_info = get_provider_info()

    archetype = detect_archetype(job)
    
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
        result = provider.generate_json(prompt, temperature=0.3)
        
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

        db.insert_job_evaluation(
            job_id=job_id,
            overall_score=overall,
            match_score=match_s,
            north_star_score=north_s,
            comp_score=comp_s,
            cultural_score=cultural_s,
            red_flags=red_flags,
            analysis=analysis,
            archetype=detected_archetype,
            ai_provider=provider_info["provider"],
            ai_model=provider_info["model"],
        )

        db.update_job_archetype(job_id, detected_archetype, overall)

        return {
            "job_id": job_id,
            "overall_score": overall,
            "match_score": match_s,
            "north_star_score": north_s,
            "comp_score": comp_s,
            "cultural_score": cultural_s,
            "red_flags": red_flags,
            "analysis": analysis,
            "archetype": detected_archetype,
            "provider": provider_info["provider"],
            "model": provider_info["model"],
        }

    except Exception as e:
        return {"error": str(e), "job_id": job_id}


def evaluate_batch(job_ids: list[int] = None) -> list[dict]:
    """Evaluate multiple jobs in batch."""
    if job_ids:
        jobs = db.get_jobs_by_ids(job_ids)
    else:
        jobs = db.get_jobs_by_status("scraped")

    if not jobs:
        return []

    results = []
    for job in jobs:
        result = evaluate_job(job["id"], job)
        results.append(result)

    return results


def generate_interview_stories(job: dict, profile: dict = None) -> list[dict]:
    """
    Generate STAR+R interview stories based on job description and candidate profile.
    These stories can be reused across interviews.
    """
    if profile is None:
        profile = load_profile()

    provider = get_provider()

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
        result = provider.generate_json(prompt, temperature=0.7)
        stories = result if isinstance(result, list) else result.get("stories", [])

        created_ids = []
        for story in stories:
            story_id = db.insert_interview_story(
                title=story.get("title", ""),
                situation=story.get("situation", ""),
                task=story.get("task", ""),
                action=story.get("action", ""),
                result=story.get("result", ""),
                reflection=story.get("reflection", ""),
                tags=story.get("tags", []),
                archetypes=story.get("archetypes", []),
            )
            if story_id:
                created_ids.append(story_id)

        return created_ids

    except Exception as e:
        print(f"Error generating interview stories: {e}")
        return []
