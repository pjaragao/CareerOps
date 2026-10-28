Check whether this job ad requires something the candidate cannot meet: living in a specific country/region, or
being legally authorized to work there without sponsorship.

{% include 'common/output_format.md' %}

Candidate:
- Citizenship: {{ citizenship }}
- Lives in: {{ city }}
- Authorized to work in: {{ authorized }} — needs visa sponsorship anywhere else
- Open to remote work; willing to relocate to {{ relocate }} only with sponsorship

Job Title: {{ job_title }}
Company: {{ company }}
Location field (for reference only): {{ location }}

Job Description:
{{ job_description }}

Rules:
- Read the DESCRIPTION (and any requirements / eligibility / "who can apply" text). Do NOT flag a job only because the
  location field names a country: a "United States" location with a "remote worldwide / LATAM / Brazil" description is fine.
- Flag "residency" when the text requires living / being based in a country or region the candidate is not in
  (e.g. "must reside in the US", "US-based candidates only", "remote within EU", "must be located in Canada",
  "EST time zone, US residents", "UK only"). A region that includes Brazil (LATAM, Americas, worldwide, Brazil) is fine.
- Flag "work_authorization" when the text requires work authorization the candidate lacks without offering sponsorship
  (e.g. "must be authorized to work in the US", "we do not sponsor visas", "no sponsorship", "US citizen",
  "green card holder", "security clearance", "EU work permit required", "right to work in the UK").
- "blocked" = stated as a requirement. "warning" = soft or ambiguous ("preferred", "ideally based in", "US hours",
  hybrid/on-site abroad with no word on sponsorship). "ok" = nothing of the kind, or the job offers visa sponsorship /
  relocation support, or explicitly accepts candidates from Brazil/LATAM/anywhere.
- Quote the exact sentence from the ad for every issue. No issue without a quote from the ad.

Respond with JSON:
{
    "status": "ok" | "warning" | "blocked",
    "issues": [
        {"type": "residency" | "work_authorization", "quote": "exact sentence from the ad", "reason": "short explanation in Portuguese"}
    ]
}
