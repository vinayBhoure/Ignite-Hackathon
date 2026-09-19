"""Alert evaluator (T1.8). PRD: "the evaluator runs on every replay tick and
skips an alert if the same rider and zone already alerted within 15 minutes
of replay time." Triggered by GET /api/alerts (once per dashboard refresh) -
no separate background scheduler for the MVP; see commit message for why.

Graph shape (PRD §12): Rider-[:ASSIGNED]->Order-[:HAS_CANDIDATE]->Route
{selected:true}-[:PASSES_THROUGH {bucket}]->Zone, ZoneReading{h3, ts=bucket}.
Alert's PRD key properties are id/type/severity/ts/status; h3 and order_id
are added here for dedup/filtering - additive, not in the frozen list but
not forbidden either.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from core.clock.demo_clock import get_state
from core.db.client import get_session, to_utc
from core.schemas.alerts import AlertAckResponse, AlertOut
from core.schemas.common import severity_band_for

ALERT_THRESHOLD_PM25 = 120.0
DEDUPE_MINUTES = 15

_CANDIDATES_QUERY = """
MATCH (rd:Rider)-[:ASSIGNED]->(o:Order)-[:HAS_CANDIDATE]->(rt:Route {selected: true})
      -[p:PASSES_THROUGH]->(z:Zone)
MATCH (zr:ZoneReading {h3: z.h3, ts: p.bucket})
WHERE zr.pm25 > $threshold
RETURN DISTINCT rd.id AS rider_id, o.id AS order_id, z.h3 AS h3, zr.pm25 AS pm25
"""

_RECENT_ALERT_QUERY = """
MATCH (a:Alert {h3: $h3})-[:ABOUT]->(rd:Rider {id: $rider_id})
WHERE a.ts >= $since
RETURN a.id AS id
LIMIT 1
"""

_LIST_QUERY = """
MATCH (a:Alert)
OPTIONAL MATCH (a)-[:ABOUT]->(rd:Rider)
WITH a, rd
WHERE ($status IS NULL OR a.status = $status)
  AND ($rider_id IS NULL OR rd.id = $rider_id)
RETURN a.id AS id, a.type AS type, a.severity AS severity, a.ts AS ts,
       a.status AS status, a.order_id AS order_id, rd.id AS rider_id, a.h3 AS h3
ORDER BY a.ts DESC
"""


def run_tick() -> list[AlertOut]:
    """Evaluate every active route once; create and return the new Alerts."""
    now = get_state().now_ts
    since = now - timedelta(minutes=DEDUPE_MINUTES)
    created: list[AlertOut] = []

    with get_session() as session:
        candidates = list(session.run(_CANDIDATES_QUERY, threshold=ALERT_THRESHOLD_PM25))

        for row in candidates:
            rider_id, order_id, h3, pm25 = (
                row["rider_id"],
                row["order_id"],
                row["h3"],
                row["pm25"],
            )
            dup = session.run(
                _RECENT_ALERT_QUERY, h3=h3, rider_id=rider_id, since=since
            ).single()
            if dup is not None:
                continue

            alert_id = uuid.uuid4().hex[:12]
            severity = severity_band_for(pm25)
            session.run(
                """
                MATCH (rd:Rider {id: $rider_id})
                CREATE (a:Alert {
                    id: $id, type: 'spike', severity: $severity, ts: $ts,
                    status: 'new', h3: $h3, order_id: $order_id
                })-[:ABOUT]->(rd)
                """,
                rider_id=rider_id,
                id=alert_id,
                severity=severity,
                ts=now,
                h3=h3,
                order_id=order_id,
            )
            created.append(
                AlertOut(
                    id=alert_id,
                    type="spike",
                    severity=severity,
                    ts=now,
                    status="new",
                    order_id=order_id,
                    rider_id=rider_id,
                    h3=h3,
                )
            )

    return created


def list_alerts(status: str | None = None, rider_id: str | None = None) -> list[AlertOut]:
    run_tick()
    with get_session() as session:
        rows = session.run(_LIST_QUERY, status=status, rider_id=rider_id)
        return [
            AlertOut(
                id=row["id"],
                type=row["type"],
                severity=row["severity"],
                ts=to_utc(row["ts"]),
                status=row["status"],
                order_id=row["order_id"],
                rider_id=row["rider_id"],
                h3=row["h3"],
            )
            for row in rows
        ]


def ack_alert(alert_id: str) -> AlertAckResponse:
    with get_session() as session:
        record = session.run(
            """
            MATCH (a:Alert {id: $id})
            SET a.status = 'acked'
            RETURN a.id AS id, a.status AS status
            """,
            id=alert_id,
        ).single()

    if record is None:
        raise LookupError(f"alert {alert_id} not found")
    return AlertAckResponse(id=record["id"], status=record["status"])
