"""Live fleet: every active delivery moving on a Google map in replay time,
with a spike-ahead control for the demo and the alert feed."""

from __future__ import annotations

import streamlit as st

from core.schemas.demo import SpikeRequest
from ui import services
from ui.components import (
    BAND_COLORS,
    chip,
    ist,
    kpi,
    page_title,
    render_data_and_method,
    render_legend,
    render_replay_bar,
)
from ui.maps import fleet_map_html

page_title("Live fleet", "riders move on the replay clock")
render_replay_bar()
render_legend()
st.write("")


def fleet_alerts(active) -> list:
    """Open alerts for deliveries on this page. Orders seeded outside the
    console still alert, but they live in the full log on Air & alerts."""
    ids = {a.order_id for a in active}
    return [a for a in services.get_alerts(status="new") if a.order_id in ids]


@st.fragment(run_every=5)
def kpis() -> None:
    active = services.active_assignments()
    riders = services.list_riders()
    alerts = fleet_alerts(active)
    zones = services.get_zones().zones
    poor = sum(1 for z in zones if z.band in ("poor", "very_poor", "severe"))
    cols = st.columns(5)
    cols[0].markdown(kpi("Deliveries on the road", str(len(active))), unsafe_allow_html=True)
    cols[1].markdown(kpi("Riders available", f"{sum(r.status == 'available' for r in riders)}/{len(riders)}", "good"),
                     unsafe_allow_html=True)
    cols[2].markdown(kpi("Open spike alerts", str(len(alerts)), "warn" if alerts else ""), unsafe_allow_html=True)
    cols[3].markdown(kpi("Zones reporting now", str(len(zones))), unsafe_allow_html=True)
    cols[4].markdown(kpi("Zones Poor or worse", str(poor), "warn" if poor else ""), unsafe_allow_html=True)


kpis()
st.write("")

map_col, side_col = st.columns([1.7, 1])

with map_col:
    s = services.settings()
    st.iframe(
        fleet_map_html(s.public_api_url, st.session_state["token"], BAND_COLORS, s.google_maps_browser_key or ""),
        height=535,
    )


@st.fragment(run_every=5)
def deliveries() -> None:
    active = services.active_assignments()
    st.markdown("##### On the road")
    if not active:
        st.markdown('<p class="av-note">Nobody is out yet. Dispatch an order from <b>Plan &amp; dispatch</b>, '
                    'then press <b>Play</b> on the replay bar.</p>', unsafe_allow_html=True)
        return
    for a in active:
        alert = chip(f"{a.new_alerts} alert", "sim") if a.new_alerts else ""
        st.markdown(
            f'<div class="av-route" style="margin-bottom:8px;padding:10px 12px">'
            f'<div style="display:flex;justify-content:space-between"><b>{a.rider_name}</b>{alert}</div>'
            f'<div class="av-note">{a.pickup_name} → {a.drop_name} · <span class="mono">{a.order_id}</span></div>'
            f'<div class="row"><span>ETA</span><b>{ist(a.eta):%H:%M}</b></div>'
            f'<div class="row"><span>Planned dose · coverage</span><b>{a.dose:.0f} · {a.coverage:.0%}</b></div></div>',
            unsafe_allow_html=True,
        )
        st.progress(a.progress, text=f"{a.progress:.0%} of route")


with side_col:
    deliveries()

st.divider()
spike_col, alert_col = st.columns([1, 1.2])

with spike_col:
    st.markdown("##### Demo: spike the air ahead of a rider")
    active = services.active_assignments()
    if not active:
        st.markdown('<p class="av-note">Needs a delivery on the road.</p>', unsafe_allow_html=True)
    else:
        target = st.selectbox("Delivery", active, format_func=lambda a: f"{a.rider_name} → {a.drop_name}")
        ahead = services.zones_ahead(target.order_id)
        if not ahead:
            st.markdown('<p class="av-note">This rider has passed every tracked zone on their route.</p>',
                        unsafe_allow_html=True)
        else:
            # Default to a zone no alternative passes through - a spike there
            # can be routed around, which is the point of the demo.
            default = next((i for i, z in enumerate(ahead) if z.avoidable and z.minutes_ahead >= 5), 0)
            zone = st.selectbox(
                "Zone on their route",
                ahead,
                index=default,
                format_func=lambda z: f"{z.h3} · in {z.minutes_ahead:.0f} replay-min"
                + (f" · PM2.5 {z.pm25:.0f}" if z.pm25 is not None else "")
                + (" · avoidable" if z.avoidable else " · on every route"),
            )
            pm25 = st.slider("Spike PM2.5 (µg/m³)", 130, 500, 320, step=10)
            if st.button("Inject simulated spike", type="primary", use_container_width=True):
                # Cover from now until the rider has cleared that zone.
                duration = int(zone.minutes_ahead) + 30
                services.create_spike(SpikeRequest(h3=zone.h3, pm25=float(pm25), duration_min=duration))
                services.get_alerts(status="new")  # evaluate immediately
                st.toast("Spike injected - labeled Simulated. The rider gets an alert and a reroute offer.")
                st.rerun()


@st.fragment(run_every=5)
def alert_feed() -> None:
    st.markdown("##### Alert feed")
    alerts = fleet_alerts(services.active_assignments())
    if not alerts:
        st.markdown('<p class="av-note">No open alerts.</p>', unsafe_allow_html=True)
        return
    for a in alerts[:8]:
        cols = st.columns([5, 1.3], vertical_alignment="center")
        cols[0].markdown(
            f'<div class="av-alert"><b>{a.severity.replace("_", " ").title()}</b> air ahead of '
            f'<b>{a.rider_id}</b> · zone <span class="mono">{a.h3}</span> · order '
            f'<span class="mono">{a.order_id}</span> · {ist(a.ts):%H:%M} IST '
            f'{chip("Simulated", "sim") if a.simulated else chip("Sensor reading", "low")}</div>',
            unsafe_allow_html=True,
        )
        if cols[1].button("Acknowledge", key=f"ack_{a.id}", use_container_width=True):
            services.acknowledge_alert(a.id)
            st.rerun(scope="fragment")


with alert_col:
    alert_feed()

render_data_and_method()
