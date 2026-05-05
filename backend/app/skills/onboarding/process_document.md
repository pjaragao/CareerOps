Analyze the following document text and extract relevant professional information.
Focus on identifying:
1. Profile data (personal info, summary, education)
2. Skills (technical, soft, tools)
3. Professional experiences
4. STAR Cases: Identify specific achievements and format them as raw STAR (Situation, Task, Action, Result) cases.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Current Profile Information (LinkedIn):
{{ current_profile | tojson }}

# Instructions:
- Analyze the document text below.
- Extract information that is NEW, MORE DETAILED, or provides DIFFERENT PERSPECTIVES compared to the current profile.
- If a work experience or education is already present with the same level of detail, do not duplicate it.
- Focus heavily on extracting "STAR Cases" (Situation, Task, Action, Result) from the experiences.

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
