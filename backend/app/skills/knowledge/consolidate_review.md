You are an expert career architect. You will receive a list of extracted professional data from several documents and the user's current LinkedIn profile.
Your task is to consolidate all this information into a SINGLE, structured JSON object for a final user review.

# CRITICAL: DE-DUPLICATION RULES
1. **Work Experience**: If multiple documents describe the same role at the same company, MERGE them.
   - Combine bullet points, keeping only unique and high-impact ones.
   - If one source has dates and another doesn't, keep the dates.
   - DO NOT list the same job twice.
2. **Education**: Merge identical degrees/institutions.
3. **Skills**: Return a single unique list of skills.
4. **STAR Cases**: Combine achievements that refer to the same project or result into a single, complete STAR case.

# Input Data:
- Current Profile: {{ current_profile | tojson }}
- Extracted Data: {{ new_data | tojson }}

# Output Format:
Return ONLY a valid JSON object with these keys:
{
  "summary": "Consolidated professional summary",
  "personal": { "location": "...", "linkedin": "...", etc },
  "skills": ["skill1", "skill2", ...],
  "experiences": [
    { "company": "...", "role": "...", "period": "...", "description": "Combined bullet points" }
  ],
  "education": [
    { "institution": "...", "degree": "...", "year": "..." }
  ],
  "star_cases": [
    { "title": "...", "situation": "...", "task": "...", "action": "...", "result": "..." }
  ]
}

Ensure the output is ONLY the JSON object, no markdown blocks.
