"""Dose scoring for a real route polyline against the replayed zone layer.

Dose (CLAUDE.md domain facts): sum(C_zone(t_arrival) * dt_hours) * A * (1 - F_mask),
using PM2.5 concentration (not AQI). Time in each H3 zone is the route's
traffic-aware duration split by distance; arrival time picks the 15-minute
bucket. A simulated spike overrides the sensor value for the same
(h3, bucket), never sums with it.

Gaps: a zone with no reading at its bucket is filled with the city-wide mean
of sensor readings in that same bucket (source="model"). Counting gaps as 0
would make the route with the *least data* look cleanest. Coverage still
reports only the sensor/simulated share, so low-confidence flags stay honest.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

import h3

from core.clock.math import floor_to_bucket
from core.db.client import get_session, to_data_tz
from core.navigation.geometry import LatLngT, haversine_m
from core.schemas.routes import RouteZoneSegment

H3_RES = 8
_MAX_PIECE_M = 100.0  # res-8 cells are ~460 m across; 100 m pieces don't skip cells
MEASURED = ("sensor", "simulated")

# Sensor readings are replayed history and never change, so the city mean
# per bucket is safe to memoize for the life of the process.
_bucket_means: dict[str, float | None] = {}
_means_lock = threading.Lock()


@dataclass
class ZoneSegment:
    idx: int
    h3: str
    distance_m: float
    seconds: float
    enter_ts: datetime
    bucket: datetime
    pm25: float | None = None
    source: str | None = None


@dataclass
class ScoredRoute:
    segments: list[ZoneSegment]
    dose: float
    coverage: float

    @property
    def zones(self) -> list[RouteZoneSegment]:
        return [
            RouteZoneSegment(h3=s.h3, seconds=s.seconds, pm25=round(s.pm25, 1), source=s.source)
            for s in self.segments
            if s.pm25 is not None
        ]


def segment_route(points: list[LatLngT], duration_s: float, departure: datetime) -> list[ZoneSegment]:
    pieces: list[tuple[str, float]] = []
    for a, b in zip(points, points[1:]):
        length = haversine_m(a, b)
        if length == 0:
            continue
        n = max(1, int(length // _MAX_PIECE_M) + 1)
        for k in range(n):
            t = (k + 0.5) / n
            mid = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            pieces.append((h3.latlng_to_cell(mid[0], mid[1], H3_RES), length / n))

    total = sum(d for _, d in pieces) or 1.0
    merged: list[list] = []
    for cell, dist in pieces:
        if merged and merged[-1][0] == cell:
            merged[-1][1] += dist
        else:
            merged.append([cell, dist])

    segments: list[ZoneSegment] = []
    elapsed = 0.0
    for idx, (cell, dist) in enumerate(merged):
        seconds = duration_s * dist / total
        enter = departure + timedelta(seconds=elapsed)
        mid_time = enter + timedelta(seconds=seconds / 2)
        segments.append(
            ZoneSegment(
                idx=idx,
                h3=cell,
                distance_m=dist,
                seconds=seconds,
                enter_ts=enter,
                bucket=floor_to_bucket(mid_time),
            )
        )
        elapsed += seconds
    return segments


def attach_readings(segments: list[ZoneSegment]) -> None:
    """One round trip for all (h3, bucket) pairs; simulated beats sensor."""
    if not segments:
        return
    pairs = [
        {"h3": s.h3, "bucket": to_data_tz(s.bucket), "key": f"{s.h3}|{s.bucket.isoformat()}"} for s in segments
    ]
    readings: dict[str, tuple[float, str]] = {}
    with get_session() as session:
        rows = session.run(
            """
            UNWIND $pairs AS p
            MATCH (zr:ZoneReading {h3: p.h3, ts: p.bucket})
            RETURN p.key AS key, zr.pm25 AS pm25, zr.source AS source
            ORDER BY CASE zr.source WHEN 'simulated' THEN 0 ELSE 1 END
            """,
            pairs=pairs,
        )
        for row in rows:
            readings.setdefault(row["key"], (float(row["pm25"]), row["source"] or "sensor"))

    for s in segments:
        hit = readings.get(f"{s.h3}|{s.bucket.isoformat()}")
        if hit:
            s.pm25, s.source = hit
            if s.source not in MEASURED:
                s.source = "sensor"

    gaps = [s for s in segments if s.pm25 is None]
    if gaps:
        means = _city_means({s.bucket for s in gaps})
        for s in gaps:
            mean = means.get(s.bucket.isoformat())
            if mean is not None:
                s.pm25, s.source = mean, "model"


def _city_means(buckets: set[datetime]) -> dict[str, float | None]:
    keys = {b.isoformat(): b for b in buckets}
    with _means_lock:
        missing = [b for k, b in keys.items() if k not in _bucket_means]
    if missing:
        with get_session() as session:
            rows = session.run(
                """
                UNWIND $buckets AS b
                OPTIONAL MATCH (zr:ZoneReading {ts: b.ts, source: 'sensor'})
                RETURN b.key AS key, avg(zr.pm25) AS mean
                """,
                buckets=[{"ts": to_data_tz(b), "key": b.isoformat()} for b in missing],
            )
            fetched = {row["key"]: row["mean"] for row in rows}
        with _means_lock:
            _bucket_means.update(fetched)
    with _means_lock:
        return {k: _bucket_means.get(k) for k in keys}


def score_route(
    points: list[LatLngT],
    duration_s: float,
    departure: datetime,
    activity_factor: float = 1.0,
    mask_filtration: float = 0.0,
) -> ScoredRoute:
    segments = segment_route(points, duration_s, departure)
    attach_readings(segments)
    base = sum(s.pm25 * s.seconds / 3600 for s in segments if s.pm25 is not None)
    total_s = sum(s.seconds for s in segments) or 1.0
    return ScoredRoute(
        segments=segments,
        dose=base * activity_factor * (1 - mask_filtration),
        coverage=sum(s.seconds for s in segments if s.source in MEASURED) / total_s,
    )
