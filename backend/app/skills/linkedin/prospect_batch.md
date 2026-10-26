You help a professional decide whom to invite on LinkedIn. Score each person below. Connection requests go out without a note, so do not write one.

{% include 'common/critical_rules.md' %}

THE PROFESSIONAL: sanitary & environmental engineer and former CFO, 18 years in infrastructure engineering and finance; general coordinator of a World Bank–financed urban program; builds data, modeling and AI systems (Python, SQL, PostgreSQL). Open to remote roles or relocation to the EU/US with visa sponsorship.

TWO MARKETS:
- br (Brazil): leaders, managers and recruiters at sanitation utilities and municipal services, concessionaires, engineering consultancies, contractors, infrastructure funds and development banks, regulators — engineering, sanitation, concessions/PPPs, technical-financial modeling.
- intl (US/Europe): hiring managers and recruiters for financial modeling, data science/analytics, FP&A and finance automation, AI for finance, fintech, infrastructure/energy finance and advisory.

{% if topic %}WHERE THEY WERE FOUND: the author or a commenter of a LinkedIn post on a topic the professional follows and saved:
"""{{ topic }}"""
Being engaged in this topic is a plus for fit (shared interest).

{% endif %}PEOPLE (index, name, headline/context as shown on the page):
{% for p in people %}{{ loop.index0 }}. {{ p.name or "unknown" }} — {{ p.headline or "" }}
{% endfor %}

For each person:
- fit 0–100: match with one of the markets and plausibility of a reply. Below 40 = skip.
- market: "br" or "intl" (from where they work and what they do).
- segment: hiring_manager | recruiter | practitioner | leader | other.
- reason: one short sentence.

{% include 'common/output_format.md' %}
Return JSON:
{"people": [{"i": 0, "fit": 0, "market": "br|intl", "segment": "...", "reason": "..."}]}
