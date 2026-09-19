"""Monitor (T2.8-T2.9): a zones/AQI time inspector independent of the live
replay clock, and the full alert log with filters, acknowledge and a deep
link to the order (PRD IA: "Alert deep links to open its order").
"""

from __future__ import annotations

import h3
import pandas as pd
import pydeck as pdk
import streamlit as st

from ui import services
from ui.components import (
    BAND_RGB,
    configure_page,
    confidence_badge,
    render_data_and_method,
    render_legend,
    render_replay_bar,
)

configure_page("Monitor")
st.title("Monitor")

render_replay_bar()
render_legend()

tab_zones, tab_alerts = st.tabs(["Zones and AQI", "Alerts log"])

with tab_zones:
    st.subheader("Inspect a replay moment")
    state = services.get_clock_state()
    total_minutes = int((state.max_ts - state.min_ts).total_seconds() // 60)
    slider_minutes = st.slider(
        "Minutes into the replay window",
        min_value=0,
        max_value=max(total_minutes, 1),
        value=min(int((state.now_ts - state.min_ts).total_seconds() // 60), total_minutes),
        step=15,
    )
    inspect_ts = state.min_ts + pd.Timedelta(minutes=slider_minutes)
    st.caption(f"Inspecting {inspect_ts:%Y-%m-%d %H:%M} replay time (independent of the live clock above).")

    zones_at_ts = services.get_zones(ts=inspect_ts)

    map_col, list_col = st.columns([3, 2])
    with map_col:
        if zones_at_ts.zones:
            df = pd.DataFrame(
                [
                    {"h3": z.h3, "pm25": z.pm25, "band": z.band, "color": BAND_RGB[z.band]}
                    for z in zones_at_ts.zones
                ]
            )
            center_lat, center_lng = h3.cell_to_latlng(df.iloc[0]["h3"])
            layer = pdk.Layer(
                "H3HexagonLayer",
                df,
                get_hexagon="h3",
                get_fill_color="color",
                get_line_color=[255, 255, 255],
                line_width_min_pixels=1,
                opacity=0.7,
                pickable=True,
            )
            st.pydeck_chart(
                pdk.Deck(
                    layers=[layer],
                    initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lng, zoom=10),
                    tooltip={"text": "{h3}\nPM2.5: {pm25}\nBand: {band}"},
                    map_style=None,
                )
            )
        else:
            st.info("No zone readings at this replay moment.")

    with list_col:
        st.markdown("**Zone list**")
        for z in sorted(zones_at_ts.zones, key=lambda z: -z.pm25):
            with st.container(border=True):
                st.markdown(f"`{z.h3}` - PM2.5 **{z.pm25:.0f}** ({z.band.replace('_', ' ')})")
                st.caption(f"{z.n_sensors} sensor(s) - {confidence_badge(z.confidence, z.simulated)}")

with tab_alerts:
    st.subheader("Alert log")
    filter_cols = st.columns(3)
    status_filter = filter_cols[0].selectbox("Status", options=["All", "new", "acked"])
    rider_filter = filter_cols[1].text_input("Rider id (optional)")

    all_alerts = services.get_alerts(
        status=None if status_filter == "All" else status_filter,
        rider_id=rider_filter or None,
    )

    if not all_alerts:
        st.caption("No alerts match this filter.")
    else:
        for alert in sorted(all_alerts, key=lambda a: a.ts, reverse=True):
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(
                    f"**{alert.severity.replace('_', ' ').title()}** - zone `{alert.h3}` - "
                    f"rider `{alert.rider_id}` - {alert.ts:%Y-%m-%d %H:%M} replay time"
                )
                cols[0].caption(f"Status: {alert.status} - type: {alert.type}")
                if alert.order_id:
                    # Deep-links to the rider app (FastAPI service), a
                    # different host:port than this Streamlit console - shown
                    # as the path rather than a clickable link since the API
                    # base URL isn't known to the UI in this deployment.
                    cols[1].caption(f"Order: /rider/order/{alert.order_id}")
                if alert.status == "new" and cols[2].button("Acknowledge", key=f"monitor_ack_{alert.id}"):
                    services.acknowledge_alert(alert.id)
                    st.rerun()

render_data_and_method()
