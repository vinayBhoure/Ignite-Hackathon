"""Plan & dispatch: resolve pickup/drop, compare live Google alternatives by
time, dose and window margin (never a blended score), then dispatch the
chosen route to a rider. No scoring here - ui/services.py -> core/.
"""

from __future__ import annotations

import html
import uuid
from datetime import timedelta

import h3
import streamlit as st

from core.navigation.google import RoutingUnavailable
from core.schemas.common import LatLng, severity_band_for
from core.schemas.orders import OrderAssignRequest
from core.schemas.routes import RoutePlanRequest
from ui import services
from ui.components import (
    BAND_COLORS,
    chip,
    confidence_badge,
    ist,
    page_title,
    render_data_and_method,
    render_legend,
    render_replay_bar,
)
from ui.maps import plan_map_html

page_title("Plan & dispatch", "live Google routes · replayed air")
render_replay_bar()
render_legend()

ss = st.session_state
ss.setdefault("q_pickup", "South Delhi Hub")
ss.setdefault("q_drop", "")
ss.setdefault("q_window", 60)
ss.setdefault("plan_sig", None)


def _pick(label: str, query: str, key: str):
    if not query:
        return None
    try:
        resp = services.resolve_place(query)
    except RoutingUnavailable as exc:
        st.error(f"Place search is unavailable: {exc}")
        return None
    if not resp.candidates:
        st.warning(f'No match in Delhi NCR for {label.lower()} "{query}". Try a landmark or area name.')
        return None
    if len(resp.candidates) > 1 and resp.needs_pick:
        options = {f"{c.name}  ·  {c.confidence:.0%}": c for c in resp.candidates}
        return options[st.selectbox(f"Which {label.lower()} did you mean?", list(options), key=f"pick_{key}")]
    return resp.candidates[0]


with st.form("plan_form", border=True):
    c1, c2, c3 = st.columns([2, 2, 1.2])
    pickup_q = c1.text_input("Pickup", value=ss["q_pickup"], placeholder="South Delhi Hub, Nehru Place, CP…")
    drop_q = c2.text_input("Drop", value=ss["q_drop"], placeholder="Saket, Lajpat Nagar, Connaught Place…")
    window = c3.number_input("Delivery window (min)", min_value=10, max_value=240, value=ss["q_window"], step=5)
    submitted = st.form_submit_button("Find cleanest route", type="primary", use_container_width=True)

if submitted:
    ss["q_pickup"], ss["q_drop"], ss["q_window"] = pickup_q.strip(), drop_q.strip(), int(window)
    ss["plan_departure"] = services.get_clock_state().now_ts
    ss["plan_sig"] = None
    ss.pop("dispatched", None)

if ss.get("dispatched"):
    d = ss["dispatched"]
    st.markdown(
        f'<div class="av-banner ok">Dispatched <b>{d["order_id"]}</b> to <b>{d["rider"]}</b>. '
        f'It\'s live on the fleet map now; the rider sees turn-by-turn navigation after signing in with '
        f'<span class="mono">{d["phone"]}</span> / <span class="mono">aevora-rider</span>.</div>',
        unsafe_allow_html=True,
    )

if not ss["q_pickup"] or not ss["q_drop"]:
    st.markdown('<p class="av-note">Enter a drop to compare live routes. '
                'Pickup defaults to the South Delhi Hub where the fleet is based.</p>', unsafe_allow_html=True)
    render_data_and_method()
    st.stop()

origin = _pick("Pickup", ss["q_pickup"], "o")
dest = _pick("Drop", ss["q_drop"], "d")
if not (origin and dest):
    render_data_and_method()
    st.stop()

departure = ss.get("plan_departure") or services.get_clock_state().now_ts
sig = (origin.place_id, dest.place_id, ss["q_window"], departure.isoformat())
if ss["plan_sig"] != sig:
    with st.spinner("Fetching live routes from Google and scoring each against the zone layer…"):
        try:
            ss["plan"] = services.plan_routes(
                RoutePlanRequest(
                    origin=LatLng(lat=origin.lat, lng=origin.lng),
                    destination=LatLng(lat=dest.lat, lng=dest.lng),
                    departure_ts=departure,
                    window_end=departure + timedelta(minutes=ss["q_window"]),
                )
            )
            ss["plan_sig"] = sig
        except RoutingUnavailable as exc:
            st.error(f"Couldn't get routes: {exc}")
            st.stop()

plan = ss["plan"]
rec = plan.recommendation
routes = sorted(plan.routes, key=lambda r: r.rank)
recommended = next(r for r in routes if r.id == rec.route_id)

