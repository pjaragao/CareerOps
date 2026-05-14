You are an ATS (Applicant Tracking System) expert.
Analyze how well this LinkedIn/Resume profile matches the job description.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Profile Data:
{{ profile_text }}

{% include 'common/user_context.md' %}

Job Description:
{{ job_description }}

Return JSON:
{
    "match_score": 0-100,
    "matched_keywords": ["keyword1", "keyword2"],
    "missing_keywords": [{"keyword": "word", "section": "where to add it", "priority": "high|medium|low"}],
    "strengths": ["strength 1", "strength 2"],
    "gaps": ["gap 1", "gap 2"],
    "recommendation": "overall advice"
}
