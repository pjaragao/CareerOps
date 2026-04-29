from fastapi import APIRouter
from app.services.auth_service import AuthService

router = APIRouter()

@router.post("/login")
async def start_login():
    try:
        return await AuthService.start_login()
    except Exception as e:
        import traceback
        print(f"DEBUG: Login Error Traceback:\n{traceback.format_exc()}")
        return {"error": f"Backend Exception: {str(e)}"}

@router.post("/finish-login")
async def finish_login():
    return await AuthService.finish_login()

@router.post("/session-upload")
async def upload_session(data: dict):
    return await AuthService.upload_session(data)

@router.get("/status")
async def get_status():
    return await AuthService.get_session_status()
