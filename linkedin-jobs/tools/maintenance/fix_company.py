import db

def fix_company():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            # Find jobs where company got confused with the 'Verified' status
            cur.execute("SELECT id, company, location FROM public.job_listings WHERE company ILIKE 'Verificado' OR company ILIKE 'Verified'")
            jobs = cur.fetchall()
            
            for job_id, company, location in jobs:
                # the actual company name fell into the 'location' variable
                actual_company = location
                
                # We update the company to the actual company name and clear location.
                # The next time the saved job list is scraped, it will naturally update the location
                # to the correct value since it will re-process the list correctly.
                cur.execute(
                    "UPDATE public.job_listings SET company = %s, location = '' WHERE id = %s",
                    (actual_company, job_id)
                )
                
            conn.commit()
            print(f"Fixed {len(jobs)} jobs that were incorrectly saved with 'Verificado' as company.")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_company()
