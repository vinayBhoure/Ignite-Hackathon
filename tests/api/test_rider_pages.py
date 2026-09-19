"""Rider app pages: signed-in riders only, Aevora-themed, with the Replay
disclosure and Data-and-method note the PRD requires on every screen."""

from fastapi.testclient import TestClient

from api.main import app
from tests.helpers import DISPATCHER, signed_in

anon = TestClient(app)


def test_rider_pages_redirect_to_rider_sign_in_when_signed_out():
    for path in ("/rider", "/rider/settings", "/rider/order/ord-x"):
        resp = anon.get(path, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/?role=rider"


def test_dispatcher_session_does_not_open_rider_pages():
    resp = signed_in(DISPATCHER).get("/rider", follow_redirects=False)
    assert resp.status_code == 303


def test_rider_home_renders_with_disclosures(rider_client):
    resp = rider_client.get("/rider")
    assert resp.status_code == 200
    assert "Replay" in resp.text and "replayed" in resp.text
    assert "Data and method" in resp.text
    assert "/static/aevora.css" in resp.text
    assert "Rider 1" in resp.text


def test_rider_navigation_page_renders(rider_client):
    resp = rider_client.get("/rider/order/ord-123")
    assert resp.status_code == 200
    assert '"ord-123"' in resp.text
    assert "/static/nav.js" in resp.text


def test_rider_settings_renders(rider_client):
    resp = rider_client.get("/rider/settings")
    assert resp.status_code == 200
    assert "Data and method" in resp.text
    assert "/logout?role=rider" in resp.text


def test_static_assets_served():
    assert "enablePush" in anon.get("/static/rider.js").text
    assert "AEVORA_init" in anon.get("/static/nav.js").text
    assert anon.get("/static/aevora.css").status_code == 200
    assert anon.get("/static/manifest.json").json()["start_url"] == "/rider"
