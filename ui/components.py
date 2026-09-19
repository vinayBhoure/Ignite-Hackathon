"""Shared console chrome: Aevora styling, dispatcher auth gate, replay bar,
severity legend, badges, Data-and-method. State lives in st.session_state +
Neo4j, never module globals (CLAUDE.md rule 3 - Streamlit reruns constantly).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st

from core.clock.demo_clock import DEMO_START
from core.schemas.demo import ClockActionRequest
from ui import services

IST = timezone(timedelta(hours=5, minutes=30))
COOKIE_NAME = "aevora_dispatcher"

BAND_COLORS: dict[str, str] = {
    "good": "#4FD48A",
    "satisfactory": "#9DC64A",
    "moderate": "#E8C23D",
    "poor": "#E8A33D",
    "very_poor": "#E4553F",
    "severe": "#A52C24",
}
BAND_RGB: dict[str, list[int]] = {
    k: [int(v[i : i + 2], 16) for i in (1, 3, 5)] for k, v in BAND_COLORS.items()
}
BAND_LABELS: dict[str, str] = {
    "good": "Good",
    "satisfactory": "Satisfactory",
    "moderate": "Moderate",
    "poor": "Poor",
    "very_poor": "Very poor",
    "severe": "Severe",
}

_CSS = """
<style>
:root{--smog-900:#15181A;--smog-850:#1C2022;--smog-800:#232829;--smog-700:#2F3537;--smog-600:#454C4E;
      --bone:#ECE9E0;--bone-dim:#8E948F;--lamp:#E8A33D;--clean:#4FD48A;--vpoor:#E4553F;--sev:#A52C24}
[data-testid="stHeader"]{background:transparent}
.block-container{padding-top:1.6rem;max-width:1400px}
h1,h2,h3{letter-spacing:-.02em}
.mono,code{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.av-brand{font-weight:700;font-size:28px;letter-spacing:-.05em;color:var(--clean);
          text-shadow:0 0 28px rgba(79,212,138,.25);line-height:1}
.av-sub{color:var(--bone-dim);font-size:12px;letter-spacing:.06em;margin-top:2px}
.av-sub em{font-style:normal;color:var(--clean);font-weight:600}
.av-title{display:flex;align-items:baseline;gap:14px;margin:0 0 4px}
.av-title h1{margin:0;font-size:30px}
.av-title .kicker{color:var(--bone-dim);font-size:13px}
.av-chip{display:inline-block;border-radius:999px;padding:2px 10px;font-size:11.5px;font-weight:600;
         line-height:1.6;border:1px solid transparent;white-space:nowrap}
.av-chip.replay{background:rgba(232,163,61,.14);color:var(--lamp);border-color:rgba(232,163,61,.35)}
.av-chip.live{background:rgba(79,212,138,.12);color:var(--clean);border-color:rgba(79,212,138,.3)}
.av-chip.sim{background:rgba(232,163,61,.14);color:var(--lamp)}
.av-chip.low{background:rgba(142,148,143,.15);color:var(--bone-dim)}
.av-chip.high{background:rgba(79,212,138,.12);color:var(--clean)}
.av-clock{font-family:"IBM Plex Mono",monospace;font-size:22px;font-weight:600;color:var(--bone)}
.av-clock small{font-size:12px;color:var(--bone-dim);font-weight:400;margin-left:6px}
.av-kpi{background:var(--smog-850);border:1px solid var(--smog-700);border-radius:12px;padding:14px 16px}
.av-kpi .v{font-family:"IBM Plex Mono",monospace;font-size:26px;font-weight:600;color:var(--bone);line-height:1.1}
.av-kpi .l{font-size:12px;color:var(--bone-dim);margin-top:4px}
.av-kpi.warn .v{color:var(--vpoor)} .av-kpi.good .v{color:var(--clean)}
.av-legend{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:11.5px;color:var(--bone-dim)}
.av-legend span.sw{display:inline-flex;align-items:center;gap:5px}
.av-legend i{display:inline-block;width:10px;height:10px;border-radius:3px}
.av-route{border:1px solid var(--smog-700);border-radius:12px;padding:14px 16px;background:var(--smog-850)}
.av-route.rec{border-color:rgba(79,212,138,.55);box-shadow:0 0 0 1px rgba(79,212,138,.2) inset}
.av-route .lab{font-size:12px;color:var(--bone-dim);text-transform:uppercase;letter-spacing:.06em}
.av-route .big{font-family:"IBM Plex Mono",monospace;font-size:20px;font-weight:600}
.av-route .row{display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-bottom:1px dashed var(--smog-700)}
.av-route .row:last-child{border-bottom:0}
.av-route .row b{font-family:"IBM Plex Mono",monospace;font-weight:500}
.av-banner{border-radius:12px;padding:12px 16px;font-size:14px;border:1px solid}
.av-banner.ok{background:rgba(79,212,138,.08);border-color:rgba(79,212,138,.35)}
.av-banner.risk{background:rgba(228,85,63,.08);border-color:rgba(228,85,63,.4)}
.av-step{display:flex;gap:10px;font-size:13px;padding:6px 0;border-bottom:1px solid var(--smog-800)}
.av-step .d{font-family:"IBM Plex Mono",monospace;color:var(--bone-dim);min-width:64px;text-align:right}
.av-alert{border-left:3px solid var(--vpoor);background:var(--smog-850);border-radius:8px;padding:10px 12px;margin-bottom:8px;font-size:13.5px}
.av-note{color:var(--bone-dim);font-size:12.5px}
[data-testid="stSidebarNav"] a span{font-size:14px}
div[data-testid="stExpander"] details{border-color:var(--smog-700)}
</style>
"""


def ist(dt: datetime) -> datetime:
    return dt.astimezone(IST)


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def page_title(title: str, kicker: str = "") -> None:
    st.markdown(
        f'<div class="av-title"><h1>{title}</h1><span class="kicker">{kicker}</span></div>',
        unsafe_allow_html=True,
    )


# --- auth -------------------------------------------------------------------


def _login_url() -> str:
    base = services.settings().public_api_url
    # After an explicit sign-out, also drop the API's dispatcher cookie, or the
    # login page would bounce straight back here.
    return f"{base}/logout?role=dispatcher" if st.session_state.get("signed_out") else f"{base}/"


def require_dispatcher():
    """Gate the whole console. The login page hands off ?token=...; locally
    the API's cookie is also visible here (cookies ignore port), so a
    refresh keeps you signed in."""
    token = st.query_params.get("token")
    if token:
        session = services.verify_session(token)
        if session and session.role == "dispatcher":
            st.session_state["session"] = session
            st.session_state["token"] = token
            st.session_state.pop("signed_out", None)
        del st.query_params["token"]

    session = st.session_state.get("session")
    if session is None and not st.session_state.get("signed_out"):
        cookie_token = st.context.cookies.get(COOKIE_NAME)
        candidate = services.verify_session(cookie_token)
        if candidate and candidate.role == "dispatcher":
            session = candidate
            st.session_state["session"] = session
            st.session_state["token"] = cookie_token

    if session is not None and (session.role != "dispatcher" or services.verify_session(st.session_state.get("token")) is None):
        st.session_state.pop("session", None)
        session = None

    if session is None:
        inject_css()
        st.markdown(
            f"""
            <div style="max-width:420px;margin:12vh auto 0;text-align:center">
              <div class="av-brand" style="font-size:64px">Aevora</div>
              <div class="av-sub">Powered by <em>Neo4j</em></div>
              <div class="av-route" style="margin-top:28px;text-align:left">
                <h3 style="margin:0 0 6px">Dispatcher sign-in required</h3>
                <p class="av-note" style="margin:0 0 14px">The console is for signed-in dispatchers.
                Sign in on the Aevora page and you'll be brought straight back here.</p>
                <a href="{_login_url()}" target="_self" style="display:block;text-align:center;background:#E8A33D;
                   color:#12140F;font-weight:600;border-radius:9px;padding:11px;text-decoration:none">Go to sign in</a>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()
    return session


def render_sidebar(session) -> None:
    with st.sidebar:
        st.markdown(
            '<div class="av-brand">Aevora</div><div class="av-sub">Powered by <em>Neo4j</em></div>',
            unsafe_allow_html=True,
        )
        st.caption(" ")
        st.markdown(f"**{session.name}**  \n<span class='av-note'>Dispatcher</span>", unsafe_allow_html=True)
        if st.button("Sign out", use_container_width=True, key="sign_out"):
            for k in ("session", "token"):
                st.session_state.pop(k, None)
            st.session_state["signed_out"] = True
            st.rerun()
        st.markdown(
            f"<p class='av-note' style='margin-top:10px'>Rider app: "
            f"<a href='{services.settings().public_api_url}/?role=rider' target='_blank'>open</a></p>",
            unsafe_allow_html=True,
        )


# --- replay bar + legend ----------------------------------------------------

_SPEEDS = [1, 5, 10, 30, 60, 120, 300, 600]


def render_replay_bar() -> None:
    state = services.get_clock_state()
    now = ist(state.now_ts)
    with st.container(border=True):
        cols = st.columns([3.2, 1.1, 1.3, 1.3, 1.3, 1.6], vertical_alignment="center")
        cols[0].markdown(
            f'<span class="av-chip replay">Replay</span> '
            f'<span class="av-clock">{now:%a %d %b %H:%M}<small>IST · {state.speed}×'
            f'{"" if state.running else " · paused"}</small></span>',
            unsafe_allow_html=True,
        )
        if cols[1].button("Pause" if state.running else "Play", key="clock_toggle", use_container_width=True):
            services.update_clock(ClockActionRequest(action="pause" if state.running else "resume"))
            st.rerun()
        speed = cols[2].selectbox(
            "Speed", _SPEEDS, index=_SPEEDS.index(state.speed) if state.speed in _SPEEDS else 4,
            key="clock_speed", label_visibility="collapsed", format_func=lambda s: f"{s}×",
        )
        if speed != state.speed:
            services.update_clock(ClockActionRequest(action="set_speed", speed=speed))
            st.rerun()
        if cols[3].button("Demo start", key="clock_demo_start", use_container_width=True,
                          help="Jump to Wed 27 Jan 2021, 14:00 IST - most zones reporting, moderate air"):
            services.update_clock(ClockActionRequest(action="jump", to=DEMO_START))
            st.rerun()
        if cols[4].button("Clear spikes", key="clock_reset_spikes", use_container_width=True):
            services.clear_spikes()
            st.rerun()
        cols[5].markdown(
            '<span class="av-chip live">Live Google traffic</span>'
            if not services.using_mocks() else '<span class="av-chip low">Mocked data</span>',
            unsafe_allow_html=True,
        )


def render_legend() -> None:
    items = "".join(
        f'<span class="sw"><i style="background:{BAND_COLORS[b]}"></i>{BAND_LABELS[b]}</span>'
        for b in BAND_COLORS
    )
    st.markdown(
        f'<div class="av-legend"><span>PM2.5 (15-min median)</span>{items}'
        f'<span style="margin-left:8px">· coverage under 80% = low confidence · '
        f'scores show exposure reduction, not a health claim</span></div>',
        unsafe_allow_html=True,
    )


def chip(text: str, kind: str) -> str:
    return f'<span class="av-chip {kind}">{text}</span>'


def confidence_badge(confidence: str, simulated: bool) -> str:
    out = chip(f"{confidence} confidence", "high" if confidence == "high" else "low")
    if simulated:
        out += " " + chip("Simulated", "sim")
    return out


def kpi(label: str, value: str, kind: str = "") -> str:
    return f'<div class="av-kpi {kind}"><div class="v">{value}</div><div class="l">{label}</div></div>'


def render_data_and_method() -> None:
    with st.expander("Data and method"):
        st.markdown(
            "- **Pollution is replayed**: PM2.5 zones come from a historical Delhi NCR sensor dataset "
            "(Jan 2021), aggregated to 15-minute buckets on H3 zones and replayed on the clock above.\n"
            "- **Traffic and routes are live**: candidate routes come from the Google Routes API "
            "(two-wheeler, traffic-aware, alternatives) at the moment you plan - today's traffic, "
            "not January 2021's.\n"
            "- **Dose** = Σ PM2.5 × hours in each zone, using the arrival time at each zone to pick the "
            "bucket. Zones with no reading at that time use the city-wide mean for that bucket and don't "
            "count toward coverage.\n"
            "- **Simulated** readings are spikes injected for this demo, never real sensor data.\n"
            "- **Confidence**: route coverage under 80% is marked low confidence.\n"
            "- Scores show relative **exposure reduction**, not a health or medical claim."
        )
