"""
Processor — scrapes full description for each 'new' job, saves to DB.
"""
import time
from config import SCRAPE_DELAY
import db
import scraper


def process_new_jobs(delay: int | None = None):
    """
    Fetch all jobs with status 'new', scrape their descriptions,
    and update DB with description + language + status='scraped'.
    """
    if delay is None:
        delay = SCRAPE_DELAY

    jobs = db.get_jobs_by_status("new")
    if not jobs:
        print("\n✅ No new jobs to process.")
        return

    print(f"\n⚙️  Processing {len(jobs)} new jobs...")

    for i, job in enumerate(jobs, 1):
        print(f"\n   [{i}/{len(jobs)}] {job['job_title'] or job['url']}")

        try:
            job_data = scraper.scrape_job_description(job["url"])
            description = job_data["description"]
            language = job_data["language"]

            if not description or len(description) < 50:
                print(f"   ⚠️  Description too short ({len(description)} chars). Marking as error.")
                db.update_job_status(job["id"], "error")
                continue

            db.update_job_description(
                job_id=job["id"],
                description=description,
                language=language,
                company_description=job_data.get("company_description"),
                company_profile_url=job_data.get("company_profile_url"),
                hiring_team_json=job_data.get("hiring_team")
            )
            print(f"   ✅ Scraped ({language}) — {len(description)} chars")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            db.update_job_status(job["id"], "error")

        # Delay between requests to avoid LinkedIn blocking
        if i < len(jobs):
            print(f"   ⏳ Waiting {delay}s...")
            time.sleep(delay)

    print("\n✅ Processing complete.")
