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


def insert_manual_job(job_title: str, company: str, location: str, url: str, description: str) -> bool:
    """
    Insert a manually added job directly in 'scraped' status so it's ready for AI generation.
    Returns True if successful.
    """
    conn = get_connection()
    # Generate a unique synthetic linkedin_job_id for manual jobs
    import uuid
    synthetic_id = f"manual_{uuid.uuid4().hex[:8]}"
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.job_listings
                    (url, linkedin_job_id, job_title, company, location, description, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'scraped')
                ON CONFLICT (url) DO UPDATE SET
                    description = EXCLUDED.description,
                    job_title = EXCLUDED.job_title,
                    company = EXCLUDED.company,
                    location = EXCLUDED.location,
                    status = 'scraped'
            """, (url, synthetic_id, job_title, company, location, description))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting manual job: {e}")
        return False
    finally:
        conn.close()


def get_job_by_id(job_id: int) -> dict:
    """Fetch a specific job by ID."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM public.job_listings WHERE id = %s", (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None
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

# ---------------------------------------------------------------------------
# Applications Module
# ---------------------------------------------------------------------------

def get_applications() -> list[dict]:
    """Fetch all tracked job applications."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT a.*, j.location, j.url 
                FROM public.applications a
                LEFT JOIN public.job_listings j ON a.job_id = j.id
                ORDER BY a.updated_at DESC
            """)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def insert_application(job_id: int, company_name: str, job_title: str, apply_method: str, status: str = 'Applied', notes: str = '') -> bool:
    """Insert a new job application."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.applications
                    (job_id, company_name, job_title, apply_method, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (job_id, company_name, job_title, apply_method, status, notes))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting application: {e}")
        return False
    finally:
        conn.close()


def update_application(app_id: int, status: str = None, apply_method: str = None, notes: str = None, company_name: str = None, job_title: str = None) -> bool:
    """Update an application's details."""
    conn = get_connection()
    
    sets = ["updated_at = %s"]
    vals = [datetime.now(timezone.utc)]
    
    if status is not None:
        sets.append("status = %s")
        vals.append(status)
    
    if apply_method is not None:
        sets.append("apply_method = %s")
        vals.append(apply_method)
    
    if notes is not None:
        sets.append("notes = %s")
        vals.append(notes)
        
    if company_name is not None:
        sets.append("company_name = %s")
        vals.append(company_name)

    if job_title is not None:
        sets.append("job_title = %s")
        vals.append(job_title)
        
    vals.append(app_id)
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE public.applications SET {', '.join(sets)} WHERE id = %s",
                vals
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating application: {e}")
        return False
    finally:
        conn.close()


def delete_application(app_id: int) -> bool:
    """Delete an application."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.applications WHERE id = %s", (app_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting application: {e}")
        return False
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Profile Stats Module
# ---------------------------------------------------------------------------

def get_latest_profile_stats() -> dict:
    """Fetch the most recent profile optimization stats."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM public.profile_stats ORDER BY updated_at DESC LIMIT 1")
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()

def upsert_profile_stats(score: int = None, analysis: str = None, 
                         scraped_at: datetime = None, 
                         last_optimized_at: datetime = None,
                         current_data: dict = None) -> bool:
    """Insert or update profile stats. Since we only care about the latest, we can keep it simple or append."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # For simplicity, we'll just insert a new record for history, 
            # and our 'get_latest' will pick the newest.
            cur.execute("""
                INSERT INTO public.profile_stats 
                    (score, analysis, scraped_at, last_optimized_at, current_data, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (score, analysis, scraped_at, last_optimized_at, 
                  json.dumps(current_data) if current_data else None))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error upserting profile stats: {e}")
        return False
    finally:
        conn.close()

import json

# ---------------------------------------------------------------------------
# Job Evaluations (Scoring System)
# ---------------------------------------------------------------------------

