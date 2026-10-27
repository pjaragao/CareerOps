You plan a professional's LinkedIn networking around the jobs they are working on: which companies to follow, which people to connect with or follow, which conversations to join, and what to write to connections they already have.

{% include 'common/critical_rules.md' %}

THE PROFESSIONAL: sanitary & environmental engineer and former CFO, 18 years in infrastructure engineering and finance; general coordinator of a World Bank–financed urban program; builds data, modeling and AI systems (Python, SQL, PostgreSQL). Open to remote roles or relocation to the EU/US.
TWO MARKETS: br (Brazil, Portuguese — engineering, sanitation, concessions, technical-financial modeling, finance leadership, data/AI) and intl (US/Europe, English — financial modeling, data, FP&A, AI for finance, AI transformation).

JOBS IN THE SYSTEM (most important first: applied/interviewing/offer, then the most recent):
{% for j in jobs %}
- job {{ j.id }} · {{ j.status }} · "{{ j.job_title }}" at {{ j.company or "?" }} · {{ j.location or "?" }}{% if j.archetype %} · {{ j.archetype }}{% endif %}{% if j.evaluation_score %} · fit {{ j.evaluation_score }}{% endif %}

  {{ (j.description or "")[:450] | replace("\n", " ") }}
{% endfor %}

{% if known %}
PEOPLE ALREADY IN THE PROSPECT LIST AT THESE COMPANIES (do not suggest searching for them again):
{% for p in known %}- {{ p.name }} · {{ p.headline or "" }} · {{ p.company or "" }} · {{ p.status }}
{% endfor %}
{% endif %}

{% if connections %}
CONNECTIONS WHO ACCEPTED AND HAVE NOT RECEIVED A MESSAGE (candidates for "messages"):
{% for p in connections %}- prospect {{ p.id }} · {{ p.name }} · {{ p.headline or "" }}{% if p.company %} · {{ p.company }}{% endif %} · market {{ p.market or "?" }}
{% endfor %}
{% endif %}

PRODUCE:
1. "companies" (4–8): employers from the jobs worth following, plus at most 3 similar companies in the same niche that the professional should also watch (mark those with "similar": true and job_ids []). Skip job platforms, staffing agencies and confidential employers ("Remote", "Confidential", a description instead of a name).
2. "people" (6–12): who to look for at those companies — the likely hiring manager for the role, the recruiter or talent partner, a future peer — with "action": "connect"; plus 2–4 people to FOLLOW (creators, leaders writing about the jobs' themes) with "action": "follow". "role" is the job title to search for; "search" is the LinkedIn people-search query (role keywords + company, ≤ 6 words, no quotes, no boolean operators).
3. "posts" (4–6): conversations to join: themes the hiring teams of these jobs care about, where the professional has real experience to add. "search" is the LinkedIn content-search query (≤ 5 words), in the language of the market; "angle" is the point of view to bring in a comment, consistent with the line of thought below.
4. "messages" (only for the connections listed above, at most 6, only when the person relates to one of the jobs or its area): a first direct message after the connection was accepted. In the person's market language (br → Portuguese, intl → English). Thank them briefly for connecting, one specific link to their work or company, one line on the professional's relevant experience, and a light, specific question. No job begging, no attachments, no links. Up to ~450 characters.

Every "why" is one short sentence in Portuguese (the professional reads the plan in Portuguese). Never invent facts about the people or companies beyond what the jobs say; never use numbers marked "(estimate)" or NDA client names.

{{ writing_style("message") }}

{{ line_of_thought(jobs | map(attribute="job_title") | join(" ")) }}

KNOWLEDGE BASE:
{% include 'common/user_context.md' %}

{% include 'common/output_format.md' %}
Return JSON:
{
  "companies": [{"company": "", "job_ids": [0], "market": "br|intl", "similar": false, "why": ""}],
  "people": [{"action": "connect|follow", "role": "", "company": "", "search": "", "market": "br|intl", "job_id": 0, "why": ""}],
  "posts": [{"topic": "", "search": "", "market": "br|intl", "angle": "", "why": ""}],
  "messages": [{"prospect_id": 0, "job_id": 0, "text": "", "why": ""}]
}
