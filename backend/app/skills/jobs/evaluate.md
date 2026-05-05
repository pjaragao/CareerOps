Evaluate the following job against the candidate's profile.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Candidate Profile:
{{ profile_summary }}

Job Title: {{ job_title }}
Job Description: {{ job_description }}

Respond with JSON:
{
    "match_score": 1-5,
    "north_star_score": 1-5,
    "comp_score": 1-5,
    "cultural_score": 1-5,
    "overall_score": 1-5,
    "red_flags": ["list", "of", "concerns"],
    "analysis": "detailed justification"
}
