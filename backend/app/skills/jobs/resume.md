You are a career consultant expert in ATS-optimized resumes.
Tailor the candidate's resume to the following job description.

{% include 'common/critical_rules.md' %}
{% include 'common/language_rules.md' %}
{% include 'common/output_format.md' %}

Job Title: {{ job_title }} at {{ company }}
Job Description: {{ job_description }}

Base Resume:
{{ resume_base }}

Additional Professional Context (Knowledge Base):
{% include 'common/user_context.md' %}

{{ orientation }}

{{ writing_style("application") }}
(For the resume, the length rule does not apply: keep it to two pages.)

Return JSON:
{
    "resume_markdown": "the full tailored resume in markdown format",
    "match_analysis": "brief explanation of changes"
}
