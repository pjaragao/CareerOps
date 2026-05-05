Generate a list of {{ count }} likely interview questions for this role, based on the job description and candidate background.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Job Title: {{ job_title }}
Job Description: {{ job_description }}

Candidate Profile:
{{ profile_summary }}

Return JSON:
{
    "questions": [
        {"text": "question?", "category": "behavioral/technical/situational", "intent": "what recruiter wants to know"}
    ]
}
