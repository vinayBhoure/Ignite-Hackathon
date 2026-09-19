"""Spike injector (E3 Clock and spikes, T1.7). Writes ZoneReading nodes with
source='simulated' for the replay window starting at the clock's current
now, one per 15-minute bucket for duration_min. Per the plan's Q3 resolution:
simulated readings override the sensor value for the same (h3, bucket) at
read time (core/clock/zones.py) rather than being summed with it.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from core.clock.demo_clock import get_state
from core.clock.math import floor_to_bucket
from core.db.client import get_session, to_data_tz
from core.schemas.demo import DemoResetResponse, SpikeRequest, SpikeResponse

BUCKET_MINUTES = 15


def inject_spike(req: SpikeRequest) -> SpikeResponse:
    now = get_state().now_ts
    start = floor_to_bucket(now, BUCKET_MINUTES)
    n_buckets = max(1, -(-req.duration_min // BUCKET_MINUTES))
    spike_id = uuid.uuid4().hex[:12]

    with get_session() as session:
        for i in range(n_buckets):
            bucket_ts = start + timedelta(minutes=BUCKET_MINUTES * i)
            session.run(
                """
                CREATE (z:ZoneReading {
                    h3: $h3, ts: $ts, pm25: $pm25, source: 'simulated',
                    confidence: 'High', n_sensors: 1, spike_id: $spike_id
                })
                """,
                h3=req.h3,
                ts=to_data_tz(bucket_ts),
                pm25=req.pm25,
                spike_id=spike_id,
            )

    return SpikeResponse(spike_id=spike_id, buckets_written=n_buckets, source="simulated")


def reset_spikes() -> DemoResetResponse:
    with get_session() as session:
        count = session.run(
            "MATCH (z:ZoneReading {source: 'simulated'}) RETURN count(z) AS c"
        ).single()["c"]
        session.run("MATCH (z:ZoneReading {source: 'simulated'}) DETACH DELETE z")

    return DemoResetResponse(spikes_cleared=count)
