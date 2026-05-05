Generate high-level career insights and growth opportunities for this candidate based on their profile and the current market trends.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Profile Summary:
{{ profile_summary }}

Return JSON:
{
    "market_positioning": "how the user is perceived currently",
    "growth_opportunities": ["opportunity1", "opportunity2"],
    "suggested_certifications": ["cert1", "cert2"],
    "next_steps": ["step1", "step2"]
}
