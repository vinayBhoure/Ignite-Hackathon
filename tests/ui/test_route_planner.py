"""T2.5-T2.7 smoke tests: route planner page runs headlessly, resolves a
known landmark unambiguously, and a search produces a comparison."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGE_PATH = str(Path(__file__).resolve().parents[2] / "ui" / "pages" / "1_Route_Planner.py")


def test_route_planner_loads_without_exceptions():
    at = AppTest.from_file(PAGE_PATH, default_timeout=30)
    at.run()
    assert not at.exception


def test_search_known_landmarks_produces_comparison():
    at = AppTest.from_file(PAGE_PATH, default_timeout=30)
    at.run()

    inputs = at.text_input
    inputs[0].input("cp")
    inputs[1].input("cyber hub")
    # render_replay_bar() renders its own buttons first, so find the submit
    # button by label rather than assuming it's at.button[0]
    submit = next(b for b in at.button if b.label == "Find routes")
    submit.click().run()

    assert not at.exception
    full_text = " ".join(md.value for md in at.markdown) + " ".join(m.label for m in at.metric)
    assert "Time" in full_text or len(at.metric) > 0
