
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# Add backend to path to use CompanyService
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from app.services.company_service import CompanyService
from app.db.session import get_db_connection

def repair_links():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Fetch all jobs without company_id
            cur.execute("SELECT id, company, url FROM public.job_listings WHERE company_id IS NULL")
            jobs = cur.fetchall()
            print(f"Found {len(jobs)} jobs to repair.")
            
            for job in jobs:
                # We try to find by name first
                name = job['company']
                url = job['url']
                
                print(f"Repairing job {job['id']}: {name}...")
                
                # Use the improved service logic
                company_id = CompanyService.get_or_create_company(name, url)
                
                cur.execute(
                    "UPDATE public.job_listings SET company_id = %s WHERE id = %s",
                    (company_id, job['id'])
                )
            
            conn.commit()
            print("Repair completed successfully.")
    except Exception as e:
        print(f"Error during repair: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    repair_links()
