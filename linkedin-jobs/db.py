"""
Database module — PostgreSQL connection and CRUD for job_listings.
"""
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


def get_connection():
    """Return a new PostgreSQL connection."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def run_migration():
    """Execute migration.sql to create the table if it doesn't exist."""
    from config import PROJECT_DIR

    migration_path = PROJECT_DIR / "migration.sql"
    sql = migration_path.read_text(encoding="utf-8")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("✅ Migration executed successfully.")
    finally:
        conn.close()


def upsert_job(url: str, linkedin_job_id: str, job_title: str = "",
               company: str = "", location: str = "",
               easy_apply: bool = False) -> bool:
    """
    Insert a new job or ignore if it already exists (by url).
    Returns True if a new row was inserted, False if it already existed.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.job_listings
                    (url, linkedin_job_id, job_title, company, location, easy_apply, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'new')
                ON CONFLICT (url) DO UPDATE SET
                    easy_apply = EXCLUDED.easy_apply,
                    job_title = CASE WHEN EXCLUDED.job_title != '' THEN EXCLUDED.job_title ELSE job_listings.job_title END,
                    company = CASE WHEN EXCLUDED.company != '' THEN EXCLUDED.company ELSE job_listings.company END,
                    location = CASE WHEN EXCLUDED.location != '' THEN EXCLUDED.location ELSE job_listings.location END
                RETURNING id
            """, (url, linkedin_job_id, job_title, company, location, easy_apply))
            result = cur.fetchone()
        conn.commit()
        return result is not None
    finally:
        conn.close()


def get_jobs_by_status(status: str) -> list[dict]:
    """Fetch all jobs with the given status."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM public.job_listings WHERE status = %s ORDER BY created_at",
                (status,)
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_jobs_by_ids(job_ids: list[int]) -> list[dict]:
    """Fetch specific jobs by ID."""
    if not job_ids:
        return []
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM public.job_listings WHERE id = ANY(%s) ORDER BY created_at",
                (job_ids,)
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_all_active_job_ids() -> set[str]:
    """Get all linkedin_job_ids that are NOT 'removed'."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT linkedin_job_id FROM public.job_listings WHERE status != 'removed'"
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def mark_removed(linkedin_job_ids: list[str]):
    """Mark jobs as 'removed' (unsaved from LinkedIn)."""
    if not linkedin_job_ids:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.job_listings
                SET status = 'removed', updated_at = %s
                WHERE linkedin_job_id = ANY(%s) AND status NOT IN ('done', 'removed')
                """,
                (datetime.now(timezone.utc), linkedin_job_ids)
            )
        conn.commit()
    finally:
        conn.close()


def update_job_description(job_id: int, description: str, language: str, 
                           company_description: str = None, 
                           company_profile_url: str = None, 
                           hiring_team_json: str = None):
    """Save scraped description and update status to 'scraped'."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.job_listings
                SET description = %s, language = %s, status = 'scraped',
                    company_description = %s, company_profile_url = %s,
                    hiring_team_json = %s,
                    scraped_at = %s, updated_at = %s
                WHERE id = %s
            """, (description, language, company_description, 
                  company_profile_url, hiring_team_json,
                  datetime.now(timezone.utc), datetime.now(timezone.utc), job_id))
        conn.commit()
    finally:
        conn.close()


def update_job_status(job_id: int, status: str, **extra):
    """Update job status and optional extra fields."""
    now = datetime.now(timezone.utc)
    sets = ["status = %s", "updated_at = %s"]
    vals = [status, now]

    for key, val in extra.items():
        sets.append(f"{key} = %s")
        vals.append(val)

    vals.append(job_id)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE public.job_listings SET {', '.join(sets)} WHERE id = %s",
                vals,
            )
        conn.commit()
    finally:
        conn.close()
def delete_job(job_id: int):
    """Hard delete a job from the database."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.job_listings WHERE id = %s", (job_id,))
        conn.commit()
    finally:
        conn.close()


def clear_all_jobs():
    """Mark all jobs that are not 'done' as 'removed'."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.job_listings 
                SET status = 'removed', updated_at = %s 
                WHERE status != 'done' AND status != 'removed'
            """, (datetime.now(timezone.utc),))
        conn.commit()
    finally:
        conn.close()
