"""
Verify - Health check for the pipeline.
Checks data integrity, orphan records, and system status.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


def verify_pipeline():
    """Run health checks on the database and report issues."""
    conn = db.get_connection()
    issues = []
    warnings = []
    stats = {}

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.job_listings WHERE status = 'new'")
            stats["new"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM public.job_listings WHERE status = 'scraped'")
            stats["scraped"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM public.job_listings WHERE status = 'done'")
            stats["done"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM public.job_listings WHERE status = 'error'")
            stats["error"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM public.job_listings WHERE status = 'removed'")
            stats["removed"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM public.job_listings WHERE status NOT IN ('new','scraped','done','error','removed','generating')")
            non_canonical = cur.fetchone()[0]
            if non_canonical > 0:
                issues.append(f"{non_canonical} jobs have non-canonical statuses")

            cur.execute("""
                SELECT COUNT(*) FROM public.job_listings j
                LEFT JOIN public.job_evaluations e ON j.id = e.job_id
                WHERE j.status = 'scraped' AND e.id IS NULL
            """)
            unevaluated = cur.fetchone()[0]
            if unevaluated > 0:
                warnings.append(f"{unevaluated} scraped jobs have no evaluation")

            cur.execute("""
                SELECT COUNT(*) FROM public.job_evaluations e
                LEFT JOIN public.job_listings j ON e.job_id = j.id
                WHERE j.id IS NULL
            """)
            orphan_evals = cur.fetchone()[0]
            if orphan_evals > 0:
                issues.append(f"{orphan_evals} orphan evaluations (job deleted)")

            cur.execute("""
                SELECT COUNT(*) FROM public.applications a
                LEFT JOIN public.job_listings j ON a.job_id = j.id
                WHERE a.job_id IS NOT NULL AND j.id IS NULL
            """)
            orphan_apps = cur.fetchone()[0]
            if orphan_apps > 0:
                warnings.append(f"{orphan_apps} applications reference deleted jobs")

            cur.execute("SELECT COUNT(*) FROM public.applications")
            stats["applications"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM public.interview_stories")
            stats["stories"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM public.profile_stats")
            stats["profile_stats"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM public.pipeline_urls WHERE status = 'pending'")
            stats["pending_urls"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM public.job_listings
                WHERE description IS NOT NULL AND LENGTH(description) < 50
                AND status = 'scraped'
            """)
            short_desc = cur.fetchone()[0]
            if short_desc > 0:
                warnings.append(f"{short_desc} scraped jobs have very short descriptions")

    finally:
        conn.close()

    print("\n=== Pipeline Health Check ===\n")
    print("Job Statuses:")
    for status, count in stats.items():
        if status in ("applications", "stories", "profile_stats", "pending_urls"):
            continue
        print(f"  {status}: {count}")
    print(f"\nApplications: {stats.get('applications', 0)}")
    print(f"Interview Stories: {stats.get('stories', 0)}")
    print(f"Profile Stats: {stats.get('profile_stats', 0)}")
    print(f"Pending Pipeline URLs: {stats.get('pending_urls', 0)}")

    if issues:
        print(f"\n❌ Issues ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")

    if warnings:
        print(f"\n⚠️  Warnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")

    if not issues and not warnings:
        print("\n✅ All checks passed!")

    return {"issues": issues, "warnings": warnings, "stats": stats}


if __name__ == "__main__":
    verify_pipeline()
