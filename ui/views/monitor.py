"""Air & alerts: inspect any replay moment's zone layer (independent of the
live clock) and the full alert log with filters and acknowledge."""

from __future__ import annotations

from datetime import timedelta

import h3
import pandas as pd
import pydeck as pdk
import streamlit as st

from ui import services
from ui.components import (
    BAND_LABELS,
    BAND_RGB,
    chip,
    confidence_badge,
    ist,
    page_title,
    render_data_and_method,
    render_legend,
    render_replay_bar,
)

page_title("Air & alerts", "the replayed zone layer and every alert")
render_replay_bar()
render_legend()

tab_zones, tab_alerts = st.tabs(["Zone layer", "Alert log"])

with tab_zones:
    state = services.get_clock_state()
    total = int((state.max_ts - state.min_ts).total_seconds() // 60)
    current = min(int((state.now_ts - state.min_ts).total_seconds() // 60), total)
    minutes = st.slider("Replay moment", 0, max(total, 1), current - current % 15, step=15,
                        format="%d min into the window")
    moment = state.min_ts + timedelta(minutes=minutes)
    st.markdown(f'<p class="av-note">Showing <span class="mono">{ist(moment):%a %d %b %H:%M}</span> IST - '
                f'independent of the live clock.</p>', unsafe_allow_html=True)
    zones = services.get_zones(ts=moment).zones

    map_col, list_col = st.columns([1.7, 1])
    with map_col:
        if zones:
            df = pd.DataFrame([{"h3": z.h3, "pm25": round(z.pm25), "band": BAND_LABELS[z.band],
                                "color": BAND_RGB[z.band] + [170]} for z in zones])
            lat, lng = h3.cell_to_latlng(zones[0].h3)
            st.pydeck_chart(
                pdk.Deck(
                    layers=[pdk.Layer("H3HexagonLayer", df, get_hexagon="h3", get_fill_color="color",
                                      get_line_color=[21, 24, 26], line_width_min_pixels=1, pickable=True)],
                    initial_view_state=pdk.ViewState(latitude=lat, longitude=lng, zoom=10.3),
                    tooltip={"text": "PM2.5 {pm25} · {band}"},
                    map_style="dark",
                ),
                height=520,
            )
        else:
            st.info("No zone reports at this replay moment (overnight coverage is sparse).")
    with list_col:
        st.markdown(f"##### {len(zones)} zones reporting")
        for z in sorted(zones, key=lambda z: -z.pm25)[:25]:
            st.markdown(
                f'<div class="av-step"><span class="d">{z.pm25:.0f}</span>'
                f'<span><span class="mono">{z.h3}</span> · {BAND_LABELS[z.band]} · {z.n_sensors} sensor(s) '
                f'{confidence_badge(z.confidence, z.simulated)}</span></div>',
                unsafe_allow_html=True,
            )

with tab_alerts:
    c1, c2 = st.columns(2)
    status = c1.selectbox("Status", ["All", "new", "acked"])
    rider = c2.text_input("Rider id", placeholder="rider-3")
    alerts = services.get_alerts(status=None if status == "All" else status, rider_id=rider.strip() or None)
    if not alerts:
        st.markdown('<p class="av-note">No alerts match.</p>', unsafe_allow_html=True)
    for a in alerts[:50]:
        cols = st.columns([5, 1.2], vertical_alignment="center")
        cols[0].markdown(
            f'<div class="av-alert"><b>{a.severity.replace("_", " ").title()}</b> · rider <b>{a.rider_id}</b> · '
            f'zone <span class="mono">{a.h3}</span> · order <span class="mono">{a.order_id}</span> · '
            f'{ist(a.ts):%d %b %H:%M} IST · {a.status} '
            f'{chip("Simulated", "sim") if a.simulated else chip("Sensor reading", "low")}</div>',
            unsafe_allow_html=True,
        )
        if a.status == "new" and cols[1].button("Acknowledge", key=f"mon_ack_{a.id}", use_container_width=True):
            services.acknowledge_alert(a.id)
            st.rerun()

render_data_and_method()
