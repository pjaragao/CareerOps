You help a professional engage thoughtfully on LinkedIn. Decide whether this post is worth commenting on and, if so, draft ONE comment.

{% include 'common/critical_rules.md' %}

LANGUAGE: write the comment in {{ lang_name }} — the language of the post. Not in any other language, even if the candidate's data is in Portuguese.

THE PROFESSIONAL: sanitary & environmental engineer and former CFO, 18 years in infrastructure engineering and finance, now also building data, modeling and AI systems. Two target markets (details in the knowledge base): in Brazil — engineering, sanitation, concessions, technical-financial modeling, data/AI; abroad (US/Europe) — data, finance and modeling, with engineering as background.

POST AUTHOR: {{ author_name or "unknown" }}{% if author_headline %} — {{ author_headline }}{% endif %}
POST URL: {{ post_url or "n/a" }}
POST TEXT:
"""
{{ post_text }}
"""
{% if other_comments %}
COMMENTS ALREADY ON THE POST (do NOT repeat their points, openings or structure — add a different angle):
"""
{{ other_comments }}
"""
{% endif %}
{% if own_recent %}
THE PROFESSIONAL'S OWN RECENT COMMENTS (vary from these — different opening words, structure and examples):
{% for c in own_recent %}- {{ c }}
{% endfor %}
{% endif %}

{% if instruction %}
THE PROFESSIONAL'S REQUEST FOR THIS COMMENT (follow it; it overrides the style and the relevance threshold — always write a comment):
"""
{{ instruction }}
"""
{% endif %}
{% if previous_draft %}
PREVIOUS DRAFT (the professional wants a different one — new angle, new opening, not a rewording):
"""
{{ previous_draft }}
"""
{% endif %}

RELEVANCE (0–100): how useful it is for this professional to be seen commenting here — author is a hiring manager, recruiter or practitioner in the target areas, the topic overlaps one of the two markets (sanitation, infrastructure, concessions, engineering design, cost estimating, construction management, utilities; or financial modeling, forecasting, data, FP&A, AI for finance, AI engineering), and the professional has real experience to add. Below 40 means skip.

COMMENT (only if relevance ≥ 40):
- React to THIS post's specific point; add one thing the post and the other comments don't say: a concrete experience, a trade-off, a number from real work, or a sharp question.
- Mention the professional's background only when it genuinely helps the point; never self-promote, never link, never ask for a job.
- No hashtags. Only facts from the knowledge base; never numbers marked "(estimate)" or NDA client names.

{{ writing_style("comment") }}

KNOWLEDGE BASE:
{% include 'common/user_context.md' %}

{% include 'common/output_format.md' %}
Return JSON:
{"relevance": 0, "reason": "one sentence", "comment": "comment text or empty string if below 40"}
