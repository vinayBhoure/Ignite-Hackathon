"""Real POST /api/routes/plan: Google alternatives -> dose -> PRD decision rule.

Decision rule (CLAUDE.md domain facts): drop routes whose window margin is
under the buffer (2 min), pick the lowest dose (tie: shorter duration); if
none qualifies, recommend the fastest with window_at_risk. Always report the
delta vs the fastest route.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import timedelta

from core.navigation.exposure import ScoredRoute, score_route
from core.navigation.google import GoogleRoute, compute_routes
from core.schemas.routes import (
    RouteOption,
    RoutePlanRequest,
    RoutePlanResponse,
    RouteRecommendation,
    RouteStep,
)

WINDOW_BUFFER_S = 120
LOW_CONFIDENCE_COVERAGE = 0.8
MASK_FILTRATION = {"unmasked": 0.0}
_PLAN_CACHE_MAX = 300


@dataclass
class PlannedRoute:
    """Everything needed to assign or navigate a route later in this process."""

    request: RoutePlanRequest
    google: GoogleRoute
    scored: ScoredRoute
    option: RouteOption
    sibling_ids: tuple[str, ...]


_plans: "OrderedDict[str, PlannedRoute]" = OrderedDict()
_plans_lock = threading.Lock()


def get_planned(route_id: str) -> PlannedRoute | None:
    with _plans_lock:
        return _plans.get(route_id)


def _remember(items: list[PlannedRoute]) -> None:
    with _plans_lock:
        for item in items:
            _plans[item.option.id] = item
        while len(_plans) > _PLAN_CACHE_MAX:
            _plans.popitem(last=False)


def _steps(route: GoogleRoute) -> list[RouteStep]:
    return [
        RouteStep(
            instruction=s.instruction,
            maneuver=s.maneuver,
            distance_m=s.distance_m,
            duration_s=s.duration_s,
            lat=s.start[0],
            lng=s.start[1],
        )
        for s in route.steps
    ]


def decide(options: list[RouteOption]) -> RouteRecommendation:
    fastest = min(options, key=lambda r: r.duration_s)
    qualifying = [r for r in options if r.window_margin_s >= WINDOW_BUFFER_S]
    if qualifying:
        chosen = min(qualifying, key=lambda r: (r.dose, r.duration_s))
        at_risk = False
    else:
        chosen, at_risk = fastest, True
    for r in options:
        r.selected = r.id == chosen.id

    delta = 0.0 if fastest.dose == 0 else (chosen.dose - fastest.dose) / fastest.dose * 100
    return RouteRecommendation(
        route_id=chosen.id,
        dose_delta_pct=round(delta, 1),
        extra_minutes=round((chosen.duration_s - fastest.duration_s) / 60, 1),
        window_met=chosen.window_margin_s >= 0,
        window_at_risk=at_risk,
    )


def _label(options: list[RouteOption]) -> None:
    fastest = min(options, key=lambda r: r.duration_s).id
    cleanest = min(options, key=lambda r: (r.dose, r.duration_s)).id
    for r in options:
        tags = []
        if r.id == fastest:
            tags.append("Fastest")
        if r.id == cleanest and len(options) > 1:
            tags.append("Lowest exposure")
        r.label = " · ".join(tags) or "Alternative"


def explain(options: list[RouteOption], rec: RouteRecommendation) -> str:
    chosen = next(r for r in options if r.id == rec.route_id)
    minutes = chosen.duration_s / 60
    coverage = f"{chosen.coverage:.0%} of the ride has zone readings (gaps use the city mean)"
    if rec.window_at_risk:
        return (
            f"No route clears the delivery window with a 2-minute buffer, so the fastest "
            f"({minutes:.0f} min) is recommended and the window is flagged at risk; {coverage}."
        )
    if len(options) == 1:
        return f"Google returned one route ({minutes:.0f} min, dose {chosen.dose:.0f}); {coverage}."
    if rec.dose_delta_pct < -0.5:
        return (
            f"This route cuts exposure {abs(rec.dose_delta_pct):.0f}% versus the fastest for "
            f"+{rec.extra_minutes:.0f} min and still meets the window; {coverage}."
        )
    return f"The fastest route is also the lowest-exposure option that meets the window; {coverage}."


def plan(req: RoutePlanRequest) -> RoutePlanResponse:
    origin = (req.origin.lat, req.origin.lng)
    destination = (req.destination.lat, req.destination.lng)
    google_routes = compute_routes(origin, destination)
    mask = MASK_FILTRATION.get(req.mask_type, 0.0)

    planned: list[PlannedRoute] = []
    ids = [f"rt-{uuid.uuid4().hex[:10]}" for _ in google_routes]
    for rid, groute in zip(ids, google_routes):
        scored = score_route(list(groute.points), groute.duration_s, req.departure_ts, req.activity_factor, mask)
        eta = req.departure_ts + timedelta(seconds=groute.duration_s)
        option = RouteOption(
            id=rid,
            duration_s=groute.duration_s,
            distance_m=groute.distance_m,
            polyline=groute.encoded_polyline,
            eta=eta,
            window_margin_s=(req.window_end - eta).total_seconds(),
            dose=round(scored.dose, 2),
            coverage=round(scored.coverage, 3),
            confidence="high" if scored.coverage >= LOW_CONFIDENCE_COVERAGE else "low",
            rank=1,
            selected=False,
            zones=scored.zones,
            steps=_steps(groute),
        )
        planned.append(PlannedRoute(req, groute, scored, option, tuple(ids)))

    options = [p.option for p in planned]
    for rank, option in enumerate(sorted(options, key=lambda r: r.duration_s), start=1):
        option.rank = rank
    rec = decide(options)
    _label(options)
    _remember(planned)
    return RoutePlanResponse(routes=options, recommendation=rec, explanation=explain(options, rec))