def insert_job_evaluation(job_id: int, overall_score: float, match_score: float,
                          north_star_score: float, comp_score: float,
                          cultural_score: float, red_flags: str = "",
                          analysis: str = "", archetype: str = "",
                          ai_provider: str = "", ai_model: str = "") -> bool:
    """Insert a job evaluation with scoring."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.job_evaluations
                    (job_id, overall_score, match_score, north_star_score,
                     comp_score, cultural_score, red_flags, analysis,
                     archetype, ai_provider, ai_model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (job_id, overall_score, match_score, north_star_score,
                  cultural_score, red_flags, analysis, archetype,
                  ai_provider, ai_model))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting job evaluation: {e}")
        return False
    finally:
        conn.close()


def get_job_evaluation(job_id: int) -> dict:
    """Get evaluation for a specific job."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM public.job_evaluations
                WHERE job_id = %s ORDER BY evaluated_at DESC LIMIT 1
            """, (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_all_evaluations() -> list[dict]:
    """Get all job evaluations."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT e.*, j.job_title, j.company, j.url
                FROM public.job_evaluations e
                JOIN public.job_listings j ON e.job_id = j.id
                ORDER BY e.evaluated_at DESC
            """)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_job_archetype(job_id: int, archetype: str, score: float = None):
    """Update job archetype and optionally score on the job_listings table."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if score is not None:
                cur.execute("""
                    UPDATE public.job_listings
                    SET archetype = %s, evaluation_score = %s, updated_at = NOW()
                    WHERE id = %s
                """, (archetype, score, job_id))
            else:
                cur.execute("""
                    UPDATE public.job_listings
                    SET archetype = %s, updated_at = NOW()
                    WHERE id = %s
                """, (archetype, job_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Interview Stories (STAR+R)
# ---------------------------------------------------------------------------

def get_interview_stories(tags: list[str] = None, archetypes: list[str] = None) -> list[dict]:
    """Get interview stories, optionally filtered by tags or archetypes."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if tags:
                cur.execute("""
                    SELECT * FROM public.interview_stories
                    WHERE tags && %s::text[]
                    ORDER BY usage_count DESC, updated_at DESC
                """, (tags,))
            elif archetypes:
                cur.execute("""
                    SELECT * FROM public.interview_stories
                    WHERE archetypes && %s::text[]
                    ORDER BY usage_count DESC, updated_at DESC
                """, (archetypes,))
            else:
                cur.execute("""
                    SELECT * FROM public.interview_stories
                    ORDER BY usage_count DESC, updated_at DESC
                """)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def insert_interview_story(title: str, situation: str = "", task: str = "",
                           action: str = "", result: str = "", reflection: str = "",
                           tags: list[str] = None, archetypes: list[str] = None) -> int:
    """Insert a new interview story. Returns the story ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.interview_stories
                    (title, situation, task, action, result, reflection, tags, archetypes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (title, situation, task, action, result, reflection,
                  tags or [], archetypes or []))
            row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    except Exception as e:
        print(f"Error inserting interview story: {e}")
        return None
    finally:
        conn.close()


def update_story_usage_count(story_id: int):
    """Increment the usage count for a story."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.interview_stories
                SET usage_count = usage_count + 1, updated_at = NOW()
                WHERE id = %s
            """, (story_id,))
        conn.commit()
    finally:
        conn.close()


def delete_interview_story(story_id: int) -> bool:
    """Delete an interview story."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.interview_stories WHERE id = %s", (story_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting interview story: {e}")
        return False
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Pipeline URLs
# ---------------------------------------------------------------------------

def insert_pipeline_url(url: str, source: str = "manual") -> bool:
    """Add a URL to the processing pipeline."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.pipeline_urls (url, source, status)
                VALUES (%s, %s, 'pending')
                ON CONFLICT DO NOTHING
            """, (url, source))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting pipeline URL: {e}")
        return False
    finally:
        conn.close()


def get_pipeline_urls(status: str = "pending") -> list[dict]:
    """Get pipeline URLs by status."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM public.pipeline_urls
                WHERE status = %s ORDER BY created_at ASC
            """, (status,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_pipeline_url(pipeline_id: int, status: str, error_message: str = None):
    """Update pipeline URL status."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if status == "done":
                cur.execute("""
                    UPDATE public.pipeline_urls
                    SET status = %s, processed_at = NOW()
                    WHERE id = %s
                """, (status, pipeline_id))
            elif error_message:
                cur.execute("""
                    UPDATE public.pipeline_urls
                    SET status = %s, error_message = %s, processed_at = NOW()
                    WHERE id = %s
                """, (status, error_message, pipeline_id))
            else:
                cur.execute("""
                    UPDATE public.pipeline_urls
                    SET status = %s, processed_at = NOW()
                    WHERE id = %s
                """, (status, pipeline_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AI Config
# ---------------------------------------------------------------------------

def get_ai_config() -> dict:
    """Get current AI provider configuration."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM public.ai_config ORDER BY updated_at DESC LIMIT 1")
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def save_ai_config(provider: str, model: str, base_url: str = "") -> bool:
    """Save AI provider configuration."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.ai_config (provider, model, base_url, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT DO NOTHING
            """, (provider, model, base_url))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving AI config: {e}")
        return False
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Job Evaluations (Scoring System)
# ---------------------------------------------------------------------------

def insert_job_evaluation(job_id: int, overall_score: float, match_score: float,
                          north_star_score: float, comp_score: float,
                          cultural_score: float, red_flags: str = "",
                          analysis: str = "", archetype: str = "",
                          ai_provider: str = "", ai_model: str = "") -> bool:
    """Insert a job evaluation with scoring."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.job_evaluations
                    (job_id, overall_score, match_score, north_star_score,
                     comp_score, cultural_score, red_flags, analysis,
                     archetype, ai_provider, ai_model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (job_id, overall_score, match_score, north_star_score,
                  cultural_score, red_flags, analysis, archetype,
                  ai_provider, ai_model))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting job evaluation: {e}")
        return False
    finally:
        conn.close()


def get_job_evaluation(job_id: int) -> dict:
    """Get evaluation for a specific job."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM public.job_evaluations
                WHERE job_id = %s ORDER BY evaluated_at DESC LIMIT 1
            """, (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_all_evaluations() -> list[dict]:
    """Get all job evaluations."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT e.*, j.job_title, j.company, j.url
                FROM public.job_evaluations e
                JOIN public.job_listings j ON e.job_id = j.id
                ORDER BY e.evaluated_at DESC
            """)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_job_archetype(job_id: int, archetype: str, score: float = None):
    """Update job archetype and optionally score on the job_listings table."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if score is not None:
                cur.execute("""
                    UPDATE public.job_listings
                    SET archetype = %s, evaluation_score = %s, updated_at = NOW()
                    WHERE id = %s
                """, (archetype, score, job_id))
            else:
                cur.execute("""
                    UPDATE public.job_listings
                    SET archetype = %s, updated_at = NOW()
                    WHERE id = %s
                """, (archetype, job_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Interview Stories (STAR+R)
# ---------------------------------------------------------------------------

def get_interview_stories(tags: list[str] = None, archetypes: list[str] = None) -> list[dict]:
    """Get interview stories, optionally filtered by tags or archetypes."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if tags:
                cur.execute("""
                    SELECT * FROM public.interview_stories
                    WHERE tags && %s::text[]
                    ORDER BY usage_count DESC, updated_at DESC
                """, (tags,))
            elif archetypes:
                cur.execute("""
                    SELECT * FROM public.interview_stories
                    WHERE archetypes && %s::text[]
                    ORDER BY usage_count DESC, updated_at DESC
                """, (archetypes,))
            else:
                cur.execute("""
                    SELECT * FROM public.interview_stories
                    ORDER BY usage_count DESC, updated_at DESC
                """)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def insert_interview_story(title: str, situation: str = "", task: str = "",
                           action: str = "", result: str = "", reflection: str = "",
                           tags: list[str] = None, archetypes: list[str] = None) -> int:
    """Insert a new interview story. Returns the story ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.interview_stories
                    (title, situation, task, action, result, reflection, tags, archetypes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (title, situation, task, action, result, reflection,
                  tags or [], archetypes or []))
            row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    except Exception as e:
        print(f"Error inserting interview story: {e}")
        return None
    finally:
        conn.close()


def update_story_usage_count(story_id: int):
    """Increment the usage count for a story."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.interview_stories
                SET usage_count = usage_count + 1, updated_at = NOW()
                WHERE id = %s
            """, (story_id,))
        conn.commit()
    finally:
        conn.close()


def delete_interview_story(story_id: int) -> bool:
    """Delete an interview story."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.interview_stories WHERE id = %s", (story_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting interview story: {e}")
        return False
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Pipeline URLs
# ---------------------------------------------------------------------------

def insert_pipeline_url(url: str, source: str = "manual") -> bool:
    """Add a URL to the processing pipeline."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.pipeline_urls (url, source, status)
                VALUES (%s, %s, 'pending')
                ON CONFLICT DO NOTHING
            """, (url, source))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting pipeline URL: {e}")
        return False
    finally:
        conn.close()


def get_pipeline_urls(status: str = "pending") -> list[dict]:
    """Get pipeline URLs by status."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM public.pipeline_urls
                WHERE status = %s ORDER BY created_at ASC
            """, (status,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_pipeline_url(pipeline_id: int, status: str, error_message: str = None):
    """Update pipeline URL status."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if status == "done":
                cur.execute("""
                    UPDATE public.pipeline_urls
                    SET status = %s, processed_at = NOW()
                    WHERE id = %s
                """, (status, pipeline_id))
            elif error_message:
                cur.execute("""
                    UPDATE public.pipeline_urls
                    SET status = %s, error_message = %s, processed_at = NOW()
                    WHERE id = %s
                """, (status, error_message, pipeline_id))
            else:
                cur.execute("""
                    UPDATE public.pipeline_urls
                    SET status = %s, processed_at = NOW()
                    WHERE id = %s
                """, (status, pipeline_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AI Config
# ---------------------------------------------------------------------------

def get_ai_config() -> dict:
    """Get current AI provider configuration."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM public.ai_config ORDER BY updated_at DESC LIMIT 1")
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def save_ai_config(provider: str, model: str, base_url: str = "") -> bool:
    """Save AI provider configuration."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.ai_config (provider, model, base_url, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT DO NOTHING
            """, (provider, model, base_url))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving AI config: {e}")
        return False
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# V3 End-to-End Functions
# ---------------------------------------------------------------------------

def upsert_user_profile(full_data: dict, base_resume_md: str, user_id: str = 'default') -> bool:
    """Insert or update exhaustive user profile."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.user_profiles (user_id, full_data, base_resume_md, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    full_data = EXCLUDED.full_data,
                    base_resume_md = EXCLUDED.base_resume_md,
                    updated_at = NOW()
            """, (user_id, json.dumps(full_data), base_resume_md))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving user profile: {e}")
        return False
    finally:
        conn.close()


def get_user_profile(user_id: str = 'default') -> dict:
    """Fetch user profile data."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM public.user_profiles WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def upsert_search_strategy(title: str, keywords: list, locations: list, remote_only: bool, ai_suggestions: str = "", user_id: str = 'default') -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.search_strategies (user_id, title, keywords, locations, remote_only, ai_suggestions, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (user_id, title, keywords, locations, remote_only, ai_suggestions))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving search strategy: {e}")
        return False
    finally:
        conn.close()


def get_search_strategies(user_id: str = 'default', active_only: bool = True) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if active_only:
                cur.execute("SELECT * FROM public.search_strategies WHERE user_id = %s AND is_active = TRUE ORDER BY created_at DESC", (user_id,))
            else:
                cur.execute("SELECT * FROM public.search_strategies WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def upsert_skill_gap(skill_name: str, priority: str = 'medium') -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.skill_gaps (skill_name, priority, frequency, last_seen_at)
                VALUES (%s, %s, 1, NOW())
                ON CONFLICT (skill_name) DO UPDATE SET
                    frequency = public.skill_gaps.frequency + 1,
                    last_seen_at = NOW()
            """, (skill_name, priority))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving skill gap: {e}")
        return False
    finally:
        conn.close()


