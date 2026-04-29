from typing import List, Optional
from app.db.session import get_db_connection, get_db_cursor
from datetime import datetime, timezone

class PipelineService:
    @staticmethod
    def get_urls(status: str = 'pending') -> List[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("""
                    SELECT * FROM public.pipeline_urls 
                    WHERE status = %s 
                    ORDER BY created_at DESC
                """, (status,))
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def add_url(url: str, source: str = 'manual') -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.pipeline_urls (url, source, status, created_at)
                    VALUES (%s, %s, 'pending', NOW())
                    ON CONFLICT (url) DO NOTHING
                """, (url, source))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    def delete_url(url_id: int) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.pipeline_urls WHERE id = %s", (url_id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    def update_status(url_id: int, status: str) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE public.pipeline_urls 
                    SET status = %s, processed_at = NOW() 
                    WHERE id = %s
                """, (status, url_id))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
