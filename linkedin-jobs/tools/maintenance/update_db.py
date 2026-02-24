import psycopg2
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def run_db_update():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE public.job_listings 
                ADD COLUMN IF NOT EXISTS company_description TEXT,
                ADD COLUMN IF NOT EXISTS company_profile_url TEXT,
                ADD COLUMN IF NOT EXISTS hiring_team_json TEXT;
            """)
        conn.commit()
        print("✅ Database updated with new columns.")
    except Exception as e:
        print(f"❌ Error updating database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_db_update()
