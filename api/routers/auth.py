"""Aevora sign-in: the login page at "/", plus login/logout/me endpoints.

Riders land on /rider (same origin, cookie). Dispatchers are handed to the
Streamlit console with the signed token in the URL once - the console runs on
a different origin (port locally, subdomain on Render), so a cookie alone
can't carry the session across.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from api.config import Settings, get_settings
from api.security import COOKIE_NAMES, cookie_name, current_session, require_session
from core.auth import SESSION_TTL_S, Session, authenticate, issue_token
from core.schemas.auth import LoginRequest, LoginResponse, SessionInfo

router = APIRouter(tags=["auth"])

LOGIN_PAGE = (Path(__file__).resolve().parent.parent / "templates" / "login.html").read_text(encoding="utf-8")


def home_url(session: Session, settings: Settings) -> str:
    if session.role == "rider":
        return "/rider"
    return f"{settings.console_url}/?{urlencode({'token': issue_token(session)})}"


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request, settings: Settings = Depends(get_settings)):
    # Already signed in for the requested role (dispatcher unless ?role=rider)
    # -> straight to that home; ?switch shows the form regardless.
    wanted = "rider" if request.query_params.get("role") == "rider" else "dispatcher"
    session = current_session(request, wanted)
    if session is not None and request.query_params.get("switch") is None:
        return RedirectResponse(home_url(session, settings), status_code=303)
    return HTMLResponse(LOGIN_PAGE)


@router.post("/api/auth/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request, settings: Settings = Depends(get_settings)):
    session = authenticate(req.role, req.identifier, req.password)
    if session is None:
        raise HTTPException(status_code=401, detail="Those credentials don't match a demo account.")

    body = LoginResponse(role=session.role, name=session.name, redirect=home_url(session, settings))
    response = JSONResponse(body.model_dump())
    response.set_cookie(
        cookie_name(session.role),
        issue_token(session),
        max_age=SESSION_TTL_S,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    return response


@router.get("/logout", include_in_schema=False)
def logout(request: Request) -> RedirectResponse:
    """?role=rider|dispatcher signs out just that role; no role signs out both."""
    role = request.query_params.get("role")
    roles = [role] if role in COOKIE_NAMES else list(COOKIE_NAMES)
    response = RedirectResponse("/?role=rider" if role == "rider" else "/", status_code=303)
    for r in roles:
        response.delete_cookie(COOKIE_NAMES[r])
    return response


@router.get("/api/auth/me", response_model=SessionInfo)
def me(session: Session = Depends(require_session)) -> SessionInfo:
    return SessionInfo(role=session.role, sub=session.sub, name=session.name)
