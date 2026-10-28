Extract structured information from this job ad (text of a job page or a pasted ad; ignore menus, cookie banners,
other jobs listed and footer text).

Use only what the text says; an empty string for anything it does not state. Never invent.
{% include 'common/output_format.md' %}

Raw Job Description:
{{ raw_text }}

Return JSON:
{
    "title": "Job Title",
    "company": "Company Name",
    "location": "Location",
    "type": "Full-time/Contract/Remote",
    "description": "The full job description as plain text: every section (about the role, responsibilities, requirements, benefits, how to apply), paragraphs on their own lines, list items starting with \"• \". Do not summarize or rewrite.",
    "requirements": ["req1", "req2"],
    "technologies": ["tech1", "tech2"]
}
