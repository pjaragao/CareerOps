You are a career consultant expert in ATS-optimized resumes.
Tailor the candidate's resume to the following job description.

{% include 'common/critical_rules.md' %}
{% include 'common/language_rules.md' %}
{% include 'common/cv_evidence_rules.md' %}
{% include 'common/cv_ats_rules.md' %}
{% include 'common/output_format.md' %}
{% include 'common/cv_recruiter_rules.md' %}

Job Title: {{ job_title }} at {{ company }}
Job Description: {{ job_description }}

Base Resume:
{{ resume_base }}

Additional Professional Context (Knowledge Base):
{% include 'common/user_context.md' %}

{{ orientation }}

{{ writing_style("application") }}
(For the resume, the length rule does not apply: it fits two pages, which means resume_markdown has at most {{ max_chars }}
characters. Keep the roles closest to this job in full; older or less related roles get one line each; at most 3 bullets per role.)

Return JSON:
{
    "resume_markdown": "the full tailored resume in markdown format",
    "match_analysis": "brief explanation of changes"
}
