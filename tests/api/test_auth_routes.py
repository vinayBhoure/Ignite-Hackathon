"""Login page, per-role cookies and role separation over HTTP."""

from fastapi.testclient import TestClient

from api.main import app
from tests.helpers import DISPATCHER, RIDER_1, signed_in


def test_login_page_is_the_wired_aevora_page():
    resp = TestClient(app).get("/")
    assert resp.status_code == 200
    assert "Aevora" in resp.text and 'id="loginForm"' in resp.text


def test_bad_credentials_return_the_error_envelope():
    resp = TestClient(app).post("/api/auth/login", json={**DISPATCHER, "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["error"]["message"]


def test_dispatcher_is_handed_to_the_console_with_a_token():
    resp = TestClient(app).post("/api/auth/login", json=DISPATCHER)
    assert resp.status_code == 200
    assert "/?token=" in resp.json()["redirect"]
    assert "aevora_dispatcher" in resp.cookies


def test_rider_lands_on_the_rider_app():
    resp = TestClient(app).post("/api/auth/login", json=RIDER_1)
    assert resp.json()["redirect"] == "/rider"
    assert "aevora_rider" in resp.cookies


def test_both_roles_can_be_signed_in_side_by_side():
    client = signed_in(DISPATCHER)
    client.post("/api/auth/login", json=RIDER_1)
    assert client.get("/rider").status_code == 200
    assert client.get("/api/demo/clock").status_code == 200
    assert client.get("/api/auth/me").json()["role"] == "rider"


def test_signed_in_users_skip_the_form_unless_switching():
    rider = signed_in(RIDER_1)
    assert rider.get("/?role=rider", follow_redirects=False).headers["location"] == "/rider"
    assert rider.get("/?role=rider&switch=1").status_code == 200


def test_logout_by_role():
    client = signed_in(DISPATCHER)
    client.post("/api/auth/login", json=RIDER_1)
    client.get("/logout?role=rider")
    assert client.get("/rider", follow_redirects=False).status_code == 303
    assert client.get("/api/demo/clock").status_code == 200
    client.get("/logout")
    assert client.get("/api/demo/clock").status_code == 401


def test_bearer_token_works_for_the_console_map(dispatcher_token):
    client = TestClient(app)
    assert client.get("/api/fleet/live").status_code == 401
    ok = client.get("/api/fleet/live", headers={"Authorization": f"Bearer {dispatcher_token}"})
    assert ok.status_code == 200
    rider = signed_in(RIDER_1)
    assert rider.get("/api/fleet/live").status_code == 403
