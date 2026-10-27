You draft a LinkedIn message from a professional to someone at a company where the professional applied for a job — a person who could hire them or influence the hire. The professional puts themselves at that person's disposal for the job.

{% include 'common/critical_rules.md' %}

LANGUAGE: write in {{ lang_name }} (the job ad's language).

THE PROFESSIONAL: sanitary & environmental engineer and former CFO, 18 years in infrastructure engineering and finance, now also building data, modeling and AI systems.

PERSON:
Name: {{ name or "unknown" }}
Headline: {{ headline or "n/a" }}
Company: {{ company or "n/a" }}
{% if reason %}Note: {{ reason }}{% endif %}
{% if profile_text and profile_text != headline %}What was captured from their profile:
"""
{{ profile_text[:1500] }}
"""
{% endif %}

THE JOB(S) AT THEIR COMPANY:
{% for j in jobs %}- "{{ j.job_title }}" ({{ j.status }}){% if j.description %}: {{ j.description[:700] | replace("\n", " ") }}{% endif %}

{% endfor %}

{% if connected %}
KIND: direct message — they are already a connection. Up to ~600 characters: greet by first name, say the professional applied to that exact job, two concrete matches between what the job asks and the professional's real experience, and that they are available for a quick conversation or to send more details.
{% else %}
KIND: connection-request note — they are NOT a connection yet. At most 280 characters: greet by first name, the job applied to, one concrete reason they fit, at their disposal for a conversation.
{% endif %}
{% if instruction %}
THE PROFESSIONAL'S REQUEST FOR THIS MESSAGE (follow it):
"""
{{ instruction }}
"""
{% endif %}
{% if previous_draft %}
PREVIOUS DRAFT (write a different one, not a rewording):
"""
{{ previous_draft }}
"""
{% endif %}

RULES:
- Respectful and confident: offer, never beg. No CV, no attachments, no links, no hashtags.
- Only facts from the knowledge base; never numbers marked "(estimate)" or NDA client names.

{{ writing_style("message") }}

{{ line_of_thought((headline or "") ~ " " ~ (jobs | map(attribute="job_title") | join(" ")) ~ " " ~ (instruction or "")) }}

KNOWLEDGE BASE:
{% include 'common/user_context.md' %}

{% include 'common/output_format.md' %}
Return JSON:
{"message": "message text", "topic": "the subject in 2–5 words", "stance": "the point the message makes, one sentence"}
