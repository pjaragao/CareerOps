
import csv
import sys
import os
import psycopg2
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from app.db.session import get_db_connection
from app.services.company_service import CompanyService

def restore():
    # We need to read from the container or a copied file
    csv_path = 'scratch/exported_jobs.csv'
    if not os.path.exists(csv_path):
        print("CSV not found. Make sure to copy it from the container first.")
        return

    conn = get_db_connection()
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                # Extract data
                title = row.get('job_title')
                company_name = row.get('company')
                location = row.get('location')
                url = row.get('url')
                description = row.get('description')
                status = row.get('status', 'scraped')
                
                # Get or create company link
                company_id = CompanyService.get_or_create_company(company_name, url)
                
                # Synthetic linkedin_job_id if not present
                linkedin_id = row.get('linkedin_job_id')
                if not linkedin_id:
                    # Try to extract from URL
                    import re
                    match = re.search(r'/view/(\d+)', url)
                    linkedin_id = match.group(1) if match else f"restored_{count}"

                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.job_listings (job_title, company, location, url, description, status, company_id, linkedin_job_id, scraped_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (linkedin_job_id) DO NOTHING
                    """, (title, company_name, location, url, description, status, company_id, linkedin_id))
                count += 1
            conn.commit()
            print(f"Restored {count} jobs.")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    restore()
