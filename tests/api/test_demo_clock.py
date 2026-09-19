"""T1.6 integration tests: the derived clock persisted in real AuraDB.

Hits the live Neo4j configured in .env (per CLAUDE.md, state lives in Neo4j,
not local files) - these are integration tests, not unit tests.
"""

from fastapi.testclient import TestClient

from api.main import app
from tests.helpers import DISPATCHER, RIDER_1, signed_in

client = signed_in(DISPATCHER)


def test_clock_controls_are_dispatcher_only():
    assert TestClient(app).get("/api/demo/clock").status_code == 401
    rider = signed_in(RIDER_1)
    assert rider.post("/api/demo/clock", json={"action": "pause"}).status_code == 403
    # riders can still read the replay time
    assert rider.get("/api/clock").status_code == 200


def test_get_clock_returns_bounds_from_real_zone_readings():
    resp = client.get("/api/demo/clock")
    assert resp.status_code == 200
    body = resp.json()
    assert body["min_ts"] < body["max_ts"]
    assert body["min_ts"] <= body["now_ts"] or not body["running"]


def test_set_speed_is_clamped():
    resp = client.post("/api/demo/clock", json={"action": "set_speed", "speed": 99999})
    assert resp.status_code == 200
    assert resp.json()["speed"] == 600


def test_jump_is_clamped_to_replay_window():
    # pause first so a running clock's elapsed-time drift can't make now_ts
    # overshoot min_ts between the write and the read inside apply_action
    client.post("/api/demo/clock", json={"action": "pause"})
    resp = client.post("/api/demo/clock", json={"action": "jump", "to": "1999-01-01T00:00:00Z"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["now_ts"] == body["min_ts"]


def test_pause_then_resume():
    paused = client.post("/api/demo/clock", json={"action": "pause"}).json()
    assert paused["running"] is False
    frozen_ts = paused["now_ts"]

    still_paused = client.get("/api/demo/clock").json()
    assert still_paused["now_ts"] == frozen_ts

    resumed = client.post("/api/demo/clock", json={"action": "resume"}).json()
    assert resumed["running"] is True


def test_set_speed_without_speed_is_400():
    resp = client.post("/api/demo/clock", json={"action": "set_speed"})
    assert resp.status_code == 400


def test_jump_without_to_is_400():
    resp = client.post("/api/demo/clock", json={"action": "jump"})
    assert resp.status_code == 400
