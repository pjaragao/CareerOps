
import csv
import os
import sys
from pathlib import Path
import psycopg2
import psycopg2.extras
import google.generativeai as genai
from dotenv import load_dotenv

# Project root
PROJECT_DIR = Path("/app") if Path("/app").exists() else Path(__file__).parent.resolve()

# Load config from .env
load_dotenv(PROJECT_DIR / ".env")

# DB Settings
# If running inside Docker, SUPABASE_DB_HOST should be 'supabase-db'
# If running outside, it might be 'localhost'
DB_HOST = os.getenv("SUPABASE_DB_HOST", "localhost")
DB_PORT = int(os.getenv("SUPABASE_DB_PORT", "5432"))
DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")
DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Special case for running on host but needing to access mapped docker port
# If we are NOT in docker and host is 'supabase-db', it probably won't resolve.
# But if the user says it's running 'under supabase', they might have host entries.
# I'll stick to the env vars for now.

def get_connection():
    print(f"Connecting to {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}...")
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

def summarize_description(description):
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY not found, skipping summarization.")
        return description[:10000] + "... (truncated due to length and no API key)"
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = (
        "Resuma a seguinte descrição de vaga de emprego, focando nos requisitos principais e responsabilidades. "
        "Mantenha o resumo conciso e em português.\n\n"
        f"Descrição:\n{description}"
    )
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error summarizing with Gemini: {e}")
        return description[:50000] + "... (truncated due to error during summarization)"

def export_to_csv():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Fetch all job listings that are not 'removed'
            cur.execute("SELECT * FROM public.job_listings WHERE status != 'removed' ORDER BY created_at DESC")
            jobs = cur.fetchall()
            
        if not jobs:
            print("No jobs found to export.")
            return

        output_file = PROJECT_DIR / "output" / "exported_jobs.csv"
        # Ensure output dir exists
        (PROJECT_DIR / "output").mkdir(parents=True, exist_ok=True)
        
        TOKEN_THRESHOLD_CHARS = 700000
        
        fieldnames = [
            'id', 'job_title', 'company', 'location', 'status', 'url', 
            'description', 'easy_apply', 'scraped_at', 'created_at'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for job in jobs:
                desc = job.get('description') or ""
                if len(desc) > TOKEN_THRESHOLD_CHARS:
                    print(f"Job ID {job['id']} has a very long description ({len(desc)} chars). Summarizing...")
                    job['description'] = summarize_description(desc)
                
                writer.writerow(job)
                
        print(f"✅ Successfully exported {len(jobs)} jobs to {output_file}")
        return output_file

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    export_to_csv()
