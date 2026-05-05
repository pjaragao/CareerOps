Analyze these job descriptions and the candidate's skills.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Candidate Skills: {{ user_skills | tojson }}

Descriptions Context:
{{ descriptions_text }}

Identify the top 10 technologies or skills that are frequently required in these jobs but are NOT in the candidate's skills.
Return a JSON array of objects:
[
    {"skill": "Docker", "frequency": 15, "priority": "high"},
    {"skill": "Kubernetes", "frequency": 12, "priority": "medium"}
]
