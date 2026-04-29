"""
Normalize - Normalize job statuses to canonical values.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

CANONICAL_STATUSES = {"new", "scraped", "done", "error", "removed", "generating"}
STATUS_MAPPING = {
    "pending": "new",
    "processing": "scraped",
    "complete": "done",
    "failed": "error",
    "deleted": "removed",
    "cancelled": "removed",
    "generating": "generating",
}


def normalize_statuses():
    """Normalize non-canonical statuses to standard values."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT status FROM public.job_listings
                WHERE status NOT IN %s
            """, (tuple(CANONICAL_STATUSES),))
            non_canonical = [row[0] for row in cur.fetchall()]

            if not non_canonical:
                print("All statuses are already canonical.")
                return 0

            updated = 0
            for status in non_canonical:
                normalized = STATUS_MAPPING.get(status.lower(), status.lower())
                if normalized not in CANONICAL_STATUSES:
                    normalized = "new"

                with conn.cursor() as cur2:
                    cur2.execute("""
                        UPDATE public.job_listings
                        SET status = %s, updated_at = NOW()
                        WHERE status = %s
                    """, (normalized, status))
                    updated += cur2.rowcount
                print(f"  {status} -> {normalized} ({cur2.rowcount} rows)")

            conn.commit()
            print(f"\nNormalized {updated} jobs.")
            return updated
    finally:
        conn.close()


if __name__ == "__main__":
    normalize_statuses()
