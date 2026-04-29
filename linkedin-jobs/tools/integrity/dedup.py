"""
Dedup - Remove duplicate jobs by linkedin_job_id or URL.
Keeps the most recent entry (highest id).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


def dedup_jobs():
    """Find and remove duplicate jobs."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT linkedin_job_id, COUNT(*) as cnt
                FROM public.job_listings
                WHERE linkedin_job_id IS NOT NULL
                GROUP BY linkedin_job_id
                HAVING COUNT(*) > 1
            """)
            duplicates = cur.fetchall()

            if not duplicates:
                print("No duplicates found.")
                return 0

            removed = 0
            for linkedin_job_id, count in duplicates:
                with conn.cursor() as cur2:
                    cur2.execute("""
                        DELETE FROM public.job_listings
                        WHERE linkedin_job_id = %s
                        AND id NOT IN (
                            SELECT MAX(id) FROM public.job_listings
                            WHERE linkedin_job_id = %s
                        )
                    """, (linkedin_job_id, linkedin_job_id))
                    removed += cur2.rowcount

            conn.commit()
            print(f"Removed {removed} duplicate jobs.")
            return removed
    finally:
        conn.close()


if __name__ == "__main__":
    dedup_jobs()
