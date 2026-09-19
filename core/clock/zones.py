"""GET /api/zones (T1.7), real Neo4j read. ZoneReading nodes were already
scored by Track A's offline ETL (pm25 is a stored property, not computed
here) - this module only reads the right 15-minute bucket and prefers a
simulated spike over the sensor value for the same (h3, bucket).
"""

from __future__ import annotations

from datetime import datetime

from core.clock.demo_clock import get_state
from core.clock.math import floor_to_bucket
from core.db.client import get_session, to_data_tz
from core.schemas.common import severity_band_for
from core.schemas.zones import ZoneReadingOut, ZonesResponse

BUCKET_MINUTES = 15

_QUERY = """
MATCH (z:ZoneReading {ts: $bucket})
WITH z.h3 AS h3, z
ORDER BY h3, CASE z.source WHEN 'simulated' THEN 0 ELSE 1 END
WITH h3, collect(z)[0] AS chosen
RETURN chosen
"""


def get_zones(ts: datetime | None = None) -> ZonesResponse:
    ts = ts or get_state().now_ts
    bucket = floor_to_bucket(ts, BUCKET_MINUTES)

    with get_session() as session:
        rows = session.run(_QUERY, bucket=to_data_tz(bucket))
        zones = [_to_zone_reading(row["chosen"]) for row in rows]

    return ZonesResponse(ts=ts, bucket=f"{bucket.isoformat()}/15m", zones=zones)


def _to_zone_reading(z) -> ZoneReadingOut:
    pm25 = z["pm25"]
    confidence = str(z.get("confidence", "Medium")).lower()
    if confidence not in ("high", "medium"):
        confidence = "high" if z.get("n_sensors", 1) >= 2 else "medium"
    return ZoneReadingOut(
        h3=z["h3"],
        pm25=pm25,
        band=severity_band_for(pm25),
        confidence=confidence,
        n_sensors=max(int(z.get("n_sensors", 1)), 1),
        simulated=(z["source"] == "simulated"),
    )
