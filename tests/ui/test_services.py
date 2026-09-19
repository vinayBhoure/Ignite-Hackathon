"""T2.1: ui/services.py is a thin, working facade over the same mock/real
switch and core/ calls the API uses - no scoring logic duplicated here."""

from datetime import datetime, timezone

import ui.services as services
from core.schemas.common import LatLng
from core.schemas.orders import OrderAssignRequest
from core.schemas.routes import RoutePlanRequest


def test_resolve_place_uses_mock_by_default():
    resp = services.resolve_place("cp")
    assert resp.needs_pick is False


def test_plan_routes_round_trip():
    now = datetime(2020, 11, 1, tzinfo=timezone.utc)
    req = RoutePlanRequest(
        origin=LatLng(lat=28.6315, lng=77.2167),
        destination=LatLng(lat=28.4950, lng=77.0890),
        departure_ts=now,
        window_end=now.replace(hour=23),
    )
    resp = services.plan_routes(req)
    assert len(resp.routes) == 3


def test_get_zones_returns_data():
    resp = services.get_zones()
    assert len(resp.zones) > 0


def test_assign_order_round_trip():
    resp = services.assign_order("o1", OrderAssignRequest(route_id="r1"))
    assert resp.order_id == "o1"


def test_clock_state_reads_real_clock():
    state = services.get_clock_state()
    assert state.min_ts < state.max_ts


def test_using_mocks_reflects_settings():
    assert isinstance(services.using_mocks(), bool)
