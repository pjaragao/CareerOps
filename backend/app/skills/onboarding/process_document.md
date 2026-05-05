Analyze the following document text and extract relevant professional information.
Focus on identifying:
1. Profile data (personal info, summary, education)
2. Skills (technical, soft, tools)
3. Professional experiences
4. STAR Cases: Identify specific achievements and format them as raw STAR (Situation, Task, Action, Result) cases.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Document Text:
{{ raw_text }}

Return JSON with this structure:
{
    "summary": "Short professional summary",
    "personal": {
        "name": "...",
        "headline": "..."
    },
    "education": [
        {"institution": "...", "degree": "...", "year": "..."}
    ],
    "skills": ["skill1", "skill2"],
    "experiences": [
        {"company": "...", "role": "...", "period": "...", "description": "..."}
    ],
    "star_cases": [
        {
            "title": "Brief title of the achievement",
            "situation": "...",
            "task": "...",
            "action": "...",
            "result": "..."
        }
    ]
}
