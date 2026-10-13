from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth import (
    auth_enabled,
    clear_auth_cookie,
    is_authenticated,
    set_auth_cookie,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    if not auth_enabled():
        return {"status": "ok", "auth_required": False}

    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    set_auth_cookie(response)
    return {"status": "ok", "auth_required": True}


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"status": "ok"}


@router.get("/status")
async def auth_status(request: Request):
    return {
        "auth_required": auth_enabled(),
        "authenticated": is_authenticated(request),
    }
