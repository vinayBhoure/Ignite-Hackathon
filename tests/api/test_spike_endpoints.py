"""T1.7 HTTP-level check: POST /api/demo/spike and /api/demo/reset always hit
real core/clock (they don't go through the USE_MOCKS switch, unlike zones).
"""

import h3

from tests.helpers import DISPATCHER, signed_in

client = signed_in(DISPATCHER)

TEST_H3 = h3.latlng_to_cell(28.4950, 77.0890, 8)  # Cyber Hub, Gurugram


def test_spike_then_reset_over_http():
    resp = client.post("/api/demo/spike", json={"h3": TEST_H3, "pm25": 280, "duration_min": 15})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "simulated"
    assert body["buckets_written"] == 1

    reset_resp = client.post("/api/demo/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["spikes_cleared"] >= 1
