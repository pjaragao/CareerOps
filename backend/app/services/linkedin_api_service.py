"""Official LinkedIn API: OAuth 2.0 (OpenID Connect) and member posts.

Only what LinkedIn's self-serve products allow for a personal profile:
- "Sign In with LinkedIn using OpenID Connect" → scopes openid, profile (who is connected)
- "Share on LinkedIn" → scope w_member_social (create posts as the member)
No reading of feeds, no likes, comments, follows or invitations — those stay manual.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import requests

from app.core.config import settings
from app.db.session import get_db_connection, get_db_cursor

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/rest/posts"
SCOPES = "openid profile w_member_social"
STATE_TTL = timedelta(minutes=15)


class LinkedInApiError(Exception):
    pass


def _api_version() -> str:
    if settings.LINKEDIN_API_VERSION:
        return settings.LINKEDIN_API_VERSION
    first_of_month = datetime.now(timezone.utc).replace(day=1)
    previous = first_of_month - timedelta(days=1)
    return previous.strftime("%Y%m")


class LinkedInApiService:
    @staticmethod
    def is_configured() -> bool:
        return bool(settings.LINKEDIN_CLIENT_ID and settings.LINKEDIN_CLIENT_SECRET)

    @staticmethod
    def authorization_url() -> str:
        if not LinkedInApiService.is_configured():
            raise LinkedInApiError("LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET are not set")
        state = secrets.token_urlsafe(24)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.linkedin_oauth_states WHERE created_at < NOW() - INTERVAL '1 day'")
                cur.execute("INSERT INTO public.linkedin_oauth_states (state) VALUES (%s)", (state,))
            conn.commit()
        finally:
            conn.close()
        return AUTH_URL + "?" + urlencode({
            "response_type": "code",
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "state": state,
            "scope": SCOPES,
        })

    @staticmethod
    def _consume_state(state: str) -> bool:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("DELETE FROM public.linkedin_oauth_states WHERE state = %s RETURNING created_at", (state,))
                row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()
        return bool(row) and datetime.now(timezone.utc) - row["created_at"] <= STATE_TTL

    @staticmethod
    def handle_callback(code: str, state: str) -> dict:
        if not LinkedInApiService._consume_state(state):
            raise LinkedInApiError("Invalid or expired OAuth state — start the connection again")
        r = requests.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        }, timeout=30)
        if r.status_code != 200:
            raise LinkedInApiError(f"Token exchange failed ({r.status_code}): {r.text[:300]}")
        token = r.json()
        access_token = token["access_token"]
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in", 0)))

        u = requests.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
        if u.status_code != 200:
            raise LinkedInApiError(f"Could not read the member profile ({u.status_code}): {u.text[:300]}")
        info = u.json()
        member_urn = f"urn:li:person:{info['sub']}"
        name = info.get("name") or " ".join(filter(None, [info.get("given_name"), info.get("family_name")]))

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.linkedin_auth (id, access_token, expires_at, member_urn, member_name, scope, updated_at)
                    VALUES (1, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET access_token = EXCLUDED.access_token, expires_at = EXCLUDED.expires_at,
                        member_urn = EXCLUDED.member_urn, member_name = EXCLUDED.member_name, scope = EXCLUDED.scope,
                        updated_at = NOW()
                """, (access_token, expires_at, member_urn, name, token.get("scope", SCOPES)))
            conn.commit()
        finally:
            conn.close()
        return {"member_name": name, "expires_at": expires_at.isoformat()}

    @staticmethod
    def _auth() -> Optional[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.linkedin_auth WHERE id = 1")
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def status() -> dict:
        auth = LinkedInApiService._auth()
        connected = bool(auth) and auth["expires_at"] > datetime.now(timezone.utc)
        return {
            "configured": LinkedInApiService.is_configured(),
            "connected": connected,
            "member_name": auth["member_name"] if auth else None,
            "expires_at": auth["expires_at"].isoformat() if auth else None,
            "api_version": _api_version(),
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,   # shown in the app's setup guide
        }

    @staticmethod
    def disconnect() -> None:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.linkedin_auth WHERE id = 1")
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def publish_text(text: str) -> str:
        """Publishes a public text post as the connected member. Returns the post URN."""
        auth = LinkedInApiService._auth()
        if not auth or auth["expires_at"] <= datetime.now(timezone.utc):
            raise LinkedInApiError("LinkedIn is not connected (or the token expired) — connect again")
        r = requests.post(POSTS_URL, json={
            "author": auth["member_urn"],
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }, headers={
            "Authorization": f"Bearer {auth['access_token']}",
            "LinkedIn-Version": _api_version(),
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }, timeout=30)
        if r.status_code not in (200, 201):
            raise LinkedInApiError(f"Publish failed ({r.status_code}): {r.text[:300]}")
        return r.headers.get("x-restli-id", "")
