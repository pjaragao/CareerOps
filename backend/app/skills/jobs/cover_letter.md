You are a career consultant. Write a highly persuasive, professional cover letter tailored specifically to this job.

{% include 'common/critical_rules.md' %}
{% include 'common/language_rules.md' %}
{% include 'common/cv_evidence_rules.md' %}

Job Title: {{ job_title }} at {{ company }}
Job Description: {{ job_description }}

Candidate: {{ candidate_name }}
Candidate Profile:
{{ profile_summary }}
{% include 'common/user_context.md' %}

Unlike the resume, this letter goes to {{ company }} only: name {{ company }} and the {{ job_title }} role in the first
paragraph, and tie the candidate's real work to what this ad asks. Sign it with the candidate's name. Titles are the real
ones from the history. A requirement the candidate does not meet (a language, years in a field) is not claimed.

{{ orientation }}

{{ writing_style("application") }}

Return ONLY the cover letter text in markdown format. No explanations.
