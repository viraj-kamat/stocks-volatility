"""Cookie-based password authentication for StockSpikes."""
import hashlib
import hmac
import logging
import secrets
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

from app.config import settings

logger = logging.getLogger(__name__)

AUTH_COOKIE = "stockspikes_auth"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year — until cookies are cleared

PUBLIC_PATHS = {
    "/login",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/status",
}
PUBLIC_PREFIXES = ("/static",)


def auth_enabled() -> bool:
    return bool(settings.stockspikes_pwd)


def expected_session_token() -> str:
    """Stable session token derived from STOCKSPIKES_PWD."""
    pwd = settings.stockspikes_pwd
    if not pwd:
        return ""
    return hmac.new(
        pwd.encode("utf-8"),
        b"stockspikes-auth-v1",
        hashlib.sha256,
    ).hexdigest()


def verify_password(password: str) -> bool:
    configured = settings.stockspikes_pwd
    if not configured:
        return False
    return secrets.compare_digest(password, configured)


def is_authenticated(request: Request) -> bool:
    if not auth_enabled():
        return True
    token = request.cookies.get(AUTH_COOKIE)
    if not token:
        return False
    expected = expected_session_token()
    if not expected:
        return False
    return secrets.compare_digest(token, expected)


def set_auth_cookie(response: Response) -> None:
    response.set_cookie(
        key=AUTH_COOKIE,
        value=expected_session_token(),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=AUTH_COOKIE, path="/")


def _is_public(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path == prefix or path.startswith(prefix + "/") for prefix in PUBLIC_PREFIXES)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not auth_enabled():
            return await call_next(request)

        path = request.url.path
        if _is_public(path):
            return await call_next(request)

        if is_authenticated(request):
            return await call_next(request)

        accept = request.headers.get("accept", "")
        wants_html = "text/html" in accept or path == "/"
        if wants_html and not path.startswith("/api"):
            return RedirectResponse(url="/login", status_code=302)

        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
        )
