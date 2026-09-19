"""Static-credential auth for the hackathon demo (dispatcher + riders).

Framework-free so both the FastAPI service and the Streamlit console verify
the same signed session token. Credentials are fixed demo accounts, not a
user store - fine for a judged demo, never for production.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Literal

Role = Literal["dispatcher", "rider"]

SESSION_TTL_S = 12 * 60 * 60
_DEV_SECRET = "aevora-dev-secret-change-me"

DISPATCHERS: dict[str, dict[str, str]] = {
    "dispatch@aevora.in": {"password": "aevora-dispatch", "name": "Dispatch Desk"},
}

# Phone numbers map onto the riders already seeded in Neo4j (rider-1..rider-8).
RIDERS: dict[str, dict[str, str]] = {
    f"+9199000000{i:02d}": {"password": "aevora-rider", "rider_id": f"rider-{i}", "name": f"Rider {i}"}
    for i in range(1, 9)
}

logger = logging.getLogger("auth")


@dataclass(frozen=True)
class Session:
    role: Role
    sub: str
    name: str
    exp: int


def _secret() -> bytes:
    secret = os.getenv("SESSION_SECRET")
    if not secret:
        logger.warning("SESSION_SECRET not set - using the dev default; set it before deploying")
        secret = _DEV_SECRET
    return secret.encode()


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        digits = "91" + digits
    return "+" + digits


def authenticate(role: Role, identifier: str, password: str) -> Session | None:
    if role == "dispatcher":
        account = DISPATCHERS.get((identifier or "").strip().lower())
        if account and hmac.compare_digest(account["password"], password or ""):
            return _new_session("dispatcher", identifier.strip().lower(), account["name"])
        return None

    account = RIDERS.get(normalize_phone(identifier))
    if account and hmac.compare_digest(account["password"], password or ""):
        return _new_session("rider", account["rider_id"], account["name"])
    return None


def _new_session(role: Role, sub: str, name: str) -> Session:
    return Session(role=role, sub=sub, name=name, exp=int(time.time()) + SESSION_TTL_S)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_token(session: Session) -> str:
    payload = _b64(json.dumps(session.__dict__, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: str | None) -> Session | None:
    if not token or "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        data = json.loads(_unb64(payload))
        session = Session(**data)
    except (ValueError, TypeError):
        return None
    if session.exp < time.time() or session.role not in ("dispatcher", "rider"):
        return None
    return session
