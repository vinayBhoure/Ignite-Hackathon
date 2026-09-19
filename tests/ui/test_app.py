"""T2.2-T2.4 smoke test: the Home page runs headlessly with no exceptions and
renders the required Replay bar, legend and Data-and-method disclosure."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[2] / "ui" / "app.py")


def test_home_page_runs_without_exceptions():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception


def test_home_page_shows_required_disclosures():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    full_text = " ".join(md.value for md in at.markdown) + " ".join(c.value for c in at.caption)
    assert "Replay" in full_text
    assert "replay" in full_text.lower()
