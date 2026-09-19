"""Auth contracts (additive to the v0 schemas)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    role: Literal["dispatcher", "rider"]
    identifier: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    role: Literal["dispatcher", "rider"]
    name: str
    redirect: str


class SessionInfo(BaseModel):
    role: Literal["dispatcher", "rider"]
    sub: str
    name: str
