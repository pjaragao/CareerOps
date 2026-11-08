Someone replied to a comment the professional left on a LinkedIn post. Read the post, the professional's comment and the reply, and decide what the professional should do: only like the reply, or like it and answer.

{% include 'common/critical_rules.md' %}

THE PROFESSIONAL: sanitary & environmental engineer and former CFO, 18 years in infrastructure engineering and finance, now also building data, modeling and AI systems.

POST{% if post_author %} by {{ post_author }}{% endif %}:
"""
{{ post_text }}
"""

THE PROFESSIONAL'S COMMENT:
"""
{{ my_comment }}
"""
{% if thread %}
THE THREAD AS SHOWN ON THE PAGE (names, headlines and times mixed in):
"""
{{ thread }}
"""
{% endif %}
REPLY — by {{ reply_author or "someone" }}:
"""
{{ reply_text }}
"""

DECIDE:
- "like": the reply only thanks, agrees, praises, reacts with an emoji or tags someone — there is nothing left to say, and another message would only stretch the exchange. A like closes it well. This is the usual case.
- "reply": the reply adds a point, disagrees, asks a question or opens a real discussion that deserves an answer. Answer that point directly: agree or push back with one concrete reason, an example from real work, or a short answer to the question. At most one question back, only if it moves the discussion.
- "ignore": the reply is spam, a sales pitch, off-topic, hostile, or not addressed to the professional.

WHEN "reply":
- Write in the language of the reply (the same language they used).
- Do not start with the person's name: the reply goes out with an @mention of them in front. Up to ~350 characters.
- Never self-promote, never link, never ask for a job, no hashtags. Only facts from the knowledge base; never numbers marked "(estimate)" or NDA client names.

{{ writing_style("comment") }}

KNOWLEDGE BASE:
{% include 'common/user_context.md' %}

{% include 'common/output_format.md' %}
Return JSON:
{"decision": "like|reply|ignore", "reason": "one short sentence in Portuguese on why", "lang": "ISO 639-1 code of the reply's language", "reply": "the answer text when decision is reply, else empty"}
