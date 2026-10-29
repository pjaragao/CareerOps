import psycopg2
import os
from dotenv import load_dotenv

# Load .env from parent directory
load_dotenv()

def run_migration():
    password = os.getenv("SUPABASE_DB_PASSWORD")
    if not password:
        raise RuntimeError("SUPABASE_DB_PASSWORD environment variable must be set")
    conn = psycopg2.connect(
        host=os.getenv("SUPABASE_DB_HOST", "supabase-db"),
        port=os.getenv("SUPABASE_DB_PORT", "5432"),
        dbname=os.getenv("SUPABASE_DB_NAME", "postgres"),
        user=os.getenv("SUPABASE_DB_USER", "postgres"),
        password=password
    )
    
    try:
        with conn.cursor() as cur:
            migration_path = "/app/app/db/migrations/migrations_v5.sql"
            with open(migration_path, "r") as f:
                sql = f.read()
            
            print(f"Executing migration from {migration_path}...")
            cur.execute(sql)
            conn.commit()
            print("Migration V5 executed successfully.")
    except Exception as e:
        print(f"Error executing migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
