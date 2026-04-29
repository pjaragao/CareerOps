import psycopg2
import psycopg2.extras
from app.core.config import settings

def get_db_connection():
    """Returns a new PostgreSQL connection."""
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )
    return conn

def get_db_cursor(conn):
    """Returns a RealDictCursor for the given connection."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
