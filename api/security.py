"""Request-level auth for the FastAPI service: reads the signed session
cookies set by the Aevora login page (core/auth.py does the crypto).

One cookie per role, so a dispatcher and a rider can be signed in side by
side in the same browser - the demo runs both on one laptop.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from core.auth import Role, Session, verify_token

COOKIE_NAMES: dict[str, str] = {"dispatcher": "aevora_dispatcher", "rider": "aevora_rider"}


def cookie_name(role: Role) -> str:
    return COOKIE_NAMES[role]


def _from_cookie(request: Request, role: Role) -> Session | None:
    session = verify_token(request.cookies.get(COOKIE_NAMES[role]))
    return session if session and session.role == role else None


def current_session(request: Request, role: Role | None = None) -> Session | None:
    # Bearer for the console's map iframe, which runs on another origin.
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        session = verify_token(auth[7:].strip())
        return session if session and (role is None or session.role == role) else None
    if role is not None:
        return _from_cookie(request, role)
    # Role-agnostic endpoints (alerts, clock) are only called by the rider app
    # over REST - the console reads core directly - so the rider view wins.
    return _from_cookie(request, "rider") or _from_cookie(request, "dispatcher")


def require_session(request: Request) -> Session:
    session = current_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Sign in required")
    return session


def _require(request: Request, role: Role) -> Session:
    session = current_session(request, role)
    if session is None:
        other = current_session(request)
        if other is not None:
            raise HTTPException(status_code=403, detail=f"{role.title()} access only")
        raise HTTPException(status_code=401, detail="Sign in required")
    return session


def require_dispatcher(request: Request) -> Session:
    return _require(request, "dispatcher")


def require_rider(request: Request) -> Session:
    return _require(request, "rider")