banner_kind = "risk" if rec.window_at_risk else "ok"
headline = "Window at risk - fastest route recommended" if rec.window_at_risk else "Recommended route"
st.markdown(
    f'<div class="av-banner {banner_kind}"><b>{headline}:</b> {recommended.label} · '
    f'<span class="mono">{recommended.duration_s / 60:.0f} min</span> · dose '
    f'<span class="mono">{recommended.dose:.0f}</span> '
    f'({rec.dose_delta_pct:+.0f}% vs fastest, {rec.extra_minutes:+.0f} min) · departs '
    f'<span class="mono">{ist(departure):%H:%M}</span> IST replay<br>'
    f'<span class="av-note">{plan.explanation}</span></div>',
    unsafe_allow_html=True,
)
st.write("")

map_col, cards_col = st.columns([1.55, 1])

with cards_col:
    st.markdown("##### Compare routes")
    for r in routes:
        is_rec = r.id == rec.route_id
        simulated = any(z.source == "simulated" for z in r.zones)
        st.markdown(
            f"""
            <div class="av-route {'rec' if is_rec else ''}" style="margin-bottom:10px">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span class="lab">#{r.rank} · {r.label}</span>
                {chip('Recommended', 'high') if is_rec else ''}
              </div>
              <div class="row"><span>Time</span><b>{r.duration_s / 60:.0f} min · {r.distance_m / 1000:.1f} km</b></div>
              <div class="row"><span>Dose (µg·h/m³, relative)</span><b>{r.dose:.0f}</b></div>
              <div class="row"><span>Window margin</span><b style="color:{'#E4553F' if r.window_margin_s < 120 else 'inherit'}">{r.window_margin_s / 60:+.0f} min</b></div>
              <div class="row"><span>Coverage</span><b>{r.coverage:.0%}</b></div>
              <div style="margin-top:8px">{confidence_badge(r.confidence, simulated)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with map_col:
    key = services.settings().google_maps_browser_key
    zones = []
    for z in recommended.zones:
        lat, lng = h3.cell_to_latlng(z.h3)
        zones.append({"lat": lat, "lng": lng, "pm25": z.pm25, "source": z.source,
                      "color": BAND_COLORS[severity_band_for(z.pm25)]})
    st.iframe(
        plan_map_html(
            [{"polyline": r.polyline, "recommended": r.id == rec.route_id, "label": r.label} for r in routes],
            {"lat": origin.lat, "lng": origin.lng, "name": origin.name},
            {"lat": dest.lat, "lng": dest.lng, "name": dest.name},
            zones, key or "",
        ),
        height=475,
    )
    st.markdown(
        '<p class="av-note">Green = recommended, grey = alternatives. Circles are PM2.5 at the time the rider '
        'reaches each zone (faint = city-mean estimate, amber ring = simulated).</p>',
        unsafe_allow_html=True,
    )

st.divider()
left, right = st.columns([1.1, 1])

with left:
    st.markdown("##### Dispatch")
    choice = st.radio(
        "Route to dispatch",
        [r.id for r in routes],
        index=[r.id for r in routes].index(rec.route_id),
        format_func=lambda rid: next(
            f"#{r.rank} {r.label} — {r.duration_s / 60:.0f} min, dose {r.dose:.0f}" for r in routes if r.id == rid
        ),
    )
    riders = [r for r in services.list_riders() if r.status == "available"]
    if not riders:
        st.warning("Every rider is on a delivery. Wait for one to arrive, or check the fleet page.")
    else:
        rider = st.selectbox(
            "Rider", riders, format_func=lambda r: f"{r.name} · activity ×{r.activity_factor:.2f}"
        )
        if st.button("Dispatch to rider", type="primary", use_container_width=True):
            order_id = f"ord-{uuid.uuid4().hex[:6]}"
            services.assign_order(
                order_id,
                OrderAssignRequest(route_id=choice, rider_id=rider.id,
                                   pickup_name=origin.name.split(",")[0], drop_name=dest.name.split(",")[0]),
            )
            n = int(rider.id.split("-")[1])
            ss["dispatched"] = {"order_id": order_id, "rider": rider.name, "phone": f"+91 99000 000{n:02d}"}
            ss["q_drop"], ss["plan_sig"] = "", None
            st.rerun()

with right:
    chosen = next(r for r in routes if r.id == choice)
    st.markdown(f"##### Turn by turn · {chosen.label}")
    def _step(s) -> str:
        # Google puts advisories ("Parts of this road may be closed...") on
        # later lines of the same instruction.
        main, *notes = [html.escape(line) for line in s.instruction.split("\n") if line.strip()] or ["Continue"]
        note = f'<br><span class="av-note">{" · ".join(notes)}</span>' if notes else ""
        return f'<div class="av-step"><span class="d">{s.distance_m / 1000:.1f} km</span><span>{main}{note}</span></div>'

    steps_html = "".join(_step(s) for s in chosen.steps[:14])
    more = len(chosen.steps) - 14
    st.markdown(steps_html + (f'<p class="av-note">+{more} more steps</p>' if more > 0 else ""), unsafe_allow_html=True)

render_data_and_method()
