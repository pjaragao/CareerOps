
import psycopg2
from app.db.session import get_db_connection

def check_schema():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'job_listings'")
            rows = cur.fetchall()
            for row in rows:
                print(row)
    finally:
        conn.close()

if __name__ == "__main__":
    check_schema()
