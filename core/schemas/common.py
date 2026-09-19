"""Shared primitives used across every core/schemas contract.

Frozen v0 per docs/TrackB_Implementation_Plan.md T1.2. Only additive
changes after Track A sign-off.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SeverityBand = Literal["good", "satisfactory", "moderate", "poor", "very_poor", "severe"]
"""PRD severity bands, in order: Good 0-30, Satisfactory 31-60, Moderate 61-90,
Poor 91-120, Very poor 121-250 (alert threshold), Severe above 250 (ug/m3)."""

ZoneConfidence = Literal["high", "medium"]
"""2+ sensors within SENSOR_RADIUS_KM = high, 1 sensor = medium. 0 sensors excludes the zone."""

RouteConfidence = Literal["high", "low"]
"""Derived from route coverage %: below 80% coverage is low confidence."""

ReadingSource = Literal["sensor", "simulated", "model"]

MaskType = Literal["unmasked"]
"""MVP ships unmasked only; the field exists so mask differentiation is additive later."""


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    """Every non-2xx API response body shape (api/main.py exception handlers)."""

    error: ErrorDetail


_BAND_BOUNDARIES: list[tuple[float, SeverityBand]] = [
    (30, "good"),
    (60, "satisfactory"),
    (90, "moderate"),
    (120, "poor"),
    (250, "very_poor"),
]


def severity_band_for(pm25: float) -> SeverityBand:
    """PRD severity bands (display heuristics on 15-minute medians), inclusive upper bounds."""
    for upper, band in _BAND_BOUNDARIES:
        if pm25 <= upper:
            return band
    return "severe"
