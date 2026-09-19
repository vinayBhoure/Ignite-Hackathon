"""Web push (T1.9). Subscriptions stored as PushSub nodes, linked to Rider via
HAS_SUBSCRIPTION (PRD §12). Never log or print subscription endpoints or keys
(CLAUDE.md working rules) - failures below log only the status class, never
the subscription_info dict.
"""

from __future__ import annotations

import json
import os

from pywebpush import WebPushException, webpush

from core.db.client import get_session
from core.schemas.push import PushSubscribeRequest, PushSubscribeResponse

FALLBACK_STATUS_CODES = (404, 410)  # gone/expired - the plan's "removed" criterion


class MissingVapidConfig(RuntimeError):
    pass


def get_vapid_public_key() -> str:
    key = os.getenv("VAPID_PUBLIC_KEY")
    if not key:
        raise MissingVapidConfig(
            "VAPID_PUBLIC_KEY not set - run scripts/generate_vapid_keys.py and add it to .env"
        )
    return key


def subscribe(req: PushSubscribeRequest) -> PushSubscribeResponse:
    # Neo4j node properties must be primitives (or arrays thereof), so the
    # PushSub's keys map is stored flattened rather than as a nested object.
    with get_session() as session:
        session.run(
            """
            MERGE (rd:Rider {id: $rider_id})
            MERGE (ps:PushSub {endpoint: $endpoint})
            ON CREATE SET ps.created_at = datetime()
            SET ps.p256dh = $p256dh, ps.auth = $auth
            MERGE (rd)-[:HAS_SUBSCRIPTION]->(ps)
            """,
            rider_id=req.rider_id,
            endpoint=req.subscription.endpoint,
            p256dh=req.subscription.keys.p256dh,
            auth=req.subscription.keys.auth,
        )
    return PushSubscribeResponse()


def send_to_rider(rider_id: str, payload: dict) -> int:
    """Send payload to every subscription for this rider. Removes any
    subscription the push service reports as gone (404/410). Returns the
    number of subscriptions successfully pushed to.
    """
    private_key = os.getenv("VAPID_PRIVATE_KEY")
    subject = os.getenv("VAPID_SUBJECT")
    if not private_key or not subject:
        raise MissingVapidConfig("VAPID_PRIVATE_KEY/VAPID_SUBJECT not set - see .env.example")

    with get_session() as session:
        rows = list(
            session.run(
                """
                MATCH (rd:Rider {id: $rider_id})-[:HAS_SUBSCRIPTION]->(ps:PushSub)
                RETURN ps.endpoint AS endpoint, ps.p256dh AS p256dh, ps.auth AS auth
                """,
                rider_id=rider_id,
            )
        )

    sent = 0
    for row in rows:
        subscription_info = {
            "endpoint": row["endpoint"],
            "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
            )
            sent += 1
        except WebPushException as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code in FALLBACK_STATUS_CODES:
                _remove_subscription(row["endpoint"])

    return sent


def _remove_subscription(endpoint: str) -> None:
    with get_session() as session:
        session.run("MATCH (ps:PushSub {endpoint: $endpoint}) DETACH DELETE ps", endpoint=endpoint)
