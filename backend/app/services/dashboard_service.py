from app.db.session import get_db_connection, get_db_cursor

class DashboardService:
    @staticmethod
    def get_stats() -> dict:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                # Total jobs in board
                cur.execute("SELECT count(*) FROM public.job_listings WHERE status != 'removed'")
                total_jobs = cur.fetchone()['count']

                # New jobs (not yet scraped)
                cur.execute("SELECT count(*) FROM public.job_listings WHERE status = 'new'")
                new_jobs = cur.fetchone()['count']

                # Pending in pipeline
                cur.execute("SELECT count(*) FROM public.pipeline_urls WHERE status = 'pending'")
                pipeline_pending = cur.fetchone()['count']

                # Interview stories
                cur.execute("SELECT count(*) FROM public.interview_stories")
                stories_count = cur.fetchone()['count']

                # Applications
                cur.execute("SELECT count(*) FROM public.applications")
                apps_count = cur.fetchone()['count']

                return {
                    "total_jobs": total_jobs,
                    "new_jobs": new_jobs,
                    "pipeline_pending": pipeline_pending,
                    "stories_count": stories_count,
                    "apps_count": apps_count
                }
        finally:
            conn.close()
