"""Route planner (T2.5-T2.7): search, candidate picker, side-by-side route
comparison, and a Google Maps JS view of the recommended route + zone colors.
Google traffic/routing is live; the PM2.5 zone layer is replayed (PRD §9/§15
maps rule: draw routes on Google Maps JS only, never store raw geometry).
"""

from __future__ import annotations

import json
from datetime import timedelta

import h3
import streamlit as st
from streamlit.components.v1 import html as components_html

from api.config import get_settings
from core.schemas.common import LatLng
from core.schemas.places import NEEDS_PICK_THRESHOLD
from core.schemas.routes import RoutePlanRequest
from ui import services
from ui.components import (
    BAND_COLORS,
    configure_page,
    confidence_badge,
    render_data_and_method,
    render_legend,
    render_replay_bar,
)

configure_page("Route planner")
st.title("Route planner")

render_replay_bar()
render_legend()

st.session_state.setdefault("searched", False)
st.session_state.setdefault("origin_query", "")
st.session_state.setdefault("dest_query", "")
st.session_state.setdefault("departure_time", None)
st.session_state.setdefault("window_minutes", 60)


def _resolve_and_pick(label: str, query: str, state_key: str):
    """Resolves a query and, if ambiguous, shows a picker. Runs on every
    rerun (not just on submit) so picking a candidate takes effect
    immediately - a form_submit_button-gated version would need a second
    click to notice the selectbox changed.
    """
    if not query:
        return None
    resp = services.resolve_place(query)
    if not resp.candidates:
        st.warning(f"No matches for {label.lower()} \"{query}\".")
        return None
    if resp.needs_pick or len(resp.candidates) > 1:
        options = {f"{c.name} ({c.confidence:.0%} confidence)": c for c in resp.candidates}
        picked_label = st.selectbox(
            f"Confirm {label.lower()}", options=list(options.keys()), key=f"{state_key}_pick"
        )
        return options[picked_label]
    return resp.candidates[0]


with st.form("route_search"):
    cols = st.columns(2)
    origin_query = cols[0].text_input("Pickup", placeholder="e.g. Connaught Place")
    dest_query = cols[1].text_input("Drop", placeholder="e.g. Cyber Hub, Gurugram")

    now = services.get_clock_state().now_ts
    time_cols = st.columns(2)
    departure_ts = time_cols[0].time_input("Departure (replay time)", value=now.time())
    window_minutes = time_cols[1].slider("Delivery window (minutes from departure)", 15, 180, 60, step=15)

    search_submitted = st.form_submit_button("Find routes")

if search_submitted:
    st.session_state["searched"] = True
    st.session_state["origin_query"] = origin_query
    st.session_state["dest_query"] = dest_query
    st.session_state["departure_time"] = departure_ts
    st.session_state["window_minutes"] = window_minutes

plan = None
if st.session_state["searched"]:
    origin = _resolve_and_pick("Pickup", st.session_state["origin_query"], "origin_choice")
    dest = _resolve_and_pick("Drop", st.session_state["dest_query"], "dest_choice")
    if origin and dest:
        departure = now.replace(
            hour=st.session_state["departure_time"].hour,
            minute=st.session_state["departure_time"].minute,
            second=0,
            microsecond=0,
        )
        req = RoutePlanRequest(
            origin=LatLng(lat=origin.lat, lng=origin.lng),
            destination=LatLng(lat=dest.lat, lng=dest.lng),
            departure_ts=departure,
            window_end=departure + timedelta(minutes=st.session_state["window_minutes"]),
        )
        plan = services.plan_routes(req)
        st.session_state["origin_choice"] = origin
        st.session_state["dest_choice"] = dest

if plan is None:
    st.info("Search a pickup and drop to compare routes by time, dose and window margin.")
