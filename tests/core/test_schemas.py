"""core/schemas import and validate against the Appendix A JSON examples (T1.2)."""

from core.schemas import (
    ClockActionRequest,
    ClockState,
    OrderAssignRequest,
    OrderAssignResponse,
    PlaceResolveRequest,
    PlaceResolveResponse,
    PushSubscribeRequest,
    RoutePlanRequest,
    RoutePlanResponse,
    SpikeRequest,
    SpikeResponse,
    ZonesResponse,
)


def test_place_resolve_round_trip():
    req = PlaceResolveRequest(query="cp delhi")
    resp = PlaceResolveResponse.model_validate(
        {
            "candidates": [
                {
                    "place_id": "abc",
                    "name": "Connaught Place, New Delhi",
                    "lat": 28.63,
                    "lng": 77.22,
                    "h3": "8830000000fffff",
                    "confidence": 0.93,
                }
            ],
            "ambiguous": False,
            "needs_pick": False,
        }
    )
    assert req.query == "cp delhi"
    assert resp.candidates[0].confidence == 0.93


def test_routes_plan_round_trip():
    req = RoutePlanRequest.model_validate(
        {
            "origin": {"lat": 28.6, "lng": 77.2},
            "destination": {"lat": 28.7, "lng": 77.3},
            "departure_ts": "2020-11-01T10:00:00Z",
            "window_end": "2020-11-01T11:00:00Z",
        }
    )
    assert req.mask_type == "unmasked"
    assert req.activity_factor == 1.0

    resp = RoutePlanResponse.model_validate(
        {
            "routes": [
                {
                    "id": "r1",
                    "duration_s": 1200,
                    "distance_m": 8000,
                    "polyline": "encoded",
                    "eta": "2020-11-01T10:20:00Z",
                    "window_margin_s": 2400,
                    "dose": 12.5,
                    "coverage": 0.9,
                    "confidence": "high",
                    "rank": 1,
                    "selected": True,
                    "zones": [
                        {
                            "h3": "8830000000fffff",
                            "seconds": 300,
                            "pm25": 80.0,
                            "source": "sensor",
                            "sensors": ["s1", "s2"],
                        }
                    ],
                }
            ],
            "recommendation": {
                "route_id": "r1",
                "dose_delta_pct": -15.0,
                "extra_minutes": 3.0,
                "window_met": True,
                "window_at_risk": False,
            },
            "explanation": "This route avoids the worst pollution near CP.",
        }
    )
    assert resp.routes[0].confidence == "high"
    assert resp.recommendation.window_met is True


def test_zones_response_round_trip():
    resp = ZonesResponse.model_validate(
        {
            "ts": "2020-11-01T10:00:00Z",
            "bucket": "2020-11-01T10:00:00Z/15m",
            "zones": [
                {
                    "h3": "8830000000fffff",
                    "pm25": 45.0,
                    "band": "satisfactory",
                    "confidence": "high",
                    "n_sensors": 2,
                    "simulated": False,
                }
            ],
        }
    )
    assert resp.zones[0].band == "satisfactory"


def test_clock_action_and_state():
    req = ClockActionRequest.model_validate({"action": "set_speed", "speed": 60})
    assert req.speed == 60
    state = ClockState.model_validate(
        {
            "now_ts": "2020-11-01T10:00:00Z",
            "speed": 60,
            "running": True,
            "min_ts": "2020-11-01T00:00:00Z",
            "max_ts": "2020-11-30T23:45:00Z",
        }
    )
    assert state.running is True


def test_spike_round_trip():
    req = SpikeRequest.model_validate({"h3": "8830000000fffff", "pm25": 300, "duration_min": 45})
    resp = SpikeResponse.model_validate(
        {"spike_id": "sp1", "buckets_written": 3, "source": "simulated"}
    )
    assert req.pm25 == 300
    assert resp.source == "simulated"


def test_push_subscribe_round_trip():
    req = PushSubscribeRequest.model_validate(
        {
            "rider_id": "rider-1",
            "subscription": {
                "endpoint": "https://fcm.googleapis.com/example",
                "keys": {"p256dh": "key", "auth": "auth"},
            },
        }
    )
    assert req.rider_id == "rider-1"


def test_order_assign_round_trip():
    req = OrderAssignRequest.model_validate({"route_id": "r1", "rider_id": "rider-1"})
    resp = OrderAssignResponse.model_validate(
        {"order_id": "o1", "route_id": "r1", "rider_id": "rider-1"}
    )
    assert req.route_id == "r1"
    assert resp.status == "assigned"
