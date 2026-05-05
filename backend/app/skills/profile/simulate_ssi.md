Based on this LinkedIn profile summary, simulate a LinkedIn SSI (Social Selling Index) score.
The SSI has 4 pillars, each scored 0-25 (total 0-100).

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Profile Summary:
{{ profile_summary }}

Return JSON:
{
    "total": 0-100,
    "brand": {"score": 0-25, "label": "Establish Your Brand", "tip": "specific tip"},
    "people": {"score": 0-25, "label": "Find the Right People", "tip": "specific tip"},
    "insights": {"score": 0-25, "label": "Engage with Insights", "tip": "specific tip"},
    "relationships": {"score": 0-25, "label": "Build Relationships", "tip": "specific tip"},
    "weekly_plan": ["action1", "action2", "action3", "action4", "action5"]
}
