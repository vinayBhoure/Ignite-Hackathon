"""Console smoke tests (headless Streamlit): the dispatcher gate, and every
view runs cleanly with the Replay disclosure. Mock providers (conftest), so
no Google calls; the replay clock and riders are real Neo4j reads."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[2] / "ui" / "app.py")


def _text(at) -> str:
    return " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)


def _signed_in(token: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["token"] = token
    at.run()
    return at


def test_console_requires_dispatcher_sign_in():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    assert "sign-in required" in _text(at)
    assert not any(b.label == "Play" or b.label == "Pause" for b in at.button)


def test_rider_token_does_not_open_the_console():
    from core.auth import authenticate, issue_token

    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["token"] = issue_token(authenticate("rider", "9900000001", "aevora-rider"))
    at.run()
    assert "sign-in required" in _text(at)


def test_live_fleet_view(dispatcher_token):
    at = _signed_in(dispatcher_token)
    assert not at.exception
    text = _text(at)
    assert "Replay" in text and "Live fleet" in text
    assert "Dispatch Desk" in text


def test_dispatch_view_plans_and_compares(dispatcher_token):
    at = _signed_in(dispatcher_token)
    at.switch_page("views/dispatch.py").run()
    assert not at.exception
    at.text_input[1].input("cp")
    next(b for b in at.button if b.label == "Find cleanest route").click().run()
    assert not at.exception
    text = _text(at)
    assert "Compare routes" in text
    for label in ("Time", "Dose", "Window margin", "Coverage"):
        assert label in text  # shown separately, never blended


def test_air_and_alerts_view(dispatcher_token):
    at = _signed_in(dispatcher_token)
    at.switch_page("views/monitor.py").run()
    assert not at.exception
    status = next(s for s in at.selectbox if s.label == "Status")
    status.select("acked").run()
    assert not at.exception
