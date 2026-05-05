Extract professional information from this LinkedIn profile (Raw Dump) and return it as JSON.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

SPECIFIC EXTRACTION RULES:
1. YOU MUST EXTRACT EVERY SINGLE ROLE AND EDUCATION ENTRY. No summaries.
2. NESTED ROLES: Assign the same primary company name to all nested job titles at the same company.
3. DETECT LANGUAGE: Separate the content strictly into a 'languages' dictionary by detecting the ACTUAL language of the text.

JSON Structure:
{
    "name": "Full name",
    "headline": "Current professional headline",
    "languages": {
        "pt": {
            "about": "Summary...",
            "experience": [{ "company": "...", "role": "...", "period": "...", "description": "..." }],
            "skills": ["Skill1", "Skill2"]
        },
        "en": { ... }
    }
}

Profile Content:
{{ raw_text }}
