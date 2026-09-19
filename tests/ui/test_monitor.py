"""T2.8-T2.9 smoke test: Monitor page (zones/AQI inspector + alert log)
runs headlessly with no exceptions."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGE_PATH = str(Path(__file__).resolve().parents[2] / "ui" / "pages" / "2_Monitor.py")


def test_monitor_page_runs_without_exceptions():
    at = AppTest.from_file(PAGE_PATH, default_timeout=30)
    at.run()
    assert not at.exception


def test_monitor_alerts_tab_status_filter_works():
    at = AppTest.from_file(PAGE_PATH, default_timeout=30)
    at.run()
    assert not at.exception
    # selectbox[0] is the "Status" filter (after any selects on the zones tab widgets)
    status_selects = [s for s in at.selectbox if s.label == "Status"]
    assert len(status_selects) == 1
    status_selects[0].select("acked").run()
    assert not at.exception
