"""T1.8 integration test against real AuraDB: seeds a minimal active route
(Rider-ASSIGNED->Order-HAS_CANDIDATE->Route-PASSES_THROUGH->Zone per PRD §12),
spikes that zone, and checks the evaluator creates exactly one Alert, dedupes
a second tick, and that ack() updates status. Cleans up everything it seeds.
"""

import pytest

from core.alerts.evaluator import ack_alert, list_alerts, run_tick
from core.clock.demo_clock import apply_action
from core.clock.math import floor_to_bucket
from core.clock.spikes import inject_spike, reset_spikes
from core.db.client import get_session
from core.schemas.demo import ClockActionRequest, SpikeRequest

RIDER_ID = "test-rider-eval-1"
ORDER_ID = "test-order-eval-1"
ROUTE_ID = "test-route-eval-1"


def _pick_real_zone_h3() -> str:
    with get_session() as session:
        record = session.run("MATCH (z:Zone) RETURN z.h3 AS h3 LIMIT 1").single()
    return record["h3"]


def _seed_active_route(h3: str, bucket) -> None:
    with get_session() as session:
        session.run(
            """
            MERGE (rd:Rider {id: $rider_id})
            MERGE (o:Order {id: $order_id})
            MERGE (rt:Route {id: $route_id})
            SET rt.selected = true
            MERGE (z:Zone {h3: $h3})
            MERGE (rd)-[:ASSIGNED]->(o)
            MERGE (o)-[:HAS_CANDIDATE]->(rt)
            MERGE (rt)-[p:PASSES_THROUGH]->(z)
            SET p.idx = 0, p.seconds = 300, p.bucket = $bucket
            """,
            rider_id=RIDER_ID,
            order_id=ORDER_ID,
            route_id=ROUTE_ID,
            h3=h3,
            bucket=bucket,
        )


def _cleanup(h3: str) -> None:
    reset_spikes()
    with get_session() as session:
        session.run(
            """
            MATCH (a:Alert)-[:ABOUT]->(rd:Rider {id: $rider_id})
            DETACH DELETE a
            """,
            rider_id=RIDER_ID,
        )
        session.run(
            """
            MATCH (rd:Rider {id: $rider_id})
            OPTIONAL MATCH (rd)-[:ASSIGNED]->(o:Order {id: $order_id})
            OPTIONAL MATCH (o)-[:HAS_CANDIDATE]->(rt:Route {id: $route_id})
            DETACH DELETE rd, o, rt
            """,
            rider_id=RIDER_ID,
            order_id=ORDER_ID,
            route_id=ROUTE_ID,
        )


@pytest.fixture
def active_route():
    h3 = _pick_real_zone_h3()
    # pause *before* jumping: jump doesn't change `running`, so jumping while
    # a leftover high speed is still running can drift `now_ts` a few hundred
    # ms past the exact target by the time this call returns - enough to miss
    # the 15-min bucket-equality match against the spike's floored reading.
    apply_action(ClockActionRequest(action="pause"))
    clock = apply_action(ClockActionRequest(action="jump", to="2021-01-10T00:00:00Z"))
    bucket = floor_to_bucket(clock.now_ts)
    _seed_active_route(h3, bucket)
    inject_spike(SpikeRequest(h3=h3, pm25=300.0, duration_min=15))
    try:
        yield h3
    finally:
        _cleanup(h3)


def test_spike_on_active_route_creates_one_alert_and_dedupes(active_route):
    created = run_tick()
    matching = [a for a in created if a.rider_id == RIDER_ID]
    assert len(matching) == 1
    assert matching[0].severity == "severe"
    assert matching[0].status == "new"

    again = run_tick()
    assert not [a for a in again if a.rider_id == RIDER_ID]

    listed = list_alerts(rider_id=RIDER_ID)
    assert len(listed) == 1
    assert listed[0].id == matching[0].id


def test_ack_updates_status(active_route):
    run_tick()
    listed = list_alerts(rider_id=RIDER_ID)
    assert len(listed) == 1

    ack_resp = ack_alert(listed[0].id)
    assert ack_resp.status == "acked"

    still_new = list_alerts(status="new", rider_id=RIDER_ID)
    assert still_new == []
