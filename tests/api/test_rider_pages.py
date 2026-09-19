"""T1.10 checks: rider pages render, static assets are served, and the
"Replay" disclosure required on every screen is present."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_rider_home_renders_with_replay_disclosure():
    resp = client.get("/rider")
    assert resp.status_code == 200
    assert "Replay" in resp.text
    assert "Simulated" in resp.text or "replayed" in resp.text
    assert "enable-push" in resp.text


def test_rider_order_page_renders():
    resp = client.get("/rider/order/order-123")
    assert resp.status_code == 200
    assert "order-123" in resp.text


def test_rider_settings_renders():
    resp = client.get("/rider/settings")
    assert resp.status_code == 200
    assert "Data and method" in resp.text


def test_static_rider_js_served():
    resp = client.get("/static/rider.js")
    assert resp.status_code == 200
    assert "subscribeToPush" in resp.text


def test_static_manifest_served():
    resp = client.get("/static/manifest.json")
    assert resp.status_code == 200
    assert resp.json()["start_url"] == "/rider"
