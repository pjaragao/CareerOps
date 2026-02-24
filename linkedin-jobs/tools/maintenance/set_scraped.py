import db

conn = db.get_connection()
try:
    with conn.cursor() as cur:
        # Change status of all available jobs (done or error) to scraped so they can be generated again.
        cur.execute("UPDATE public.job_listings SET status = 'scraped' WHERE status IN ('done', 'error')")
        print(f"✅ Reset {cur.rowcount} jobs back to 'scraped' status so you can generate resumes for them again.")
    conn.commit()
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
