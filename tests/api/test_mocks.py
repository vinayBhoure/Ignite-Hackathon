"""T1.4 validation: mock providers run and their output matches the schemas."""

from datetime import datetime, timedelta, timezone

from api.mocks.orders import assign_order
from api.mocks.places import resolve_place
from api.mocks.routes import plan_routes
from api.mocks.zones import get_zones
from core.schemas.orders import OrderAssignRequest
from core.schemas.routes import RoutePlanRequest
from core.schemas.common import LatLng


def test_resolve_known_landmark_is_confident_and_unambiguous():
    resp = resolve_place("cp")
    assert resp.ambiguous is False
    assert resp.needs_pick is False
    assert resp.candidates[0].confidence >= 0.7


def test_resolve_unknown_query_needs_pick():
    resp = resolve_place("some random unknown place xyz")
    assert resp.ambiguous is True
    assert resp.needs_pick is True
    assert len(resp.candidates) >= 2


def test_plan_routes_picks_lowest_dose_within_generous_window():
    now = datetime(2020, 11, 1, 10, 0, tzinfo=timezone.utc)
    req = RoutePlanRequest(
        origin=LatLng(lat=28.6315, lng=77.2167),
        destination=LatLng(lat=28.4950, lng=77.0890),
        departure_ts=now,
        window_end=now + timedelta(hours=3),
    )
    resp = plan_routes(req)
    assert len(resp.routes) == 3
    selected = [r for r in resp.routes if r.selected]
    assert len(selected) == 1
    fastest = min(resp.routes, key=lambda r: r.duration_s)
    # with a generous window every route qualifies, so the lowest-dose one wins
    assert selected[0].dose == min(r.dose for r in resp.routes)
    assert resp.recommendation.window_at_risk is False
    assert resp.recommendation.dose_delta_pct <= 0
    if selected[0].id != fastest.id:
        assert resp.recommendation.extra_minutes > 0


def test_plan_routes_falls_back_to_fastest_when_window_is_tight():
    now = datetime(2020, 11, 1, 10, 0, tzinfo=timezone.utc)
    req = RoutePlanRequest(
        origin=LatLng(lat=28.6315, lng=77.2167),
        destination=LatLng(lat=28.4950, lng=77.0890),
        departure_ts=now,
        window_end=now + timedelta(minutes=1),  # no route can meet this
    )
    resp = plan_routes(req)
    fastest = min(resp.routes, key=lambda r: r.duration_s)
    selected = [r for r in resp.routes if r.selected][0]
    assert selected.id == fastest.id
    assert resp.recommendation.window_at_risk is True


def test_get_zones_spans_multiple_bands_and_flags_simulated():
    resp = get_zones()
    bands = {z.band for z in resp.zones}
    assert len(bands) >= 4
    assert any(z.simulated for z in resp.zones)
    assert any(not z.simulated for z in resp.zones)


def test_assign_order_echoes_request():
    resp = assign_order("order-1", OrderAssignRequest(route_id="r1", rider_id="rider-1"))
    assert resp.order_id == "order-1"
    assert resp.status == "assigned"
