Generate a professional outreach message for the position of {{ job_title }} at {{ company }}.

{% include 'common/critical_rules.md' %}
{% include 'common/language_rules.md' %}

Type: {{ type | upper }} (LinkedIn DM or Email)
Tone: {{ tone_instruction }}
Orientation: {{ orientation }}

Job Description: {{ job_description }}

Return ONLY the message text.
