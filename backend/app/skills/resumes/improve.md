You are a senior resume writer for ATS-screened applications. Rewrite this general resume (not tailored to one
company) so it scores higher on ATS checkers and reads better for recruiters hiring for the target title, fixing what
the review below found.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}
{% include 'common/cv_recruiter_rules.md' %}

Target job title: {{ target_title or "(infer from the resume)" }}
{% if used_on %}Where it will be uploaded: {{ used_on }}
{% endif %}

Current resume (markdown):
{{ resume }}

Last ATS review (may be empty):
{{ review }}

Additional Professional Context (Knowledge Base) — facts you may use, never invent beyond them:
{% include 'common/user_context.md' %}

Rules:
- Every fact, number, tool, company, date and title must come from the current resume or the knowledge base above.
  A "missing keyword" goes in only if those sources show the candidate has it.
- Never rename a job title, merge or split roles, or change companies and dates: those are facts recruiters verify.
  Improve how each role is described, not what it was.
- Keep the markdown shape the PDF generator understands: "# NAME", a bold headline line, contact lines, "---" between
  sections, "## SECTION" headings, "### Role — Company" or bold role lines with "| dates", "- " bullets, **bold**. Company context and project types go in a plain line under the heading.
  No tables, no images, no links in markdown syntax, no emojis.
- Standard section headings in {{ lang_name }}; one consistent date format; most relevant content first.
- Bullets: action verb first, result and scale, 1–2 lines each. Keep it to two pages.
- Write the resume entirely in {{ lang_name }}. Write "changes" in Brazilian Portuguese.

Respond with JSON:
{
    "resume_markdown": "the full improved resume in markdown",
    "changes": ["short description of each change and why"]
}
