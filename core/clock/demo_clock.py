"""One DemoClock node in Neo4j, read/written on every request. No background
ticking loop - state is derived from stored anchor/wall timestamps + wall-clock
now, so it survives a Render sleep/wake or a process restart untouched.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.clock.math import clamp_speed, clamp_to_bounds, derive_now
from core.db.client import get_session, to_utc
from core.schemas.demo import ClockActionRequest, ClockState

CLOCK_ID = "singleton"
DEFAULT_SPEED = 60
# 2021-01-27 14:00 IST: 172 of 195 zones reporting (overnight it drops to
# ~35) at a city mean of ~76 ug/m3 (Moderate). Coverage is high enough for
# real dose comparisons, and a demo spike visibly crosses the 120 threshold -
# on the worst days (Jan 14-15, ~300 mean) every zone is already Severe.
DEMO_START = datetime(2021, 1, 27, 8, 30, tzinfo=timezone.utc)


def _compute_bounds(session) -> tuple[datetime, datetime]:
    record = session.run(
        "MATCH (z:ZoneReading) RETURN min(z.ts) AS min_ts, max(z.ts) AS max_ts"
    ).single()
    return to_utc(record["min_ts"]), to_utc(record["max_ts"])


def _read_clock(session) -> dict | None:
    record = session.run("MATCH (c:DemoClock {id: $id}) RETURN c", id=CLOCK_ID).single()
    return dict(record["c"]) if record else None


def _create_clock(session) -> dict:
    min_ts, max_ts = _compute_bounds(session)
    wall_now = datetime.now(timezone.utc)
    record = session.run(
        """
        CREATE (c:DemoClock {
            id: $id, anchor_ts: $anchor_ts, wall_anchor: $wall_anchor,
            speed: $speed, running: $running, min_ts: $min_ts, max_ts: $max_ts
        })
        RETURN c
        """,
        id=CLOCK_ID,
        anchor_ts=clamp_to_bounds(DEMO_START, min_ts, max_ts),
        wall_anchor=wall_now,
        speed=DEFAULT_SPEED,
        running=True,
        min_ts=min_ts,
        max_ts=max_ts,
    ).single()
    return dict(record["c"])


def _state_from_row(clock: dict) -> ClockState:
    anchor_ts = to_utc(clock["anchor_ts"])
    wall_anchor = to_utc(clock["wall_anchor"])
    min_ts = to_utc(clock["min_ts"])
    max_ts = to_utc(clock["max_ts"])
    now_ts = derive_now(anchor_ts, clock["speed"], wall_anchor, datetime.now(timezone.utc), clock["running"])
    return ClockState(
        now_ts=now_ts,
        speed=clock["speed"],
        running=clock["running"],
        min_ts=min_ts,
        max_ts=max_ts,
    )


def get_state() -> ClockState:
    with get_session() as session:
        clock = _read_clock(session) or _create_clock(session)
    return _state_from_row(clock)


def apply_action(action: ClockActionRequest) -> ClockState:
    with get_session() as session:
        clock = _read_clock(session) or _create_clock(session)

        anchor_ts = to_utc(clock["anchor_ts"])
        wall_anchor = to_utc(clock["wall_anchor"])
        speed = clock["speed"]
        running = clock["running"]
        min_ts = to_utc(clock["min_ts"])
        max_ts = to_utc(clock["max_ts"])
        wall_now = datetime.now(timezone.utc)

        current_now = derive_now(anchor_ts, speed, wall_anchor, wall_now, running)

        if action.action == "pause":
            new_anchor, new_speed, new_running = current_now, speed, False
        elif action.action == "resume":
            new_anchor, new_speed, new_running = current_now, speed, True
        elif action.action == "set_speed":
            if action.speed is None:
                raise ValueError("speed is required for action=set_speed")
            new_anchor, new_speed, new_running = current_now, clamp_speed(action.speed), running
        elif action.action == "jump":
            if action.to is None:
                raise ValueError("to is required for action=jump")
            new_anchor = clamp_to_bounds(to_utc(action.to), min_ts, max_ts)
            new_speed, new_running = speed, running
        else:  # pragma: no cover - ClockActionType already restricts this
            raise ValueError(f"unknown action {action.action}")

        session.run(
            """
            MATCH (c:DemoClock {id: $id})
            SET c.anchor_ts = $anchor_ts, c.wall_anchor = $wall_anchor,
                c.speed = $speed, c.running = $running
            """,
            id=CLOCK_ID,
            anchor_ts=new_anchor,
            wall_anchor=wall_now,
            speed=new_speed,
            running=new_running,
        )

    return get_state()
