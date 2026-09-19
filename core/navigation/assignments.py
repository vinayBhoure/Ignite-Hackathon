"""Assign planned routes to riders, and derive live navigation from the
replay clock.

Persisted (Neo4j): Order{pickup, drop, nav_start, departure_ts, window_end,
status}, Route scores, HAS_CANDIDATE, PASSES_THROUGH{idx, seconds, bucket}
to existing zones, Rider-[:ASSIGNED]->Order. Never persisted: polylines or
steps (CLAUDE.md rule 9). A process that didn't plan the route (the rider
app runs in the API, planning happens in Streamlit) re-fetches the Google
alternatives for the same leg and takes the one closest in length.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

import h3

from core.alerts.evaluator import list_alerts, maybe_tick
from core.clock.demo_clock import get_state
from core.clock.math import floor_to_bucket
from core.db.client import get_session, to_data_tz, to_utc
from core.navigation.exposure import score_route
from core.navigation.geometry import cumulative_m, point_at_distance, remaining_path
from core.navigation.google import GoogleRoute, compute_routes
from core.navigation.planner import PlannedRoute, get_planned, plan
from core.schemas.common import LatLng, severity_band_for
from core.schemas.navigation import (
    AssignmentSummary,
    NavigationState,
    NavZone,
    RerouteOption,
    ReroutePreview,
    RiderSummary,
    RouteZoneAhead,
)
from core.schemas.orders import OrderAssignRequest, OrderAssignResponse
from core.schemas.routes import RoutePlanRequest, RouteStep

_geometry_cache: dict[str, GoogleRoute] = {}
_geometry_lock = threading.Lock()


class NotFound(LookupError):
    pass


# --------------------------------------------------------------------------- persistence


def _persist_routes(session, order_id: str, planned: list[PlannedRoute], selected_id: str) -> None:
    session.run(
        """
        MATCH (o:Order {id: $order_id})
        OPTIONAL MATCH (o)-[:HAS_CANDIDATE]->(old:Route)
        SET old.selected = false
        WITH DISTINCT o
        UNWIND $routes AS r
        MERGE (rt:Route {id: r.id})
        SET rt.provider = 'google', rt.duration_s = r.duration_s, rt.distance_m = r.distance_m,
            rt.dose = r.dose, rt.margin_s = r.margin_s, rt.coverage = r.coverage,
            rt.rank = r.rank, rt.label = r.label, rt.selected = (r.id = $selected_id)
        MERGE (o)-[:HAS_CANDIDATE]->(rt)
        """,
        order_id=order_id,
        selected_id=selected_id,
        routes=[
            {
                "id": p.option.id,
                "duration_s": p.option.duration_s,
                "distance_m": p.option.distance_m,
                "dose": p.option.dose,
                "margin_s": p.option.window_margin_s,
                "coverage": p.option.coverage,
                "rank": p.option.rank,
                "label": p.option.label,
            }
            for p in planned
        ],
    )
    for p in planned:
        session.run(
            """
            MATCH (rt:Route {id: $route_id})
            UNWIND $segments AS s
            MATCH (z:Zone {h3: s.h3})
            MERGE (rt)-[pt:PASSES_THROUGH {idx: s.idx}]->(z)
            SET pt.seconds = s.seconds, pt.bucket = s.bucket, pt.pm25_planned = s.pm25, pt.offset_s = s.offset
            """,
            route_id=p.option.id,
            # pm25_planned lets the evaluator alert on air that got worse
            # *after* the route was chosen, not on history the plan already knew;
            # offset_s (seconds from departure to entering the zone) gives the
            # console exact "reached in N min", finer than the 15-min bucket.
            segments=[
                {
                    "idx": s.idx, "h3": s.h3, "seconds": s.seconds, "bucket": to_data_tz(s.bucket), "pm25": s.pm25,
                    "offset": (s.enter_ts - p.request.departure_ts).total_seconds(),
                }
                for s in p.scored.segments
            ],
        )
        with _geometry_lock:
            _geometry_cache[p.option.id] = p.google


def assign_order(order_id: str, req: OrderAssignRequest) -> OrderAssignResponse:
    chosen = get_planned(req.route_id)
    if chosen is None:
        raise NotFound(f"route {req.route_id} is not from a recent plan - plan the order again")
    siblings = [p for rid in chosen.sibling_ids if (p := get_planned(rid)) is not None]
    plan_req = chosen.request

    with get_session() as session:
        session.run(
            """
            MERGE (o:Order {id: $order_id})
            SET o.pickup = point({latitude: $plat, longitude: $plng}),
                o.drop = point({latitude: $dlat, longitude: $dlng}),
                o.nav_start = point({latitude: $plat, longitude: $plng}),
                o.pickup_name = $pickup_name, o.drop_name = $drop_name,
                o.window_start = $departure, o.departure_ts = $departure,
                o.window_end = $window_end, o.status = 'assigned', o.created_by = 'aevora-console'
            """,
            order_id=order_id,
            plat=plan_req.origin.lat, plng=plan_req.origin.lng,
            dlat=plan_req.destination.lat, dlng=plan_req.destination.lng,
            pickup_name=req.pickup_name or "Pickup",
            drop_name=req.drop_name or "Drop",
            departure=plan_req.departure_ts, window_end=plan_req.window_end,
        )
        _persist_routes(session, order_id, siblings or [chosen], req.route_id)
        if req.rider_id:
            session.run(
                """
                MATCH (o:Order {id: $order_id})
                OPTIONAL MATCH (other:Rider)-[old:ASSIGNED]->(o)
                DELETE old
                WITH o
                MATCH (rd:Rider {id: $rider_id})
                MERGE (rd)-[a:ASSIGNED]->(o)
                SET a.ts = $now, rd.status = 'on_delivery'
                """,
                order_id=order_id, rider_id=req.rider_id, now=get_state().now_ts,
            )
    return OrderAssignResponse(order_id=order_id, route_id=req.route_id, rider_id=req.rider_id)


# --------------------------------------------------------------------------- reads


_ORDER_QUERY = """
MATCH (rd:Rider)-[:ASSIGNED]->(o:Order {id: $order_id})-[:HAS_CANDIDATE]->(rt:Route {selected: true})
WHERE $rider_id IS NULL OR rd.id = $rider_id
RETURN rd, o, rt
LIMIT 1
"""


def _load(order_id: str, rider_id: str | None):
    with get_session() as session:
        row = session.run(_ORDER_QUERY, order_id=order_id, rider_id=rider_id).single()
    if row is None:
        raise NotFound(f"order {order_id} not found for this rider")
    return dict(row["rd"]), dict(row["o"]), dict(row["rt"])


def _geometry(route: dict, order: dict) -> GoogleRoute:
    with _geometry_lock:
        cached = _geometry_cache.get(route["id"])
    if cached:
        return cached
    planned = get_planned(route["id"])
    if planned:
        geo = planned.google
    else:
        start, drop = order.get("nav_start") or order["pickup"], order["drop"]
        options = compute_routes((start.y, start.x), (drop.y, drop.x))
        geo = min(options, key=lambda r: abs(r.distance_m - float(route.get("distance_m") or 0)))
    with _geometry_lock:
        _geometry_cache[route["id"]] = geo
    return geo


def _steps(geo: GoogleRoute) -> list[RouteStep]:
    return [
        RouteStep(instruction=s.instruction, maneuver=s.maneuver, distance_m=s.distance_m,
                  duration_s=s.duration_s, lat=s.start[0], lng=s.start[1])
        for s in geo.steps
    ]


def navigation(order_id: str, rider_id: str | None = None) -> NavigationState:
    maybe_tick()
    rider, order, route = _load(order_id, rider_id)
    geo = _geometry(route, order)
    clock = get_state()
    now = clock.now_ts

    departure = to_utc(order.get("departure_ts") or order["window_start"])
    window_end = to_utc(order["window_end"])
    duration = geo.duration_s or float(route.get("duration_s") or 1)
    elapsed = (now - departure).total_seconds()
    progress = min(max(elapsed / duration, 0.0), 1.0)

    points = list(geo.points)
    cum = cumulative_m(points)
    traveled = cum[-1] * progress
    position, _ = point_at_distance(points, cum, traveled)

    step_idx, acc = 0, 0.0
    for i, step in enumerate(geo.steps):
        acc += step.distance_m
        step_idx = i
        if acc >= traveled:
            break

    scored = score_route(points, duration, departure, float(rider.get("activity_factor") or 1.0))
    now_bucket = floor_to_bucket(now)
    zones: list[NavZone] = []
    dose_so_far = 0.0
    for seg in scored.segments:
        lat, lng = h3.cell_to_latlng(seg.h3)
        ahead = seg.enter_ts + timedelta(seconds=seg.seconds) > now
        zones.append(
            NavZone(
                h3=seg.h3, lat=lat, lng=lng, bucket=seg.bucket, reach_ts=seg.enter_ts, pm25=seg.pm25,
                band=severity_band_for(seg.pm25) if seg.pm25 is not None else None,
                simulated=seg.source == "simulated", estimated=seg.source == "model", ahead=ahead,
            )
        )
        if seg.pm25 is not None:
            passed = min(max((now - seg.enter_ts).total_seconds(), 0.0), seg.seconds)
            dose_so_far += seg.pm25 * passed / 3600 * float(rider.get("activity_factor") or 1.0)

    next_bad = next(
        (
            z for z in zones
            if z.ahead and not z.estimated and z.pm25 is not None and z.pm25 > 90 and z.bucket >= now_bucket
        ),
        None,
    )

    status = "arrived" if progress >= 1.0 else "en_route"
    if status == "arrived" and order.get("status") != "delivered":
        with get_session() as session:
            session.run(
                """
                MATCH (o:Order {id: $order_id}) SET o.status = 'delivered'
                WITH o MATCH (rd:Rider)-[:ASSIGNED]->(o) SET rd.status = 'available'
                """,
                order_id=order_id,
            )

    eta = departure + timedelta(seconds=duration)
    alerts = [a for a in list_alerts(status="new", rider_id=rider["id"], tick=False) if a.order_id == order_id]
    return NavigationState(
        order_id=order_id, rider_id=rider["id"], rider_name=rider.get("name", rider["id"]),
        pickup_name=order.get("pickup_name") or "Pickup", drop_name=order.get("drop_name") or "Drop",
        status=status, route_id=route["id"], route_label=route.get("label"),
        polyline=geo.encoded_polyline, steps=_steps(geo),
        position=LatLng(lat=position[0], lng=position[1]), progress=round(progress, 4),
        current_step=step_idx, distance_remaining_m=max(cum[-1] - traveled, 0.0),
        minutes_remaining=max(duration - elapsed, 0.0) / 60, eta=eta, window_end=window_end,
        window_margin_min=(window_end - eta).total_seconds() / 60,
        dose_total=round(scored.dose * float(rider.get("activity_factor") or 1.0), 2),
        dose_so_far=round(dose_so_far, 2), coverage=round(scored.coverage, 3),
        confidence="high" if scored.coverage >= 0.8 else "low",
        zones=zones, next_bad_zone=next_bad, alerts=alerts,
        replay_now=now, clock_running=clock.running, clock_speed=clock.speed,
    )


def rider_orders(rider_id: str) -> list[AssignmentSummary]:
    return [a for a in active_assignments(include_delivered=True) if a.rider_id == rider_id]


def active_assignments(include_delivered: bool = False) -> list[AssignmentSummary]:
    now = get_state().now_ts
    with get_session() as session:
        rows = list(
            session.run(
                """
                MATCH (rd:Rider)-[:ASSIGNED]->(o:Order)-[:HAS_CANDIDATE]->(rt:Route {selected: true})
                WHERE o.created_by = 'aevora-console' AND ($all OR o.status <> 'delivered')
                OPTIONAL MATCH (a:Alert {status: 'new', order_id: o.id})
                RETURN rd, o, rt, count(a) AS alerts
                ORDER BY o.departure_ts DESC
                """,
                all=include_delivered,
            )
        )
    out = []
    for row in rows:
        rd, o, rt = dict(row["rd"]), dict(row["o"]), dict(row["rt"])
        departure = to_utc(o["departure_ts"])
        duration = float(rt.get("duration_s") or 1)
        progress = min(max((now - departure).total_seconds() / duration, 0.0), 1.0)
        out.append(
            AssignmentSummary(
                order_id=o["id"], rider_id=rd["id"], rider_name=rd.get("name", rd["id"]),
                pickup_name=o.get("pickup_name") or "Pickup", drop_name=o.get("drop_name") or "Drop",
                route_id=rt["id"], route_label=rt.get("label"), duration_min=duration / 60,
                dose=float(rt.get("dose") or 0), coverage=float(rt.get("coverage") or 0),
                progress=round(progress, 3), eta=departure + timedelta(seconds=duration),
                status="delivered" if progress >= 1 or o.get("status") == "delivered" else "en_route",
                new_alerts=int(row["alerts"]),
            )
        )
    return out


def list_riders() -> list[RiderSummary]:
    with get_session() as session:
        rows = list(
            session.run(
                """
                MATCH (rd:Rider) WHERE rd.id STARTS WITH 'rider-'
                OPTIONAL MATCH (rd)-[:ASSIGNED]->(o:Order {created_by: 'aevora-console'})
                WHERE o.status <> 'delivered'
                RETURN rd, collect(o.id)[0] AS order_id
                ORDER BY rd.id
                """
            )
        )
    return [
        RiderSummary(
            id=r["rd"]["id"], name=r["rd"].get("name", r["rd"]["id"]),
            status="on_delivery" if r["order_id"] else "available",
            activity_factor=float(r["rd"].get("activity_factor") or 1.0), order_id=r["order_id"],
        )
        for r in rows
    ]


def zones_ahead(order_id: str) -> list[RouteZoneAhead]:
    """Zones on an order's selected route the rider hasn't reached yet - the
    targets for a demo spike that should trigger an alert and reroute."""
    now = get_state().now_ts
    now_bucket = floor_to_bucket(now)
    with get_session() as session:
        rows = list(
            session.run(
                """
                MATCH (o:Order {id: $order_id})-[:HAS_CANDIDATE]->(rt:Route {selected: true})-[p:PASSES_THROUGH]->(z:Zone)
                WHERE p.bucket >= $now_bucket
                OPTIONAL MATCH (zr:ZoneReading {h3: z.h3, ts: p.bucket})
                WITH o, z, p, max(zr.pm25) AS pm25
                OPTIONAL MATCH (o)-[:HAS_CANDIDATE]->(alt:Route {selected: false})
                WITH o, z, p, pm25, collect(alt) AS alts
                RETURN z.h3 AS h3, p.bucket AS bucket, p.idx AS idx, p.offset_s AS offset,
                       o.departure_ts AS departure, pm25,
                       size(alts) > 0 AND none(a IN alts WHERE (a)-[:PASSES_THROUGH]->(z)) AS avoidable
                ORDER BY idx
                """,
                order_id=order_id, now_bucket=to_data_tz(now_bucket),
            )
        )
    out = []
    for r in rows:
        if r["offset"] is not None and r["departure"] is not None:
            reached = to_utc(r["departure"]) + timedelta(seconds=r["offset"])
        else:
            reached = to_utc(r["bucket"])
        minutes = (reached - now).total_seconds() / 60
        if minutes < 0 and r["offset"] is not None:
            continue  # already passed
        out.append(
            RouteZoneAhead(h3=r["h3"], bucket=to_utc(r["bucket"]), minutes_ahead=max(minutes, 0.0),
                           pm25=r["pm25"], avoidable=bool(r["avoidable"]))
        )
    return out


# --------------------------------------------------------------------------- reroute


def _position(order_id: str, rider_id: str) -> tuple[dict, dict, dict, GoogleRoute, datetime, float]:
    rider, order, route = _load(order_id, rider_id)
    geo = _geometry(route, order)
    now = get_state().now_ts
    departure = to_utc(order.get("departure_ts") or order["window_start"])
    progress = min(max((now - departure).total_seconds() / (geo.duration_s or 1), 0.0), 1.0)
    return rider, order, route, geo, now, progress


def reroute_preview(order_id: str, rider_id: str) -> ReroutePreview:
    rider, order, _, geo, now, progress = _position(order_id, rider_id)
    if progress >= 1.0:
        return ReroutePreview(order_id=order_id, current_minutes=0, current_dose=0, best=None,
                              recommend_switch=False, message="You've arrived - nothing to reroute.")

    points = list(geo.points)
    cum = cumulative_m(points)
    rest = remaining_path(points, cum, cum[-1] * progress)
    rest_seconds = geo.duration_s * (1 - progress)
    activity = float(rider.get("activity_factor") or 1.0)
    current = score_route(rest, rest_seconds, now, activity)

    here = rest[0]
    drop = order["drop"]
    req = RoutePlanRequest(
        origin=LatLng(lat=here[0], lng=here[1]), destination=LatLng(lat=drop.y, lng=drop.x),
        departure_ts=now, window_end=to_utc(order["window_end"]), activity_factor=activity,
    )
    result = plan(req)
    best = next(r for r in result.routes if r.id == result.recommendation.route_id)

    extra = (best.duration_s - rest_seconds) / 60
    saved = 0.0 if current.dose == 0 else (current.dose - best.dose) / current.dose * 100
    switch = saved >= 5 and not result.recommendation.window_at_risk
    if switch:
        message = f"Reroute adds {extra:+.0f} min and cuts exposure {saved:.0f}% for the rest of this ride."
    else:
        message = "Your current route is still the best option for the rest of this ride."
    return ReroutePreview(
        order_id=order_id, current_minutes=rest_seconds / 60, current_dose=round(current.dose, 2),
        best=RerouteOption(route_id=best.id, polyline=best.polyline, minutes=best.duration_s / 60,
                           dose=best.dose, coverage=best.coverage),
        extra_minutes=round(extra, 1), dose_saved_pct=round(saved, 1),
        recommend_switch=switch, message=message,
    )


def reroute_commit(order_id: str, rider_id: str, route_id: str) -> NavigationState:
    chosen = get_planned(route_id)
    if chosen is None:
        raise NotFound("That reroute option expired - request a new one")
    siblings = [p for rid in chosen.sibling_ids if (p := get_planned(rid)) is not None]
    now = get_state().now_ts
    _load(order_id, rider_id)
    with get_session() as session:
        session.run(
            """
            MATCH (o:Order {id: $order_id})
            SET o.nav_start = point({latitude: $lat, longitude: $lng}), o.departure_ts = $now
            """,
            order_id=order_id, lat=chosen.request.origin.lat, lng=chosen.request.origin.lng, now=now,
        )
        _persist_routes(session, order_id, siblings or [chosen], route_id)
        session.run(
            "MATCH (a:Alert {order_id: $order_id, status: 'new'}) SET a.status = 'acked', a.acked_ts = $now",
            order_id=order_id, now=now,
        )
    return navigation(order_id, rider_id)
