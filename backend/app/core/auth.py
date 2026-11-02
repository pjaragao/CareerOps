"""Tokens for the routes that act on your behalf (X-CareerOps-Token). Three roles: the approver (you, in the app) decides
what goes out; the bot (Lolo, on WhatsApp) passes on your decisions and the e-mails, but never changes the mode, the account
or the limits; the worker (the server browser) only reports what it did, and can never approve anything. A role with no
token configured refuses every request, so forgetting the variable closes the route instead of opening it."""
import hmac
from typing import Optional

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings

APPROVER = "approver"
WORKER = "worker"
BOT = "bot"


def _expected(role: str) -> str:
    return {APPROVER: settings.CAREEROPS_APPROVER_TOKEN, WORKER: settings.CAREEROPS_WORKER_TOKEN,
            BOT: settings.CAREEROPS_BOT_TOKEN}.get(role, "")


def require(*roles: str):
    """Route dependency: the request must carry the token of one of these roles. Returns the role it matched."""
    def check(x_careerops_token: Optional[str] = Header(None)) -> str:
        for role in roles:
            expected = _expected(role)
            if expected and x_careerops_token and hmac.compare_digest(expected, x_careerops_token):
                return role
        raise HTTPException(status_code=401, detail="Token do CareerOps ausente ou inválido — confira em Configurações → Acesso")
    return check


require_approver = require(APPROVER)
# your decisions, from the app or from WhatsApp
require_decider = require(APPROVER, BOT)


# Routes a web page must not be able to reach from its own origin, whatever token it holds
PROTECTED_PREFIXES = ("/api/automation",)
PROTECTED_POST = ("/approve", "/publish")


def is_protected(path: str) -> bool:
    if path.startswith(PROTECTED_PREFIXES):
        return True
    return path.startswith("/api/linkedin-copilot/posts/") and path.endswith(PROTECTED_POST)


def origin_allowed(origin: Optional[str]) -> bool:
    """No Origin header (curl, the worker, the backend itself) or the app's own addresses or a browser extension."""
    if not origin or origin.startswith("chrome-extension://"):
        return True
    allowed = {o.strip().rstrip("/") for o in settings.CAREEROPS_ALLOWED_ORIGINS.split(",") if o.strip()}
    return origin.rstrip("/") in allowed | {settings.FRONTEND_URL.rstrip("/")}


async def origin_guard(request: Request, call_next):
    if is_protected(request.url.path) and not origin_allowed(request.headers.get("origin")):
        return JSONResponse({"detail": "Origem não permitida"}, status_code=403)
    return await call_next(request)