def get_skill_gaps() -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM public.skill_gaps ORDER BY frequency DESC, last_seen_at DESC")
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_job_outreach(job_id: int, email_draft: str, dm_draft: str) -> bool:
    """Save outreach drafts to the job."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.job_listings
                SET email_draft = %s, linkedin_dm_draft = %s, updated_at = NOW()
                WHERE id = %s
            """, (email_draft, dm_draft, job_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating job outreach: {e}")
        return False
    finally:
        conn.close()


def update_job_recruiter(job_id: int, email: str, linkedin_url: str) -> bool:
    """Save recruiter info to the job."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.job_listings
                SET recruiter_email = %s, recruiter_linkedin_url = %s, updated_at = NOW()
                WHERE id = %s
            """, (email, linkedin_url, job_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating job recruiter: {e}")
        return False
    finally:
        conn.close()


def job_exists(url: str) -> bool:
    """Check if a job with this URL exists in job_listings or pipeline_urls."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM public.job_listings WHERE url = %s", (url,))
            if cur.fetchone():
                return True
            cur.execute("SELECT 1 FROM public.pipeline_urls WHERE url = %s", (url,))
            if cur.fetchone():
                return True
            return False
    finally:
        conn.close()


def add_pipeline_url(url: str, source: str = 'manual') -> bool:
    """Add a URL to the batch processing pipeline."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.pipeline_urls (url, source, status, created_at)
                VALUES (%s, %s, 'pending', NOW())
                ON CONFLICT (url) DO NOTHING
            """, (url, source))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding pipeline URL: {e}")
        return False
    finally:
        conn.close()


def delete_search_strategy(strategy_id: int) -> bool:
    """Permanently delete a search strategy."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.search_strategies WHERE id = %s", (strategy_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting strategy: {e}")
        return False
    finally:
        conn.close()


def save_skill_gaps(job_id: int, analysis: dict) -> bool:
    """Save or update skill gap analysis for a job."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.skill_gaps (job_id, gaps_json, match_score, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (job_id) DO UPDATE SET
                    gaps_json = EXCLUDED.gaps_json,
                    match_score = EXCLUDED.match_score,
                    updated_at = NOW()
            """, (job_id, json.dumps(analysis), analysis.get("match_score")))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving skill gaps: {e}")
        return False
    finally:
        conn.close()


def get_skill_gaps(job_id: int) -> dict:
    """Retrieve skill gap analysis for a job."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT gaps_json FROM public.skill_gaps WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
            return row[0] if row else {}
    except Exception as e:
        print(f"Error getting skill gaps: {e}")
        return {}
    finally:
        conn.close()
