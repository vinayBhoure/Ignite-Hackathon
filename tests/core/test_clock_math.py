"""T1.6 unit tests: clock math (derive, clamp, jump), no Neo4j involved."""

from datetime import datetime, timedelta, timezone

from core.clock.math import clamp_speed, clamp_to_bounds, derive_now


def test_derive_now_advances_by_speed_multiple():
    anchor = datetime(2020, 11, 1, tzinfo=timezone.utc)
    wall_anchor = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    wall_now = wall_anchor + timedelta(seconds=10)
    now = derive_now(anchor, speed=60, wall_anchor=wall_anchor, wall_now=wall_now, running=True)
    assert now == anchor + timedelta(seconds=600)


def test_derive_now_frozen_when_not_running():
    anchor = datetime(2020, 11, 1, tzinfo=timezone.utc)
    wall_anchor = datetime(2026, 1, 1, tzinfo=timezone.utc)
    wall_now = wall_anchor + timedelta(hours=5)
    now = derive_now(anchor, speed=600, wall_anchor=wall_anchor, wall_now=wall_now, running=False)
    assert now == anchor


def test_derive_now_survives_a_simulated_restart():
    """Recomputing later from the same stored anchor/wall values gives a
    consistent later `now`, exactly what a process restart or Render
    sleep/wake needs (no in-memory ticking state to lose)."""
    anchor = datetime(2020, 11, 1, tzinfo=timezone.utc)
    wall_anchor = datetime(2026, 1, 1, tzinfo=timezone.utc)

    now_1 = derive_now(anchor, 60, wall_anchor, wall_anchor + timedelta(seconds=5), True)
    # "restart": nothing but wall-clock time has moved on; anchor/wall_anchor unchanged
    now_2 = derive_now(anchor, 60, wall_anchor, wall_anchor + timedelta(seconds=15), True)
    assert now_2 > now_1
    assert now_2 - now_1 == timedelta(seconds=600)


def test_clamp_speed_bounds():
    assert clamp_speed(0) == 1
    assert clamp_speed(1) == 1
    assert clamp_speed(600) == 600
    assert clamp_speed(9999) == 600


def test_clamp_to_bounds():
    min_ts = datetime(2020, 11, 1, tzinfo=timezone.utc)
    max_ts = datetime(2020, 11, 30, tzinfo=timezone.utc)
    assert clamp_to_bounds(datetime(2020, 10, 1, tzinfo=timezone.utc), min_ts, max_ts) == min_ts
    assert clamp_to_bounds(datetime(2020, 12, 1, tzinfo=timezone.utc), min_ts, max_ts) == max_ts
    mid = datetime(2020, 11, 15, tzinfo=timezone.utc)
    assert clamp_to_bounds(mid, min_ts, max_ts) == mid
