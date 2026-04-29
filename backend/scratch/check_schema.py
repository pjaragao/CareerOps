from app.db.session import get_db_connection, get_db_cursor
import json

def check_schema():
    conn = get_db_connection()
    tables = ['job_listings', 'pipeline_urls', 'search_strategies', 'star_stories', 'profiles']
    schema = {}
    try:
        with get_db_cursor(conn) as cur:
            for table in tables:
                cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'")
                schema[table] = [dict(row) for row in cur.fetchall()]
        print(json.dumps(schema, indent=2))
    finally:
        conn.close()

if __name__ == "__main__":
    check_schema()
