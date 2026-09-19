"""Dispatcher console home (T2.2/T2.3/T2.4): zone map, demo controls, KPI
strip, alerts panel. `streamlit run ui/app.py` - additional pages live in
ui/pages/. No scoring logic here (CLAUDE.md architecture rule 1): every
value comes from ui/services.py, which calls core/ the same way the API does.
"""

from __future__ import annotations

import h3
import pandas as pd
import pydeck as pdk
import streamlit as st

from core.schemas.demo import SpikeRequest
from ui import services
from ui.components import (
    BAND_RGB,
    configure_page,
    confidence_badge,
    render_data_and_method,
    render_legend,
    render_replay_bar,
)

configure_page("Home")
st.title("Dispatcher console")

render_replay_bar()
render_legend()

zones_resp = services.get_zones()

# --- KPI strip -----------------------------------------------------------
alerts = services.get_alerts(status="new")
n_poor_plus = sum(1 for z in zones_resp.zones if z.band in ("poor", "very_poor", "severe"))
avg_coverage = (
    sum(1 for z in zones_resp.zones if z.confidence == "high") / len(zones_resp.zones)
    if zones_resp.zones
    else 0.0
)

kpi_cols = st.columns(4)
kpi_cols[0].metric("Zones tracked", len(zones_resp.zones))
kpi_cols[1].metric("Zones at Poor or worse", n_poor_plus)
kpi_cols[2].metric("New alerts", len(alerts))
kpi_cols[3].metric("High-confidence zones", f"{avg_coverage:.0%}")

st.divider()

map_col, control_col = st.columns([3, 2])

# --- Zone map --------------------------------------------------------------
with map_col:
    st.subheader("PM2.5 by zone")
    if zones_resp.zones:
        rows = [
            {
                "h3": z.h3,
                "pm25": z.pm25,
                "band": z.band,
                "color": BAND_RGB[z.band],
                "simulated": z.simulated,
            }
            for z in zones_resp.zones
        ]
        df = pd.DataFrame(rows)
        center_lat, center_lng = h3.cell_to_latlng(rows[0]["h3"])

        layer = pdk.Layer(
            "H3HexagonLayer",
            df,
            get_hexagon="h3",
            get_fill_color="color",
            get_line_color=[255, 255, 255],
            line_width_min_pixels=1,
            opacity=0.7,
            pickable=True,
            extruded=False,
        )
        view_state = pdk.ViewState(latitude=center_lat, longitude=center_lng, zoom=10)
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip={"text": "{h3}\nPM2.5: {pm25}\nBand: {band}"},
                map_style=None,
            )
        )
    else:
        st.info("No zone readings for the current replay time.")

# --- Demo controls: spike injector -----------------------------------------
with control_col:
    st.subheader("Demo controls")
    with st.form("inject_spike_form"):
        zone_options = [z.h3 for z in zones_resp.zones] or ["(no zones loaded)"]
        spike_h3 = st.selectbox("Zone to spike", options=zone_options)
        spike_pm25 = st.slider("PM2.5 during spike", min_value=130, max_value=500, value=300, step=10)
        spike_duration = st.slider("Duration (replay minutes)", min_value=15, max_value=120, value=45, step=15)
        submitted = st.form_submit_button("Inject spike")
        if submitted and zones_resp.zones:
            resp = services.create_spike(
                SpikeRequest(h3=spike_h3, pm25=float(spike_pm25), duration_min=spike_duration)
            )
            st.success(f"Spike injected ({resp.buckets_written} buckets, labeled Simulated).")
            st.rerun()

    st.caption("Injected readings are written with source=simulated and always shown with a Simulated badge.")

st.divider()

# --- Alerts panel ------------------------------------------------------------
st.subheader("Active alerts")
if not alerts:
    st.caption("No active alerts on any tracked route.")
else:
    for alert in alerts:
        with st.container(border=True):
            cols = st.columns([4, 1])
            cols[0].markdown(
                f"**{alert.severity.replace('_', ' ').title()}** spike near zone `{alert.h3}` "
                f"for rider `{alert.rider_id}` (order `{alert.order_id}`) at {alert.ts:%H:%M} replay time. "
                ":orange-badge[Simulated]" if alert.severity in ("very_poor", "severe") else ""
            )
            if cols[1].button("Acknowledge", key=f"ack_{alert.id}"):
                services.acknowledge_alert(alert.id)
                st.rerun()

render_data_and_method()
