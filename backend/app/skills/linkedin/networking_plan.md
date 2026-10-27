You plan a professional's LinkedIn networking around the jobs they applied to: who at each hiring company could hire them and what to write to those people, which companies to follow, who to follow for the jobs' themes, and what to say when engaging with the hiring companies' posts.

{% include 'common/critical_rules.md' %}

THE PROFESSIONAL: sanitary & environmental engineer and former CFO, 18 years in infrastructure engineering and finance; general coordinator of a World Bank–financed urban program; builds data, modeling and AI systems (Python, SQL, PostgreSQL). Open to remote roles or relocation to the EU/US.

JOBS (most important first; "applied", "interviewing" and "offer" are the ones the professional is pursuing):
{% for j in jobs %}
- job {{ j.id }} · {{ j.status }} · "{{ j.job_title }}" at {{ j.company or "?" }} · {{ j.location or "?" }} · ad language: {{ j.lang_name }}{% if j.archetype %} · {{ j.archetype }}{% endif %}

{% if j.hiring_team %}  HIRING TEAM SHOWN ON THE JOB PAGE (real people — write to them by name):
{% for h in j.hiring_team %}    · {{ h.name }}{% if h.title %} — {{ h.title }}{% endif %}

{% endfor %}{% endif %}
  {{ (j.description or "")[:450] | replace("\n", " ") }}
{% endfor %}

{% if known %}
PEOPLE ALREADY IN THE PROSPECT LIST AT THESE COMPANIES (write to them by name too when they could hire for the job):
{% for p in known %}- {{ p.name }} · {{ p.headline or "" }} · {{ p.company or "" }} · {{ p.status }}
{% endfor %}
{% endif %}

PRODUCE:
1. "contacts": for EVERY job the professional is pursuing (applied/interviewing/offer), the 1–3 people most likely to decide or influence the hire:
   - every hiring-team member listed for the job, by exact name ("name" as written above, "role" their title);
   - otherwise the likely hiring manager for the role (the leader the job reports to — e.g. "CFO", "Head of AI", "VP Finance") and the recruiter / talent partner, with "name" empty and "search" = LinkedIn people-search query (role keywords + company, ≤ 6 words, no quotes or operators).
   For each contact write, in the job ad's language:
   - "note": the connection-request note, ≤ 280 characters: says the professional applied to that exact job, one concrete reason they fit, and that they are at the person's disposal for a conversation. Greeting with the first name when known, otherwise start with "Olá," / "Hi,".
   - "message": the direct message after the connection is accepted, up to ~600 characters: thanks for connecting, the job applied to, two concrete matches between the job's requirements and the professional's real experience, available for a quick call or to send more details. Respectful and confident — no begging, no attachments, no links, no hashtags.
   Use "{nome}"/"{name}" only if the person is unknown and you must address them; better to greet without a name.
   Write each contact's texts for THAT person — never the same note or message for two contacts:
   - hiring manager / leader: the problem in their area the professional would solve, with one real result as proof;
   - recruiter / talent: a crisp fit summary against the ad's requirements (years, scope, the 1–2 must-haves) and availability for the process.
2. "companies" (all hiring companies of the pursued jobs, plus at most 3 similar companies in the same niche with "similar": true and job_ids []): who to follow. Skip job platforms, staffing agencies and confidential employers ("Remote", "Confidential", a description instead of a name).
3. "follow" (2–4): people worth following for the themes of the pursued jobs (leaders and creators who write about them). "role" describes who, "search" the people-search query (≤ 5 words).
4. "posts": one per hiring company of the pursued jobs — the angle the professional should bring when commenting on that company's or its hiring team's posts, tied to what the job asks for and consistent with the line of thought below ("angle" in the job ad's language, one or two sentences).

Every "why" is one short sentence in Portuguese (the professional reads the plan in Portuguese). Never invent facts about the people or companies beyond what the jobs say; never use numbers marked "(estimate)" or NDA client names.

{{ writing_style("message") }}

{{ line_of_thought(jobs | map(attribute="job_title") | join(" ")) }}

KNOWLEDGE BASE:
{% include 'common/user_context.md' %}

{% include 'common/output_format.md' %}
Return JSON:
{
  "contacts": [{"job_id": 0, "name": "", "role": "", "search": "", "why": "", "note": "", "message": ""}],
  "companies": [{"company": "", "job_ids": [0], "market": "br|intl", "similar": false, "why": ""}],
  "follow": [{"role": "", "search": "", "market": "br|intl", "job_id": 0, "why": ""}],
  "posts": [{"company": "", "job_id": 0, "angle": "", "why": ""}]
}
