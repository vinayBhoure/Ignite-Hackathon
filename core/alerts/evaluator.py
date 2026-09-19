"""Alert evaluator (T1.8). PRD: "the evaluator runs on every replay tick and
skips an alert if the same rider and zone already alerted within 15 minutes
of replay time." Triggered by dashboard refreshes and, throttled, by the
rider navigation poll - no separate background scheduler for the MVP.

Graph shape (PRD §12): Rider-[:ASSIGNED]->Order-[:HAS_CANDIDATE]->Route
{selected:true}-[:PASSES_THROUGH {bucket}]->Zone, ZoneReading{h3, ts=bucket}.
Alert's PRD key properties are id/type/severity/ts/status; h3 and order_id
are added here for dedup/filtering - additive, not in the frozen list but
not forbidden either.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import timedelta

from core.clock.demo_clock import get_state
from core.clock.math import floor_to_bucket
from core.db.client import get_session, to_data_tz, to_utc
from core.schemas.alerts import AlertAckResponse, AlertOut
from core.schemas.common import severity_band_for

ALERT_THRESHOLD_PM25 = 120.0
DEDUPE_MINUTES = 15
TICK_MIN_INTERVAL_S = 3.0

logger = logging.getLogger("alerts")
_last_tick = 0.0
_tick_lock = threading.Lock()

# Only zones the rider hasn't reached yet (arrival bucket at or after the
# current replay bucket) on orders that aren't delivered - a spike behind the
# rider can't be avoided, so it shouldn't prompt a reroute.
#
# "Crosses the threshold" (PRD scenario 2): when the route stored the PM2.5 it
# was planned against (pm25_planned), alert only if the zone is now above 120
# and either was at/below 120 at planning or has risen >= 25% since. Replayed
# history was already priced into the route choice; in January Delhi nearly
# every zone sits above 120, so alerting on it would fire on every ride.
# Routes without pm25_planned (seeded elsewhere) keep plain threshold alerts.
_CANDIDATES_QUERY = """
MATCH (rd:Rider)-[:ASSIGNED]->(o:Order)-[:HAS_CANDIDATE]->(rt:Route {selected: true})
      -[p:PASSES_THROUGH]->(z:Zone)
WHERE coalesce(o.status, 'assigned') <> 'delivered' AND p.bucket >= $now_bucket
MATCH (zr:ZoneReading {h3: z.h3, ts: p.bucket})
WITH rd, o, z, p, zr ORDER BY CASE zr.source WHEN 'simulated' THEN 0 ELSE 1 END
WITH rd, o, z, p, collect(zr)[0] AS top
WHERE top.pm25 > $threshold
  AND (p.pm25_planned IS NULL OR p.pm25_planned <= $threshold OR top.pm25 >= p.pm25_planned * $rise)
RETURN DISTINCT rd.id AS rider_id, o.id AS order_id, z.h3 AS h3, top.pm25 AS pm25,
       top.source = 'simulated' AS simulated
"""
WORSENED_RATIO = 1.25

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
       a.status AS status, a.order_id AS order_id, rd.id AS rider_id, a.h3 AS h3,
       coalesce(a.simulated, false) AS simulated
ORDER BY a.ts DESC
"""


def run_tick() -> list[AlertOut]:
    """Evaluate every active route once; create and return the new Alerts."""
    now = get_state().now_ts
    since = now - timedelta(minutes=DEDUPE_MINUTES)
    created: list[AlertOut] = []

    with get_session() as session:
        candidates = list(
            session.run(
                _CANDIDATES_QUERY,
                threshold=ALERT_THRESHOLD_PM25,
                rise=WORSENED_RATIO,
                now_bucket=to_data_tz(floor_to_bucket(now)),
            )
        )

        for row in candidates:
            rider_id, order_id, h3, pm25, simulated = (
                row["rider_id"],
                row["order_id"],
                row["h3"],
                row["pm25"],
                bool(row["simulated"]),
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
                    status: 'new', h3: $h3, order_id: $order_id, simulated: $simulated
                })-[:ABOUT]->(rd)
                """,
                rider_id=rider_id,
                id=alert_id,
                severity=severity,
                ts=now,
                h3=h3,
                order_id=order_id,
                simulated=simulated,
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
                    simulated=simulated,
                )
            )

    for alert in created:
        _push(alert)
    return created


def _push(alert: AlertOut) -> None:
    """Best-effort web push; the in-app feed (Alert node) is the fallback."""
    from core.alerts.push import MissingVapidConfig, send_to_rider

    try:
        send_to_rider(
            alert.rider_id,
            {
                "title": f"{alert.severity.replace('_', ' ').title()} air ahead on your route",
                "body": ("Simulated spike" if alert.simulated else "High PM2.5 reading")
                + " ahead. Open to see a cleaner reroute.",
                "url": f"/rider/order/{alert.order_id}",
            },
        )
    except MissingVapidConfig:
        pass
    except Exception:  # noqa: BLE001 - a push failure must never break alerting
        logger.exception("push delivery failed for alert %s", alert.id)


def maybe_tick() -> None:
    """Throttled tick for pages that poll every few seconds."""
    global _last_tick
    with _tick_lock:
        if time.monotonic() - _last_tick < TICK_MIN_INTERVAL_S:
            return
        _last_tick = time.monotonic()
    run_tick()


def list_alerts(status: str | None = None, rider_id: str | None = None, tick: bool = True) -> list[AlertOut]:
    if tick:
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
                simulated=row["simulated"],
            )
            for row in rows
        ]


def ack_alert(alert_id: str) -> AlertAckResponse:
    with get_session() as session:
        record = session.run(
            """
            MATCH (a:Alert {id: $id})
            SET a.status = 'acked', a.acked_ts = datetime()
            RETURN a.id AS id, a.status AS status
            """,
            id=alert_id,
        ).single()

    if record is None:
        raise LookupError(f"alert {alert_id} not found")
    return AlertAckResponse(id=record["id"], status=record["status"])
