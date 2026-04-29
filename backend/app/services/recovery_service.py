from app.db.session import get_db_connection
import logging

class RecoveryService:
    @staticmethod
    def auto_recover_stalled_jobs():
        """Reset jobs that were left in broken states."""
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                # 1. Reset jobs that were stuck while processing/generating back to 'scraped'
                cur.execute("""
                    UPDATE public.job_listings 
                    SET status = 'scraped' 
                    WHERE status IN ('generating', 'processing')
                    AND updated_at < NOW() - INTERVAL '1 hour'
                """)
                rowcount1 = cur.rowcount
                
                # 2. Reset failed scrapes back to 'new' if description is missing
                cur.execute("""
                    UPDATE public.job_listings 
                    SET status = 'new' 
                    WHERE status IN ('scraped', 'error') 
                    AND (description IS NULL OR LENGTH(description) < 50)
                """)
                rowcount2 = cur.rowcount
                
                if rowcount1 > 0 or rowcount2 > 0:
                    logging.info(f"Auto-recovered {rowcount1} stalled generations and {rowcount2} failed scrapes.")
            
            conn.commit()
            conn.close()
            return {"recovered_stalled": rowcount1, "recovered_failed": rowcount2}
        except Exception as e:
            logging.error(f"Could not run auto-recovery: {e}")
            return {"error": str(e)}
