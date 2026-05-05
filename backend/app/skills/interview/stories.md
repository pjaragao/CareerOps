Based on the candidate's background and the job description, generate {{ count }} interview stories using the STAR+R framework (Situation, Task, Action, Result + Relevance).

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Target Job: {{ job_title }}
Profile Data: {{ profile_summary }}

Return JSON:
{
    "stories": [
        {
            "title": "Story Title",
            "situation": "...",
            "task": "...",
            "action": "...",
            "result": "...",
            "relevance": "how it applies to the target job"
        }
    ]
}
