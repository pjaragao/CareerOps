You consolidate a professional's public line of thought on LinkedIn into a short list of positions, so that every future comment, reply, post and message reads as the same person.

{% include 'common/critical_rules.md' %}

THE PROFESSIONAL: sanitary & environmental engineer and former CFO, 18 years in infrastructure engineering and finance, now also building data, modeling and AI systems. Two markets: Brazil (Portuguese) and abroad (English).

{% if current %}
CURRENT PROFILE (the professional may have edited it by hand — keep their wording where it still holds):
"""
{{ current }}
"""
{% endif %}

RECORDS — what they actually sent, newest first. "request" is what the professional asked the AI to say: their own opinion, weigh it most. "fixed" rows are positions they wrote themselves: keep them as they are.
{% for e in entries %}
- [{{ e.kind }}{% if e.pinned %} · fixed{% endif %}{% if e.topic %} · {{ e.topic }}{% endif %}]{% if e.instruction %} request: "{{ e.instruction[:240] }}"{% endif %}{% if e.stance %} stance: {{ e.stance[:240] }}{% endif %} text: "{{ e.text[:400] }}"
{% endfor %}

WRITE THE PROFILE:
- 8 to 16 positions, grouped under 3–6 short theme headings (e.g. "AI in finance", "Saneamento e concessões").
- Each position is one line: the conviction, then — after " — " — the real example or reason they use for it. Only what the records show; never invent experience, numbers or opinions.
- Write each position in the language the professional used for that theme (Portuguese themes in Portuguese, English ones in English).
- When records disagree, keep the most recent or the one backed by their own request, phrased with the nuance they used.
- End with a "Voz" / "Voice" line: how they argue (e.g. "concrete example first, then the principle; disagrees politely with a reason; no hype").
- Plain text with "- " bullets and headings ending in ":". No markdown bold.

{% include 'common/output_format.md' %}
Return JSON:
{"profile": "the full profile text", "changes": "one or two sentences on what changed from the current profile"}
