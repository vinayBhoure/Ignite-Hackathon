"""Mock GET /api/zones. Fixed Delhi NCR zone set spanning every severity band,
one flagged simulated so the "Simulated" badge (DT-4) has something to render
against before core/exposure + the real spike injector (T1.7) exist.
"""

from __future__ import annotations

from datetime import datetime, timezone

import h3

from core.schemas.common import severity_band_for
from core.schemas.zones import ZoneReadingOut, ZonesResponse

H3_RES = 8

# (lat, lng, pm25, n_sensors, simulated)
_ZONES: list[tuple[float, float, float, int, bool]] = [
    (28.6315, 77.2167, 22.0, 3, False),   # Connaught Place - good
    (28.4950, 77.0890, 48.0, 2, False),   # Cyber Hub - satisfactory
    (28.6270, 77.3720, 75.0, 2, False),   # Noida Sector 62 - moderate
    (28.5562, 77.1000, 105.0, 1, False),  # IGI Airport - poor, medium confidence
    (28.5245, 77.2066, 180.0, 2, True),   # Saket - very poor, simulated spike
    (28.5921, 77.0460, 300.0, 3, True),   # Dwarka - severe, simulated spike
    (28.7041, 77.1025, 55.0, 2, False),   # Rohini - satisfactory
]


def get_zones(ts: datetime | None = None) -> ZonesResponse:
    ts = ts or datetime.now(timezone.utc)
    zones = [
        ZoneReadingOut(
            h3=h3.latlng_to_cell(lat, lng, H3_RES),
            pm25=pm25,
            band=severity_band_for(pm25),
            confidence="high" if n_sensors >= 2 else "medium",
            n_sensors=n_sensors,
            simulated=simulated,
        )
        for lat, lng, pm25, n_sensors, simulated in _ZONES
    ]
    return ZonesResponse(ts=ts, bucket=f"{ts.isoformat()}/15m", zones=zones)
