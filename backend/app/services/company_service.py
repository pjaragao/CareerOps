
from typing import List, Optional
import requests
from app.db.session import get_db_connection, get_db_cursor
from datetime import datetime, timezone
import re

class CompanyService:
    @staticmethod
    def get_companies(type: Optional[str] = None) -> List[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                query = """
                    SELECT c.*, COUNT(j.id) as job_count
                    FROM public.companies c
                    LEFT JOIN public.job_listings j ON c.id = j.company_id
                """
                params = []
                if type:
                    query += " WHERE c.company_type = %s"
                    params.append(type)
                
                query += " GROUP BY c.id ORDER BY c.name ASC"
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_company_by_id(company_id: int) -> Optional[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.companies WHERE id = %s", (company_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_or_create_company(name: str, url: Optional[str] = None, company_type: str = 'DIRECT_EMPLOYER') -> int:
        conn = get_db_connection()
        try:
            domain = CompanyService.extract_domain(url) if url else None
            with conn.cursor() as cur:
                # Try by name first
                cur.execute("SELECT id FROM public.companies WHERE name = %s", (name,))
                row = cur.fetchone()
                if row:
                    return row[0]
                
                # If url provided, try by domain
                if domain:
                    cur.execute("SELECT id FROM public.companies WHERE domain = %s", (domain,))
                    row = cur.fetchone()
                    if row:
                        return row[0]

                # Create new
                cur.execute("""
                    INSERT INTO public.companies (name, career_site_url, domain, company_type)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (name, url, domain, company_type))
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id
        finally:
            conn.close()

    @staticmethod
    def unshorten_url(url: str) -> str:
        if not url or 'lnkd.in' not in url:
            return url
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            # Use GET instead of HEAD for shorteners that might serve intermediate pages
            response = requests.get(url, allow_redirects=True, timeout=10, headers=headers)
            # Some shorteners use meta-refresh or JS, but lnkd.in usually works with redirects
            return response.url
        except Exception as e:
            print(f"Error unshortening {url}: {e}")
            return url

    @staticmethod
    def extract_domain(url: str) -> Optional[str]:
        if not url: return None
        # Ignore common shorteners and LinkedIn itself
        if any(shortener in url for shortener in ['lnkd.in', 'bit.ly', 't.co', 'tinyurl.com', 'linkedin.com']):
            return None
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        return match.group(1) if match else None

    @staticmethod
    def update_company(company_id: int, data: dict) -> bool:
        conn = get_db_connection()
        try:
            fields = []
            values = []
            for k, v in data.items():
                if k in ['name', 'career_site_url', 'description', 'logo_url', 'industry', 'tech_stack', 'remote_policy', 'domain', 'company_type']:
                    fields.append(f"{k} = %s")
                    values.append(v)
            
            if not fields: return False
            
            values.append(company_id)
            with conn.cursor() as cur:
                cur.execute(f"UPDATE public.companies SET {', '.join(fields)}, updated_at = NOW() WHERE id = %s", values)
            conn.commit()
            return True
        finally:
            conn.close()
