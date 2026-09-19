"""GET /api/zones contract. See docs/TrackB_Implementation_Plan.md Appendix A."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.schemas.common import SeverityBand, ZoneConfidence


class ZoneReadingOut(BaseModel):
    h3: str
    pm25: float = Field(ge=0)
    band: SeverityBand
    confidence: ZoneConfidence
    n_sensors: int = Field(ge=1)
    simulated: bool


class ZonesResponse(BaseModel):
    ts: datetime
    bucket: str
    """The 15-minute bucket the reading was aggregated into."""
    zones: list[ZoneReadingOut]
