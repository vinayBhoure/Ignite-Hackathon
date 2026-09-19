"""Pure replay-clock math, no Neo4j - CLAUDE.md architecture rule 7: the clock is
derived, not ticked: now = anchor_ts + speed * (wall_now - wall_anchor).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from core.schemas.demo import MAX_SPEED, MIN_SPEED


def derive_now(
    anchor_ts: datetime,
    speed: float,
    wall_anchor: datetime,
    wall_now: datetime,
    running: bool,
) -> datetime:
    """Recomputed on every read - this is what makes the clock survive a restart
    or a Render sleep/wake with no background ticking process."""
    if not running:
        return anchor_ts
    elapsed_s = (wall_now - wall_anchor).total_seconds()
    return anchor_ts + timedelta(seconds=speed * elapsed_s)


def clamp_speed(speed: int) -> int:
    return max(MIN_SPEED, min(MAX_SPEED, speed))


def clamp_to_bounds(ts: datetime, min_ts: datetime, max_ts: datetime) -> datetime:
    return max(min_ts, min(max_ts, ts))


def floor_to_bucket(ts: datetime, bucket_minutes: int = 15) -> datetime:
    """ZoneReading rows are keyed by 15-minute bucket, per CLAUDE.md domain facts."""
    minute = (ts.minute // bucket_minutes) * bucket_minutes
    return ts.replace(minute=minute, second=0, microsecond=0)
