"""Mock POST /api/routes/plan. Fabricates up to 3 route alternatives and applies
the PRD decision rule so T2.5/T2.6 have something real to render against, ahead
of core/routing + core/dispatch existing. Swapped for real core/ calls at T2.10.
"""

from __future__ import annotations

import math
import uuid
from datetime import timedelta

import h3

from core.schemas.common import RouteConfidence
from core.schemas.routes import (
    RouteOption,
    RoutePlanRequest,
    RoutePlanResponse,
    RouteRecommendation,
    RouteZoneSegment,
)

H3_RES = 8
WINDOW_BUFFER_S = 120  # PRD default 2-minute buffer

# (duration multiplier vs the fastest route, pm25 for the traversed zones)
_VARIANTS = [
    ("fastest", 1.00, 140.0),
    ("balanced", 1.12, 85.0),
    ("low_exposure", 1.28, 45.0),
]


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def plan_routes(req: RoutePlanRequest) -> RoutePlanResponse:
    distance_m = max(_haversine_m(req.origin.lat, req.origin.lng, req.destination.lat, req.destination.lng), 500)
    base_duration_s = distance_m / (25 * 1000 / 3600)  # ~25 km/h baseline city speed

    origin_h3 = h3.latlng_to_cell(req.origin.lat, req.origin.lng, H3_RES)
    dest_h3 = h3.latlng_to_cell(req.destination.lat, req.destination.lng, H3_RES)

    mask_factor = 0.0 if req.mask_type == "unmasked" else 0.5  # placeholder until Track A ships F_mask

    routes: list[RouteOption] = []
    for rank, (label, mult, pm25) in enumerate(_VARIANTS, start=1):
        duration_s = base_duration_s * mult
        half = duration_s / 2
        zones = [
            RouteZoneSegment(h3=origin_h3, seconds=half, pm25=pm25, source="sensor", sensors=["mock-s1"]),
            RouteZoneSegment(h3=dest_h3, seconds=half, pm25=pm25 * 0.8, source="sensor", sensors=["mock-s2"]),
        ]
        dose = sum(z.pm25 * (z.seconds / 3600) for z in zones) * req.activity_factor * (1 - mask_factor)
        eta = req.departure_ts + timedelta(seconds=duration_s)
        window_margin_s = (req.window_end - eta).total_seconds()
        coverage = 1.0 if label != "low_exposure" else 0.75
        confidence: RouteConfidence = "high" if coverage >= 0.8 else "low"

        routes.append(
            RouteOption(
                id=f"mock-{label}-{uuid.uuid4().hex[:6]}",
                duration_s=duration_s,
                distance_m=distance_m * mult,
                polyline="",
                eta=eta,
                window_margin_s=window_margin_s,
                dose=round(dose, 2),
                coverage=coverage,
                confidence=confidence,
                rank=rank,
                selected=False,
                zones=zones,
            )
        )

    fastest = min(routes, key=lambda r: r.duration_s)
    qualifying = [r for r in routes if r.window_margin_s >= WINDOW_BUFFER_S]

    if qualifying:
        chosen = min(qualifying, key=lambda r: (r.dose, r.duration_s))
        window_at_risk = False
    else:
        chosen = fastest
        window_at_risk = True
    chosen.selected = True

    dose_delta_pct = (
        0.0 if fastest.dose == 0 else round((chosen.dose - fastest.dose) / fastest.dose * 100, 1)
    )
    extra_minutes = round((chosen.duration_s - fastest.duration_s) / 60, 1)

    recommendation = RouteRecommendation(
        route_id=chosen.id,
        dose_delta_pct=dose_delta_pct,
        extra_minutes=extra_minutes,
        window_met=chosen.window_margin_s >= 0,
        window_at_risk=window_at_risk,
    )

    explanation = (
        f"Recommended route adds {extra_minutes:.0f} min but cuts exposure {abs(dose_delta_pct):.0f}% "
        f"vs the fastest option."
        if dose_delta_pct < 0
        else "Fastest route recommended; the delivery window is tight."
    )

    return RoutePlanResponse(routes=routes, recommendation=recommendation, explanation=explanation)
