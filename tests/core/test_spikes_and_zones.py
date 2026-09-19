"""T1.7 integration tests against real AuraDB: spike injection overrides the
sensor value for the same (h3, bucket), reset clears it, and get_zones()
merges simulated with real readings and follows the replay clock by default.
"""

from datetime import datetime, timezone

import h3

from core.clock.demo_clock import apply_action, get_state
from core.clock.spikes import inject_spike, reset_spikes
from core.clock.zones import get_zones
from core.schemas.demo import ClockActionRequest, SpikeRequest

TEST_H3 = h3.latlng_to_cell(28.6315, 77.2167, 8)  # Connaught Place, matches ETL H3_RES=8


def _pause_at(ts: datetime) -> None:
    apply_action(ClockActionRequest(action="jump", to=ts))
    apply_action(ClockActionRequest(action="pause"))


def test_spike_overrides_sensor_reading_and_reset_clears_it():
    min_ts = get_state().min_ts
    _pause_at(min_ts)

    before = get_zones(ts=min_ts)
    before_zone = next((z for z in before.zones if z.h3 == TEST_H3), None)

    resp = inject_spike(SpikeRequest(h3=TEST_H3, pm25=300.0, duration_min=15))
    assert resp.buckets_written == 1
    assert resp.source == "simulated"

    after = get_zones(ts=min_ts)
    spiked_zone = next(z for z in after.zones if z.h3 == TEST_H3)
    assert spiked_zone.simulated is True
    assert spiked_zone.pm25 == 300.0
    assert spiked_zone.band == "severe"

    cleared = reset_spikes()
    assert cleared.spikes_cleared >= 1

    restored = get_zones(ts=min_ts)
    restored_zone = next((z for z in restored.zones if z.h3 == TEST_H3), None)
    if before_zone is None:
        assert restored_zone is None
    else:
        assert restored_zone.simulated is False


def test_get_zones_defaults_to_current_clock_time():
    known_ts = datetime(2021, 1, 10, 0, 0, tzinfo=timezone.utc)
    _pause_at(known_ts)
    resp = get_zones()  # no ts passed - should use the paused clock's now
    assert resp.ts == get_state().now_ts
