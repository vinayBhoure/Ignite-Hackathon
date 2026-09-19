"""core/navigation: polylines, the decision rule, and plan -> assign ->
navigate -> arrive against the real zone layer. Google is stubbed with two
synthetic routes from the South Delhi Hub so results don't depend on live
traffic or quota."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import core.navigation.assignments as assignments
import core.navigation.planner as planner
from api.main import app
from core.clock.demo_clock import DEMO_START, apply_action
from core.db.client import get_session
from core.navigation.geometry import cumulative_m, decode_polyline, encode_polyline
from core.navigation.google import GoogleRoute, Step
from core.schemas.common import LatLng
from core.schemas.demo import ClockActionRequest
from core.schemas.orders import OrderAssignRequest
from core.schemas.routes import RouteOption, RoutePlanRequest
from tests.helpers import signed_in

HUB = (28.58133, 77.22538)
DEST = (28.61200, 77.22600)
ORDER_ID = "test-nav-order-1"
RIDER = "rider-8"


def _route(index: int, points: list, duration: float) -> GoogleRoute:
    dist = cumulative_m(points)[-1]
    steps = (
        Step("Head north", "DEPART", dist / 2, duration / 2, points[0], points[len(points) // 2]),
        Step("Turn right onto Test Rd", "TURN_RIGHT", dist / 2, duration / 2, points[len(points) // 2], points[-1]),
    )
    return GoogleRoute(index, duration, duration, dist, encode_polyline(points), (), steps, tuple(points))


def _line(a, b, n=12):
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def fake_routes(origin, destination):
    straight = _line(origin, destination)
    mid = ((origin[0] + destination[0]) / 2, origin[1] + 0.02)
    detour = _line(origin, mid, 8)[:-1] + _line(mid, destination, 8)
    return [_route(0, straight, 900.0), _route(1, detour, 1300.0)]


@pytest.fixture
def stub_google(monkeypatch):
    monkeypatch.setattr(planner, "compute_routes", fake_routes)
    monkeypatch.setattr(assignments, "compute_routes", fake_routes)


@pytest.fixture
def at_demo_start():
    apply_action(ClockActionRequest(action="pause"))
    apply_action(ClockActionRequest(action="jump", to=DEMO_START))
    yield DEMO_START


def _cleanup():
    with get_session() as s:
        s.run("MATCH (a:Alert {order_id: $id}) DETACH DELETE a", id=ORDER_ID)
        s.run(
            """MATCH (o:Order {id: $id}) OPTIONAL MATCH (o)-[:HAS_CANDIDATE]->(rt:Route)
               WITH o, collect(rt) AS rts FOREACH (x IN rts | DETACH DELETE x) DETACH DELETE o""",
            id=ORDER_ID,
        )
        s.run("MATCH (rd:Rider {id: $id}) SET rd.status = 'available'", id=RIDER)


def _request(departure):
    return RoutePlanRequest(
        origin=LatLng(lat=HUB[0], lng=HUB[1]), destination=LatLng(lat=DEST[0], lng=DEST[1]),
        departure_ts=departure, window_end=departure + timedelta(minutes=60),
    )


# --------------------------------------------------------------- pure


def test_polyline_decodes_googles_reference_example():
    pts = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert pts == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
    assert decode_polyline(encode_polyline(pts)) == pts


def _opt(id_, dur, dose, margin):
    return RouteOption(id=id_, duration_s=dur, distance_m=1000, polyline="", eta=DEMO_START,
                       window_margin_s=margin, dose=dose, coverage=1, confidence="high", rank=1,
                       selected=False, zones=[])


def test_decide_prefers_lowest_dose_within_the_window():
    opts = [_opt("fast", 600, 50, 900), _opt("clean", 700, 30, 800)]
    rec = planner.decide(opts)
    assert rec.route_id == "clean" and not rec.window_at_risk
    assert rec.dose_delta_pct == -40.0 and rec.extra_minutes == pytest.approx(1.7, abs=0.1)
    assert [o.selected for o in opts] == [False, True]


def test_decide_drops_routes_inside_the_buffer_and_ties_on_duration():
    opts = [_opt("fast", 600, 50, 900), _opt("tight", 700, 10, 60), _opt("tie", 650, 50, 900)]
    assert planner.decide(opts).route_id == "fast"


def test_decide_falls_back_to_fastest_when_no_route_fits():
    opts = [_opt("fast", 600, 50, 60), _opt("clean", 700, 10, 30)]
    rec = planner.decide(opts)
    assert rec.route_id == "fast" and rec.window_at_risk


# --------------------------------------------------------------- with Neo4j


def test_plan_scores_each_alternative(stub_google, at_demo_start):
    resp = planner.plan(_request(at_demo_start))
    assert len(resp.routes) == 2
    assert sum(r.selected for r in resp.routes) == 1
    assert sorted(r.rank for r in resp.routes) == [1, 2]
    fastest = min(resp.routes, key=lambda r: r.duration_s)
    assert fastest.label.startswith("Fastest")
    for r in resp.routes:
        assert r.dose > 0  # daytime demo start: readings or city-mean fill
        assert 0 <= r.coverage <= 1 and r.confidence in ("high", "low")
        assert len(r.steps) == 2 and r.polyline
    assert resp.explanation


def test_assign_navigate_and_arrive(stub_google, at_demo_start):
    try:
        resp = planner.plan(_request(at_demo_start))
        assignments.assign_order(
            ORDER_ID, OrderAssignRequest(route_id=resp.recommendation.route_id, rider_id=RIDER,
                                         pickup_name="Hub", drop_name="Test drop"),
        )
        nav = assignments.navigation(ORDER_ID, RIDER)
        assert nav.status == "en_route" and nav.progress == 0
        assert (nav.position.lat, nav.position.lng) == pytest.approx(HUB, abs=1e-4)
        assert nav.steps[1].maneuver == "TURN_RIGHT"
        assert any(a.order_id == ORDER_ID for a in assignments.active_assignments())

        with pytest.raises(assignments.NotFound):
            assignments.navigation(ORDER_ID, "rider-7")

        chosen = next(r for r in resp.routes if r.selected)
        apply_action(ClockActionRequest(action="jump", to=at_demo_start + timedelta(seconds=chosen.duration_s / 2)))
        mid = assignments.navigation(ORDER_ID, RIDER)
        assert 0.4 < mid.progress < 0.6 and mid.minutes_remaining == pytest.approx(chosen.duration_s / 120, abs=0.2)

        apply_action(ClockActionRequest(action="jump", to=at_demo_start + timedelta(seconds=chosen.duration_s + 60)))
        done = assignments.navigation(ORDER_ID, RIDER)
        assert done.status == "arrived"
        assert not any(a.order_id == ORDER_ID for a in assignments.active_assignments())
    finally:
        _cleanup()


def test_rider_navigation_api_is_scoped_to_the_rider(stub_google, at_demo_start):
    try:
        resp = planner.plan(_request(at_demo_start))
        assignments.assign_order(ORDER_ID, OrderAssignRequest(route_id=resp.recommendation.route_id, rider_id=RIDER))
        rider8 = signed_in({"role": "rider", "identifier": "9900000008", "password": "aevora-rider"})
        orders = rider8.get("/api/rider/orders").json()
        assert [o["order_id"] for o in orders] == [ORDER_ID]
        nav = rider8.get(f"/api/rider/orders/{ORDER_ID}/navigation")
        assert nav.status_code == 200 and nav.json()["route_id"] == resp.recommendation.route_id

        rider7 = signed_in({"role": "rider", "identifier": "9900000007", "password": "aevora-rider"})
        assert rider7.get(f"/api/rider/orders/{ORDER_ID}/navigation").status_code == 404
        assert TestClient(app).get(f"/api/rider/orders/{ORDER_ID}/navigation").status_code == 401
    finally:
        _cleanup()
