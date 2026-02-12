"""
Resume Generator — uses Gemini API to create customized resumes,
then converts to PDF via Gotenberg.
"""
import json
import re
import requests
from datetime import datetime, timezone

import google.generativeai as genai

from config import GEMINI_API_KEY, GOTENBERG_URL, OUTPUT_DIR, RESUME_BASE_FILE, PROMPT_FILE
import db
from resume_template import markdown_to_html, wrap_in_template


def _load_file(path) -> str:
    """Load a text file and return its contents."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _build_prompt(job: dict) -> str:
    """
    Build the Gemini prompt by loading prompt_template.md and resume_base.md
    and filling in the job details.
    """
    prompt_template = _load_file(PROMPT_FILE)
    resume_base = _load_file(RESUME_BASE_FILE)

    return prompt_template.format(
        job_title=job.get("job_title", "Job Opportunity"),
        company=job.get("company", "Direct Hiring"),
        language=job.get("language", "en"),
        description=job.get("description", "")[:15000],
        resume_base=resume_base,
    )


def _call_gemini(prompt: str) -> str:
    """
    Call Gemini API and return the resume markdown.
    """
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.7,
        ),
    )

    # Parse the JSON response
    text = response.text.strip()

    # Try direct JSON parse
    try:
        data = json.loads(text)
        if "resume_markdown" in data:
            return data["resume_markdown"]
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code block
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if "resume_markdown" in data:
                return data["resume_markdown"]
        except json.JSONDecodeError:
            pass

    # Fallback: return raw text
    return text


def _convert_to_pdf(html: str) -> bytes:
    """
    Send HTML to Gotenberg and get PDF bytes back.
    """
    url = f"{GOTENBERG_URL}/forms/chromium/convert/html"

    files = {
        "index.html": ("index.html", html.encode("utf-8"), "text/html"),
    }

    response = requests.post(url, files=files, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(
            f"Gotenberg error {response.status_code}: {response.text[:500]}"
        )

    return response.content


def _safe_filename(text: str, max_len: int = 30) -> str:
    """Create a filesystem-safe string from text."""
    clean = re.sub(r'[^a-zA-Z0-9]', '_', text)
    clean = re.sub(r'_+', '_', clean).strip('_')
    return clean[:max_len]


def generate_resumes():
    """
    Generate customized resumes for all jobs with status 'scraped'.
    Pipeline: Gemini AI → HTML → Gotenberg PDF → save file.
    """
    jobs = db.get_jobs_by_status("scraped")
    if not jobs:
        print("\n✅ No scraped jobs to generate resumes for.")
        return

    print(f"\n📝 Generating resumes for {len(jobs)} jobs...")

    for i, job in enumerate(jobs, 1):
        title = job.get("job_title", "Unknown")
        company = job.get("company", "Unknown")
        print(f"\n   [{i}/{len(jobs)}] {title} @ {company}")

        # Mark as generating
        db.update_job_status(job["id"], "generating")

        try:
            # Step 1: Build prompt and call Gemini
            print("   🤖 Calling Gemini AI...")
            prompt = _build_prompt(job)
            resume_md = _call_gemini(prompt)

            if not resume_md or len(resume_md) < 100:
                print(f"   ⚠️  Gemini response too short ({len(resume_md)} chars)")
                db.update_job_status(job["id"], "error")
                continue

            # Step 2: Convert Markdown to HTML
            print("   🎨 Converting to HTML...")
            html_content = markdown_to_html(resume_md)
            full_html = wrap_in_template(html_content)

            # Step 3: Convert HTML to PDF via Gotenberg
            print("   📄 Generating PDF via Gotenberg...")
            pdf_bytes = _convert_to_pdf(full_html)

            # Step 4: Save PDF
            date_str = datetime.now().strftime("%Y%m%d")
            file_name = (
                f"{_safe_filename(company)}_{_safe_filename(title)}_{date_str}.pdf"
            )
            pdf_path = OUTPUT_DIR / file_name
            pdf_path.write_bytes(pdf_bytes)

            # Step 5: Update DB
            db.update_job_status(
                job["id"], "done",
                file_name=file_name,
                generated_at=datetime.now(timezone.utc),
            )

            print(f"   ✅ Saved: {pdf_path}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            db.update_job_status(job["id"], "error")

    print("\n✅ Resume generation complete.")
