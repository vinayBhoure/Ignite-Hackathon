"""T1.9 HTTP-level checks: /sw.js served from root with the right content type
and no-cache header, and the push endpoints round-trip.
"""

from fastapi.testclient import TestClient

from api.main import app
from core.db.client import get_session
from tests.helpers import RIDER_1, signed_in

client = TestClient(app)

SPOOFED_RIDER_ID = "someone-else"
ENDPOINT = "https://push.example.invalid/test-endpoint-http-1"


def _cleanup():
    # Only the test subscription - rider-1 is real seeded data.
    with get_session() as session:
        session.run("MATCH (ps:PushSub {endpoint: $e}) DETACH DELETE ps", e=ENDPOINT)
        session.run("MATCH (rd:Rider {id: $id}) DETACH DELETE rd", id=SPOOFED_RIDER_ID)


def test_sw_js_served_from_root_with_correct_headers():
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/javascript") or resp.headers[
        "content-type"
    ].startswith("text/javascript")
    assert resp.headers["cache-control"] == "no-cache"
    assert b"addEventListener" in resp.content


def test_vapid_public_key_endpoint():
    resp = client.get("/api/push/vapid-public-key")
    assert resp.status_code == 200
    assert len(resp.json()["public_key"]) > 0


BODY = {
    "rider_id": SPOOFED_RIDER_ID,
    "subscription": {"endpoint": ENDPOINT, "keys": {"p256dh": "fake-p256dh", "auth": "fake-auth"}},
}


def test_push_subscribe_requires_rider():
    assert client.post("/api/push/subscribe", json=BODY).status_code == 401


def test_push_subscribe_binds_to_signed_in_rider_not_body():
    rider = signed_in(RIDER_1)
    try:
        resp = rider.post("/api/push/subscribe", json=BODY)
        assert resp.status_code == 200
        assert resp.json()["status"] == "subscribed"
        with get_session() as session:
            owner = session.run(
                "MATCH (rd:Rider)-[:HAS_SUBSCRIPTION]->(:PushSub {endpoint: $e}) RETURN rd.id AS id", e=ENDPOINT
            ).single()
        assert owner["id"] == "rider-1"
    finally:
        _cleanup()
