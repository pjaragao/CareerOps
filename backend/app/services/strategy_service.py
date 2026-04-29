from typing import List, Optional
from app.db.session import get_db_connection, get_db_cursor
import json

class StrategyService:
    @staticmethod
    def get_strategies() -> List[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.search_strategies ORDER BY created_at DESC")
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def save_strategy(title: str, keywords: List[str], locations: List[str], remote_only: bool = True) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.search_strategies (title, keywords, locations, remote_only, active, created_at)
                    VALUES (%s, %s, %s, %s, TRUE, NOW())
                """, (title, keywords, locations, remote_only))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    def delete_strategy(strat_id: int) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.search_strategies WHERE id = %s", (strat_id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
