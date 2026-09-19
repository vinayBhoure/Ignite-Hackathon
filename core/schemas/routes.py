"""POST /api/routes/plan contract. See docs/TrackB_Implementation_Plan.md Appendix A.

Decision rule (PRD domain facts, applied by core/dispatch, not here): get up to 3
alternatives, compute ETA/margin/dose/coverage, drop routes below the window buffer,
pick lowest dose (tie: shorter duration); if none qualifies, recommend the fastest
with window_at_risk=True.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.schemas.common import LatLng, MaskType, ReadingSource, RouteConfidence


class RoutePlanRequest(BaseModel):
    origin: LatLng
    destination: LatLng
    departure_ts: datetime
    window_end: datetime
    mask_type: MaskType = "unmasked"
    activity_factor: float = Field(default=1.0, gt=0.0)


class RouteZoneSegment(BaseModel):
    h3: str
    seconds: float = Field(ge=0)
    pm25: float = Field(ge=0)
    source: ReadingSource
    sensors: list[str] = Field(default_factory=list)


class RouteStep(BaseModel):
    """Turn-by-turn instruction from the Routes API (additive, post-v0)."""

    instruction: str
    maneuver: str
    distance_m: float = Field(ge=0)
    duration_s: float = Field(ge=0)
    lat: float
    lng: float


class RouteOption(BaseModel):
    id: str
    duration_s: float = Field(ge=0)
    distance_m: float = Field(ge=0)
    polyline: str
    eta: datetime
    window_margin_s: float
    """Signed: negative means the route misses the delivery window."""
    dose: float = Field(ge=0)
    """ug*h/m3, relative dose per domain facts (sum(C_zone(t) * dt_hours) * A * (1 - F_mask))."""
    coverage: float = Field(ge=0.0, le=1.0)
    confidence: RouteConfidence
    rank: int = Field(ge=1)
    selected: bool
    zones: list[RouteZoneSegment]
    steps: list[RouteStep] = Field(default_factory=list)
    label: str | None = None
    """"Fastest", "Lowest exposure", etc. - additive, post-v0."""


class RouteRecommendation(BaseModel):
    route_id: str
    dose_delta_pct: float
    """Delta vs the fastest route, always shown per PRD UI rules."""
    extra_minutes: float
    window_met: bool
    window_at_risk: bool


class RoutePlanResponse(BaseModel):
    routes: list[RouteOption]
    recommendation: RouteRecommendation
    explanation: str
    """One grounded sentence from Gemini (core/kg), never a source of truth for coordinates."""
