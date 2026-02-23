import db
import re

def clean_description(desc: str) -> str:
    if not desc:
        return desc
    
    # Common cutoffs
    cutoffs = [
        r"… more\s+Set alert for similar jobs",
        r"… ver mais\s+Criar alerta para vagas semelhantes",
        r"… show more\s+Set alert for similar jobs"
    ]
    
    for pattern in cutoffs:
        match = re.search(pattern, desc)
        if match:
            desc = desc[:match.start()].strip()
            break
            
    return desc

def main():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, description FROM public.job_listings WHERE description IS NOT NULL")
            jobs = cur.fetchall()
            
            updated_count = 0
            for job_id, desc in jobs:
                cleaned = clean_description(desc)
                if cleaned != desc:
                    cur.execute(
                        "UPDATE public.job_listings SET description = %s WHERE id = %s",
                        (cleaned, job_id)
                    )
                    updated_count += 1
            
            conn.commit()
            print(f"Updated {updated_count} job descriptions.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
