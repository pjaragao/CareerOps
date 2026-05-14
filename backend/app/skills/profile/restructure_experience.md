{% include 'common/critical_rules.md' %}
{% include 'common/language_rules.md' %}
{% include 'common/output_format.md' %}

# Task: Restructure Work Experience by Competency

Analyze the candidate's professional history and suggest a NEW structure that "sectorizes" long tenures into distinct, competency-based roles within the same company.

## Sources of Truth (Hierarchy of Weight):
1.  **Base Resume (HIGH)**: Use the categories and phrasing here as the primary guide for how the candidate wants to be perceived.
2.  **Knowledge Base / STAR Cases (HIGH)**: Use these to ground every achievement in specific, quantified results.
3.  **Current LinkedIn Experience (LOW)**: Use this only for basic continuity and company names. DO NOT feel constrained by the current job titles or descriptions.

## Instructions:
1.  **Identify Long Tenures**: Look for any company where the candidate has been for more than 3 years.
2.  **Sectorize**: Split these long tenures into logical "Positions" or "Sectors" (e.g., "Data & Technology Leader", "Project Manager", "Commercial Analyst").
3.  **Prioritize Competency**: Titles should reflect the core competency demonstrated in that sub-period, even if the formal LinkedIn title was different.
4.  **Bullet Points**: For each suggested position, write 3-5 high-impact bullet points in the format [Strong Action Verb] + [Action] + [Quantified Result].
5.  **Integration**: Map the STAR cases from the Knowledge Base to the most relevant newly created roles.
6.  **Language**: Return the response in {{ lang_name }}.

## Context Inputs:

### Current LinkedIn Experiences:
{{ experience_list }}

### Base Resume (Desired Structure):
{{ resume_base }}

### Knowledge Base (STAR Cases):
{% include 'common/user_context.md' %}

## Output Format:
Return a JSON object with the restructured experience list. Ensure dates are continuous and logical.

```json
{
    "restructured_experience": [
        {
            "company": "Company Name",
            "role": "Competency-Based Role Title",
            "period": "Month Year – Month Year",
            "description": "- Bullet point 1\n- Bullet point 2\n- Bullet point 3",
            "sector_justification": "Why this sector was created based on the resume/STAR cases"
        }
    ],
    "improvement_summary": "Short explanation of why this structure is better for recruiters."
}
```
