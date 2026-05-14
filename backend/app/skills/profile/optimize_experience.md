{% include 'common/critical_rules.md' %}
{% include 'common/language_rules.md' %}
{% include 'common/output_format.md' %}

Rewrite the work experience description following these STRICT rules:
1.  **Format**: Use a bulleted list. Each achievement MUST start with a dash `-`.
2.  **Verbs**: Use strong action verbs (Led, Built, Reduced, Increased, Delivered, Architected...).
3.  **Metrics**: Quantify achievements (%, $, numbers, timeframes).
4.  **Structure**: Impact-first format: [Verb] + [Action] + [Result].
5.  **Negative Constraint**: DO NOT return a single block of text or a paragraph. Each bullet must be on a new line.

{{ strategy_context_prompt }}

Role: {{ role }} at {{ company }}
Period: {{ period }}

Original description:
{{ description }}

Additional Professional Context (Knowledge Base):
{% include 'common/user_context.md' %}

# Rules for Context Usage:
- Scan the Knowledge Base for achievements and STAR cases that CLEARLY belong to the role "{{ role }}" at "{{ company }}".
- Use metrics and specific technical details from those cases to enrich the original description.
- DO NOT use achievements from other companies or significantly different roles unless they are foundational skills.
- If the Knowledge Base contains data for a different role at the same company, be extremely careful to only use what is relevant to the current role being optimized.

Return JSON:
{
    "company": "{{ company }}",
    "role": "{{ role }}",
    "period": "{{ period }}",
    "original": "{{ description }}",
    "optimized": "rewritten description with bullet points",
    "action_verbs_used": ["verb1", "verb2"],
    "has_metrics": true/false,
    "impact_score": 0-10
}
