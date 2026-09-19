"""Shared globals for every Streamlit page (T2.2): replay clock bar, severity
legend, confidence/Simulated badges, Data-and-method link. State lives in
st.session_state + Neo4j, not module globals (CLAUDE.md architecture rule 3
- Streamlit reruns on every interaction).
"""

from __future__ import annotations

import streamlit as st

from core.schemas.demo import MAX_SPEED, MIN_SPEED, ClockActionRequest
from ui import services

BAND_COLORS: dict[str, str] = {
    "good": "#4caf50",
    "satisfactory": "#a3d977",
    "moderate": "#f6c445",
    "poor": "#f28c3a",
    "very_poor": "#e5533d",
    "severe": "#8b1e3f",
}

BAND_RGB: dict[str, list[int]] = {
    "good": [76, 175, 80],
    "satisfactory": [163, 217, 119],
    "moderate": [246, 196, 69],
    "poor": [242, 140, 58],
    "very_poor": [229, 83, 61],
    "severe": [139, 30, 63],
}

BAND_LABELS: dict[str, str] = {
    "good": "Good",
    "satisfactory": "Satisfactory",
    "moderate": "Moderate",
    "poor": "Poor",
    "very_poor": "Very poor",
    "severe": "Severe",
}


def configure_page(title: str) -> None:
    st.set_page_config(page_title=f"{title} - Exposure-Aware Fleet Routing", layout="wide")


def render_replay_bar() -> None:
    state = services.get_clock_state()

    with st.container(border=True):
        cols = st.columns([2, 1, 1, 1, 1, 2])
        cols[0].markdown(
            f":orange-badge[Replay] **{state.now_ts:%Y-%m-%d %H:%M}** "
            f"(replay window {state.min_ts:%Y-%m-%d} to {state.max_ts:%Y-%m-%d})"
        )

        if cols[1].button("Pause" if state.running else "Resume", key="clock_toggle"):
            action = "pause" if state.running else "resume"
            services.update_clock(ClockActionRequest(action=action))
            st.rerun()

        speed = cols[2].selectbox(
            "Speed",
            options=[1, 30, 60, 120, 300, 600],
            index=[1, 30, 60, 120, 300, 600].index(state.speed) if state.speed in (1, 30, 60, 120, 300, 600) else 2,
            key="clock_speed",
            label_visibility="collapsed",
        )
        if speed != state.speed:
            services.update_clock(ClockActionRequest(action="set_speed", speed=speed))
            st.rerun()

        if cols[3].button("Jump to start", key="clock_jump_start"):
            services.update_clock(ClockActionRequest(action="jump", to=state.min_ts))
            st.rerun()

        if cols[4].button("Reset spikes", key="clock_reset_spikes"):
            services.clear_spikes()
            st.rerun()

        mode = "Mocked data" if services.using_mocks() else "Live core/ + Neo4j"
        cols[5].markdown(f":gray-badge[{mode}]")

    st.caption(
        "This demo **replays historical PM2.5 data** on the clock above; only traffic/routing "
        "is live from today. Speed is clamped to "
        f"{MIN_SPEED}–{MAX_SPEED}x."
    )


def render_legend() -> None:
    chips = " &nbsp; ".join(
        f'<span style="background:{BAND_COLORS[b]};color:#111;border-radius:10px;'
        f'padding:2px 10px;font-size:0.8rem;font-weight:600;">{BAND_LABELS[b]}</span>'
        for b in BAND_COLORS
    )
    st.markdown(chips, unsafe_allow_html=True)
    st.caption(
        "Coverage below 80% is shown as low confidence. Scores show exposure reduction - "
        "never a health or medical claim."
    )


def confidence_badge(confidence: str, simulated: bool) -> str:
    parts = [f":gray-badge[{confidence} confidence]"]
    if simulated:
        parts.append(":orange-badge[Simulated]")
    return " ".join(parts)


def render_data_and_method() -> None:
    with st.expander("Data and method"):
        st.markdown(
            "- PM2.5 zones come from a historical sensor dataset (Delhi NCR), aggregated to "
            "15-minute buckets and **replayed** on the clock above - not live pollution data.\n"
            "- Google traffic and routing are **live** from today; only the pollution layer is replayed.\n"
            "- Readings labeled **Simulated** are spikes injected for this demo, not real sensor data.\n"
            "- Zone confidence: 2+ sensors = high, 1 sensor = medium, 0 sensors = zone excluded.\n"
            "- Dose is a relative exposure figure (ug·h/m3), not a health or medical score."
        )
