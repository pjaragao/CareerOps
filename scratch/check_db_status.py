import sys
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

# Add backend to path
sys.path.append("/home/paulojr/linkedin_resume/backend")

from app.core.config import settings

def check_db():
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check documents
            cur.execute("SELECT id, filename, processing_status FROM public.user_documents")
            docs = cur.fetchall()
            print(f"Documents: {len(docs)}")
            for d in docs:
                print(f"  ID: {d['id']}, Name: {d['filename']}, Status: {d['processing_status']}")
            
            # Check interview stories
            cur.execute("SELECT count(*) FROM public.interview_stories")
            stories_count = cur.fetchone()['count']
            print(f"Interview Stories (STAR cases): {stories_count}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
