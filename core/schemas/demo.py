"""POST /api/demo/clock and POST /api/demo/spike contracts.

See docs/TrackB_Implementation_Plan.md Appendix A and T1.6/T1.7. The clock is
derived, not ticked: now = anchor_ts + speed * (wall_now - wall_anchor), stored
in one DemoClock node (CLAUDE.md architecture rule 7).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ClockActionType = Literal["set_speed", "pause", "resume", "jump"]

MIN_SPEED = 1
MAX_SPEED = 600


class ClockActionRequest(BaseModel):
    action: ClockActionType
    speed: int | None = Field(default=None, gt=0)
    """Required for action='set_speed'. Clamped to [MIN_SPEED, MAX_SPEED] by
    core/clock, not rejected - out-of-range values are a plan-stated clamp,
    not a client error."""
    to: datetime | None = None
    """Required for action='jump'; clamped to [min_ts, max_ts] by core/clock."""


class ClockState(BaseModel):
    now_ts: datetime
    speed: int
    running: bool
    min_ts: datetime
    max_ts: datetime


class SpikeRequest(BaseModel):
    h3: str
    pm25: float = Field(gt=0)
    duration_min: int = Field(gt=0)


class SpikeResponse(BaseModel):
    spike_id: str
    buckets_written: int = Field(ge=0)
    source: Literal["simulated"] = "simulated"


class DemoResetResponse(BaseModel):
    spikes_cleared: int = Field(ge=0)