else:
    rec = plan.recommendation
    recommended = next(r for r in plan.routes if r.id == rec.route_id)

    if rec.window_at_risk:
        st.warning(f"Window at risk: recommending the fastest route. {plan.explanation}")
    else:
        st.success(
            f"Recommended: {recommended.duration_s / 60:.0f} min, "
            f"{rec.dose_delta_pct:+.0f}% dose vs fastest, +{rec.extra_minutes:.1f} min vs fastest. "
            f"{plan.explanation}"
        )

    st.subheader("Compare routes")
    cols = st.columns(len(plan.routes))
    for col, route in zip(cols, sorted(plan.routes, key=lambda r: r.rank)):
        with col:
            label = "Recommended" if route.id == rec.route_id else f"Alternative (rank {route.rank})"
            st.markdown(f"**{label}**")
            st.metric("Time", f"{route.duration_s / 60:.0f} min")
            st.metric("Dose (relative)", f"{route.dose:.0f}")
            margin_min = route.window_margin_s / 60
            st.metric("Window margin", f"{margin_min:+.0f} min")
            st.markdown(confidence_badge(route.confidence, any(z.source == "simulated" for z in route.zones)))
            st.caption(f"Coverage: {route.coverage:.0%}")
            with st.expander("Zone breakdown"):
                for z in route.zones:
                    st.write(f"`{z.h3}` - {z.seconds / 60:.1f} min - PM2.5 {z.pm25:.0f} - {z.source}")

    st.divider()
    st.subheader("Map")
    settings = get_settings()
    browser_key = settings.google_maps_browser_key
    if not browser_key:
        st.warning("GOOGLE_MAPS_BROWSER_KEY / GOOGLE_MAPS_API_KEY not set - map view unavailable.")
    else:
        origin = st.session_state["origin_choice"]
        dest = st.session_state["dest_choice"]
        # look up each traversed zone's current band for the circle color
        current_zones = {zr.h3: zr for zr in services.get_zones().zones}
        zone_points = []
        for z in recommended.zones:
            lat, lng = h3.cell_to_latlng(z.h3)
            band = current_zones[z.h3].band if z.h3 in current_zones else "moderate"
            zone_points.append({"lat": lat, "lng": lng, "color": BAND_COLORS[band], "pm25": z.pm25})

        map_payload = {
            "origin": {"lat": origin.lat, "lng": origin.lng, "name": origin.name},
            "destination": {"lat": dest.lat, "lng": dest.lng, "name": dest.name},
            "zones": zone_points,
        }

        components_html(
            f"""
            <div id="route-map" style="height:480px;border-radius:8px;"></div>
            <script>
              const payload = {json.dumps(map_payload)};
              function initMap() {{
                const map = new google.maps.Map(document.getElementById("route-map"), {{
                  zoom: 11,
                  center: payload.origin,
                }});
                new google.maps.Marker({{ position: payload.origin, map, label: "A" }});
                new google.maps.Marker({{ position: payload.destination, map, label: "B" }});

                const directionsService = new google.maps.DirectionsService();
                const directionsRenderer = new google.maps.DirectionsRenderer({{ suppressMarkers: true }});
                directionsRenderer.setMap(map);
                directionsService.route(
                  {{
                    origin: payload.origin,
                    destination: payload.destination,
                    travelMode: google.maps.TravelMode.DRIVING,
                  }},
                  (result, status) => {{
                    if (status === "OK") directionsRenderer.setDirections(result);
                  }}
                );

                payload.zones.forEach((z) => {{
                  const circle = new google.maps.Circle({{
                    strokeWeight: 0,
                    fillColor: z.color,
                    fillOpacity: 0.35,
                    map,
                    center: {{ lat: z.lat, lng: z.lng }},
                    radius: 600,
                  }});
                  const info = new google.maps.InfoWindow({{ content: "PM2.5: " + z.pm25 }});
                  circle.addListener("click", (e) => {{ info.setPosition(e.latLng); info.open(map); }});
                }});
              }}
            </script>
            <script src="https://maps.googleapis.com/maps/api/js?key={browser_key}&callback=initMap" async defer></script>
            """,
            height=500,
        )
        st.caption(
            "Route and traffic are live from Google Maps today; the colored zone circles show "
            "**replayed** historical PM2.5, not live pollution."
        )

render_data_and_method()
