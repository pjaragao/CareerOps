Score the following candidate profile from 0 to 100 based on its completeness, impact, and ATS friendliness.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Profile Text:
{{ profile_text }}

{% include 'common/user_context.md' %}

Respond with JSON:
{
    "score": 0-100,
    "reason": "summary of strengths and weaknesses",
    "tips": ["tip1", "tip2"]
}
