"""Live navigation + fleet contracts (additive, post-v0)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from core.schemas.alerts import AlertOut
from core.schemas.common import LatLng, SeverityBand
from core.schemas.routes import RouteStep


class NavZone(BaseModel):
    h3: str
    lat: float
    lng: float
    bucket: datetime
    reach_ts: datetime | None = None
    """When the rider enters the zone (replay time) - finer than the bucket."""
    pm25: float | None = None
    band: SeverityBand | None = None
    simulated: bool = False
    estimated: bool = False
    """True when filled from the city-wide mean for the bucket, not a zone reading."""
    ahead: bool = True


class NavigationState(BaseModel):
    order_id: str
    rider_id: str
    rider_name: str
    pickup_name: str
    drop_name: str
    status: Literal["en_route", "arrived"]
    route_id: str
    route_label: str | None = None
    polyline: str
    steps: list[RouteStep]
    position: LatLng
    progress: float = Field(ge=0, le=1)
    current_step: int
    distance_remaining_m: float
    minutes_remaining: float
    eta: datetime
    window_end: datetime
    window_margin_min: float
    dose_total: float
    dose_so_far: float
    coverage: float
    confidence: Literal["high", "low"]
    zones: list[NavZone]
    next_bad_zone: NavZone | None = None
    alerts: list[AlertOut] = Field(default_factory=list)
    replay_now: datetime
    clock_running: bool
    clock_speed: int


class RerouteOption(BaseModel):
    route_id: str
    polyline: str
    minutes: float
    dose: float
    coverage: float


class ReroutePreview(BaseModel):
    order_id: str
    current_minutes: float
    current_dose: float
    best: RerouteOption | None
    extra_minutes: float = 0.0
    dose_saved_pct: float = 0.0
    recommend_switch: bool
    message: str


class RerouteCommit(BaseModel):
    route_id: str


class RiderSummary(BaseModel):
    id: str
    name: str
    status: str
    activity_factor: float = 1.0
    order_id: str | None = None


class AssignmentSummary(BaseModel):
    order_id: str
    rider_id: str
    rider_name: str
    pickup_name: str
    drop_name: str
    route_id: str
    route_label: str | None = None
    duration_min: float
    dose: float
    coverage: float
    progress: float
    eta: datetime
    status: str
    new_alerts: int = 0


class RouteZoneAhead(BaseModel):
    h3: str
    bucket: datetime
    minutes_ahead: float
    pm25: float | None = None
    avoidable: bool = False
    """No alternative route for this order passes through the zone, so a
    spike here can actually be routed around."""
