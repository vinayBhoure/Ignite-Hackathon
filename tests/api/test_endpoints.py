"""T1.5 validation: the four mocked endpoints work end-to-end over HTTP."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_places_resolve():
    resp = client.post("/api/places/resolve", json={"query": "cp"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_pick"] is False
    assert body["candidates"][0]["confidence"] >= 0.7


def test_places_resolve_validation_error_uses_envelope():
    resp = client.post("/api/places/resolve", json={})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_routes_plan():
    resp = client.post(
        "/api/routes/plan",
        json={
            "origin": {"lat": 28.6315, "lng": 77.2167},
            "destination": {"lat": 28.4950, "lng": 77.0890},
            "departure_ts": "2020-11-01T10:00:00Z",
            "window_end": "2020-11-01T13:00:00Z",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["routes"]) == 3
    assert "recommendation" in body
    assert "explanation" in body


def test_zones():
    resp = client.get("/api/zones")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["zones"]) > 0
    assert "ts" in body and "bucket" in body


def test_zones_with_ts_param():
    resp = client.get("/api/zones", params={"ts": "2020-11-01T10:00:00Z"})
    assert resp.status_code == 200
    assert resp.json()["ts"].startswith("2020-11-01T10:00:00")


def test_orders_assign_requires_dispatcher():
    assert client.post("/api/orders/order-1/assign", json={"route_id": "r1"}).status_code == 401


def test_orders_assign(dispatcher_client):
    resp = dispatcher_client.post("/api/orders/order-1/assign", json={"route_id": "r1", "rider_id": "rider-1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["order_id"] == "order-1"
    assert body["status"] == "assigned"
