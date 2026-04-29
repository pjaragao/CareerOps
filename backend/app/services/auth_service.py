import asyncio
from playwright.async_api import async_playwright
from app.core.config import settings

class AuthService:
    _login_browser = None
    _login_context = None
    _login_pw = None

    @staticmethod
    async def start_login():
        """Opens a headed browser for the user to log in manually."""
        import os
        # Robust display check
        display = os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')
        if os.name == 'posix' and not display:
            return {
                "error": "No display access (DISPLAY/WAYLAND_DISPLAY not set). If you are on a remote server/Docker, please use 'Manual Session Import' below.",
                "type": "DISPLAY_ERROR"
            }

        try:
            p = await async_playwright().start()
            AuthService._login_pw = p
            
            try:
                # Launch headed so user can interact
                browser = await p.chromium.launch(headless=False)
            except Exception as launch_err:
                await p.stop()
                AuthService._login_pw = None
                return {
                    "error": f"Could not launch browser with display: {str(launch_err)}. This usually means the server has no graphical interface (X11).",
                    "type": "LAUNCH_ERROR"
                }
            
            context = await browser.new_context()
            page = await context.new_page()
            
            await page.goto("https://www.linkedin.com/login")
            
            # Store globally to close later
            AuthService._login_browser = browser
            AuthService._login_context = context
            return {"message": "Browser opened for login. Please complete login and click Finish."}
        except Exception as e:
            if AuthService._login_pw:
                await AuthService._login_pw.stop()
                AuthService._login_pw = None
            return {"error": f"Failed to start Playwright: {str(e)}"}

    @staticmethod
    async def upload_session(data: dict):
        """Saves a storage state JSON provided by the user."""
        try:
            import json
            settings.AUTH_DIR.mkdir(parents=True, exist_ok=True)
            if "userAgent" in data:
                ua = data.pop("userAgent")
                ua_file = settings.AUTH_DIR / "user_agent.txt"
                with open(ua_file, "w") as f:
                    f.write(ua)
            
            with open(settings.SESSION_FILE, "w") as f:
                json.dump(data, f)
            return {"message": "Session and identity synced successfully!"}
        except Exception as e:
            return {"error": f"Failed to save session: {str(e)}"}

    @staticmethod
    async def finish_login():
        """Saves the current storage state and closes the browser."""
        if not AuthService._login_context:
            return {"error": "No active login session found."}
        
        await AuthService._login_context.storage_state(path=str(settings.SESSION_FILE))
        await AuthService._login_browser.close()
        if AuthService._login_pw:
            await AuthService._login_pw.stop()
        
        AuthService._login_browser = None
        AuthService._login_context = None
        AuthService._login_pw = None
        return {"message": "Session saved successfully!"}

    @staticmethod
    async def get_session_status():
        if settings.SESSION_FILE.exists() and settings.SESSION_FILE.stat().st_size > 100:
            return {"active": True, "last_updated": settings.SESSION_FILE.stat().st_mtime}
        return {"active": False}
