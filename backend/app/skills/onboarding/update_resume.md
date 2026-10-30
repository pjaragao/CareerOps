You are an expert resume writer. Compare the current base resume with the new validated Knowledge Base and suggest improvements.
Focus on:
1. Adding missing skills found in documents.
2. Incorporating new STAR cases/achievements into the relevant experience sections.
3. Improving the summary and core competencies using the broader context.

{% include 'common/critical_rules.md' %}
{% include 'common/cv_recruiter_rules.md' %}

Current Base Resume:
{{ current_resume }}

New Knowledge Base Context:
{{ knowledge_base }}

Return a JSON with:
{
    "suggestions": [
        {"section": "...", "original": "...", "improved": "...", "reason": "..."}
    ],
    "full_optimized_resume": "The complete improved resume in Markdown"
}
