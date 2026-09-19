"""T1.9 HTTP-level checks: /sw.js served from root with the right content type
and no-cache header, and the push endpoints round-trip.
"""

from fastapi.testclient import TestClient

from api.main import app
from core.db.client import get_session

client = TestClient(app)

RIDER_ID = "test-rider-push-http-1"
ENDPOINT = "https://push.example.invalid/test-endpoint-http-1"


def _cleanup():
    with get_session() as session:
        session.run(
            """
            MATCH (rd:Rider {id: $rider_id})
            OPTIONAL MATCH (rd)-[:HAS_SUBSCRIPTION]->(ps:PushSub)
            DETACH DELETE rd, ps
            """,
            rider_id=RIDER_ID,
        )


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


def test_push_subscribe_endpoint():
    try:
        resp = client.post(
            "/api/push/subscribe",
            json={
                "rider_id": RIDER_ID,
                "subscription": {
                    "endpoint": ENDPOINT,
                    "keys": {"p256dh": "fake-p256dh", "auth": "fake-auth"},
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "subscribed"
    finally:
        _cleanup()
