"""T1.9 tests. Subscribe/lookup are integration tests against real AuraDB;
send_to_rider's actual HTTP delivery is mocked (pywebpush.webpush) rather than
hitting a real push service, since there's no real browser subscription to
push to in a test run - only the removal-on-410 behavior is under test here.
"""

import pywebpush
import pytest

import core.alerts.push as push_module
from core.db.client import get_session
from core.schemas.push import PushSubscribeRequest, PushSubscription, PushSubscriptionKeys

RIDER_ID = "test-rider-push-1"
ENDPOINT = "https://push.example.invalid/test-endpoint-1"


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


@pytest.fixture
def subscription():
    req = PushSubscribeRequest(
        rider_id=RIDER_ID,
        subscription=PushSubscription(
            endpoint=ENDPOINT,
            keys=PushSubscriptionKeys(p256dh="fake-p256dh", auth="fake-auth"),
        ),
    )
    try:
        yield req
    finally:
        _cleanup()


def test_subscribe_creates_pushsub_and_relationship(subscription):
    resp = push_module.subscribe(subscription)
    assert resp.status == "subscribed"

    with get_session() as session:
        record = session.run(
            """
            MATCH (rd:Rider {id: $rider_id})-[:HAS_SUBSCRIPTION]->(ps:PushSub {endpoint: $endpoint})
            RETURN ps.p256dh AS p256dh, ps.auth AS auth
            """,
            rider_id=RIDER_ID,
            endpoint=ENDPOINT,
        ).single()
    assert record is not None
    assert record["p256dh"] == "fake-p256dh"
    assert record["auth"] == "fake-auth"


def test_get_vapid_public_key_returns_configured_key():
    key = push_module.get_vapid_public_key()
    assert isinstance(key, str) and len(key) > 0


def test_send_to_rider_removes_subscription_on_410(subscription, monkeypatch):
    push_module.subscribe(subscription)

    class FakeResponse:
        status_code = 410

    def fake_webpush(**kwargs):
        raise pywebpush.WebPushException("gone", response=FakeResponse())

    monkeypatch.setattr(push_module, "webpush", fake_webpush)

    sent = push_module.send_to_rider(RIDER_ID, {"title": "Spike ahead", "body": "Reroute available"})
    assert sent == 0

    with get_session() as session:
        record = session.run(
            "MATCH (ps:PushSub {endpoint: $endpoint}) RETURN ps", endpoint=ENDPOINT
        ).single()
    assert record is None
