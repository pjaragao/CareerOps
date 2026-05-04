
import psycopg2
import os
from app.db.session import get_db_connection

def run_migration():
    migration_path = "app/db/migrations/migrations_v2.sql"
    if not os.path.exists(migration_path):
        # Try relative to backend root
        migration_path = "db/migrations/migrations_v2.sql"
        
    print(f"Running migration from {migration_path}...")
    
    with open(migration_path, "r") as f:
        sql = f.read()
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("Migration successful!")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
