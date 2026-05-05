Extract structured information from this LinkedIn job description.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Raw Job Description:
{{ raw_text }}

Return JSON:
{
    "title": "Job Title",
    "company": "Company Name",
    "location": "Location",
    "type": "Full-time/Contract/Remote",
    "description": "Cleaned markdown description",
    "requirements": ["req1", "req2"],
    "technologies": ["tech1", "tech2"]
}
