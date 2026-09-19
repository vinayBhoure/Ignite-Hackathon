"""Google Maps JS views for the console. Routes are only ever drawn on a
Google map (PRD maps rule); zone colors are our own overlay.

The fleet map loads once and polls the API for positions itself, so Streamlit
never re-renders the iframe (which would reload the Maps script and flicker).
"""

from __future__ import annotations

import json


def _js(value) -> str:
    """JSON for embedding inside <script>: place names come from the geocoder,
    so never let a "</script>" in the data end the script block."""
    return json.dumps(value).replace("</", "<\\/")


DARK_STYLE = [
    {"elementType": "geometry", "stylers": [{"color": "#1c2022"}]},
    {"elementType": "labels.text.fill", "stylers": [{"color": "#8e948f"}]},
    {"elementType": "labels.text.stroke", "stylers": [{"color": "#15181a"}]},
    {"featureType": "poi", "stylers": [{"visibility": "off"}]},
    {"featureType": "transit", "stylers": [{"visibility": "off"}]},
    {"featureType": "road", "elementType": "geometry", "stylers": [{"color": "#2f3537"}]},
    {"featureType": "road", "elementType": "geometry.stroke", "stylers": [{"color": "#15181a"}]},
    {"featureType": "road.highway", "elementType": "geometry", "stylers": [{"color": "#454c4e"}]},
    {"featureType": "road.arterial", "elementType": "labels.text.fill", "stylers": [{"color": "#a7ada7"}]},
    {"featureType": "water", "elementType": "geometry", "stylers": [{"color": "#101b20"}]},
    {"featureType": "administrative", "elementType": "geometry.stroke", "stylers": [{"color": "#454c4e"}]},
]

_BASE = """
<div id="map" style="height:{height}px;border-radius:12px;overflow:hidden;border:1px solid #2F3537"></div>
<div id="note" style="position:absolute;top:12px;left:12px;font:12px 'IBM Plex Mono',monospace;color:#ECE9E0;
     background:rgba(21,24,26,.82);border:1px solid #2F3537;border-radius:8px;padding:6px 10px;display:none"></div>
<style>html,body{{margin:0;background:#15181A}}</style>
<script>
const STYLE = {style};
{script}
</script>
<script src="https://maps.googleapis.com/maps/api/js?key={key}&libraries=geometry&loading=async&callback=initMap" async defer></script>
"""


def plan_map_html(routes: list[dict], origin: dict, destination: dict, zones: list[dict], key: str, height: int = 460) -> str:
    """routes: [{polyline, recommended, label}], zones: [{lat, lng, color, pm25, source}]"""
    payload = _js({"routes": routes, "origin": origin, "destination": destination, "zones": zones})
    script = f"""
const P = {payload};
function initMap() {{
  const map = new google.maps.Map(document.getElementById('map'), {{
    styles: STYLE, disableDefaultUI: true, zoomControl: true, gestureHandling: 'greedy'
  }});
  const bounds = new google.maps.LatLngBounds();
  const ordered = P.routes.slice().sort((a, b) => a.recommended - b.recommended);
  ordered.forEach((r) => {{
    const path = google.maps.geometry.encoding.decodePath(r.polyline);
    path.forEach((p) => bounds.extend(p));
    if (r.recommended) {{
      new google.maps.Polyline({{ path, map, strokeColor: '#0B0F10', strokeWeight: 9, strokeOpacity: 0.9 }});
    }}
    new google.maps.Polyline({{
      path, map, zIndex: r.recommended ? 5 : 1,
      strokeColor: r.recommended ? '#4FD48A' : '#8E948F',
      strokeOpacity: r.recommended ? 1 : 0.55, strokeWeight: r.recommended ? 5 : 4,
    }});
  }});
  P.zones.forEach((z) => {{
    const c = new google.maps.Circle({{
      map, center: {{ lat: z.lat, lng: z.lng }}, radius: 260, strokeWeight: z.source === 'simulated' ? 2 : 0,
      strokeColor: '#E8A33D', fillColor: z.color, fillOpacity: z.source === 'model' ? 0.18 : 0.45, zIndex: 3,
    }});
    const info = new google.maps.InfoWindow({{
      content: '<div style="font:12px sans-serif;color:#111">PM2.5 <b>' + Math.round(z.pm25) + '</b> ('
        + (z.source === 'model' ? 'city mean estimate' : z.source) + ')</div>'
    }});
    c.addListener('click', (e) => {{ info.setPosition(e.latLng); info.open(map); }});
  }});
  [[P.origin, 'A', '#E8A33D'], [P.destination, 'B', '#4FD48A']].forEach(([pt, label, color]) => {{
    bounds.extend(pt);
    new google.maps.Marker({{ position: pt, map, label: {{ text: label, color: '#12140F', fontWeight: '700' }},
      icon: {{ path: google.maps.SymbolPath.CIRCLE, scale: 11, fillColor: color, fillOpacity: 1,
              strokeColor: '#12140F', strokeWeight: 2 }}, title: pt.name, zIndex: 10 }});
  }});
  map.fitBounds(bounds, 40);
}}
"""
    return _BASE.format(height=height, style=json.dumps(DARK_STYLE), script=script, key=key)


def fleet_map_html(api_url: str, token: str, band_colors: dict, key: str, height: int = 520) -> str:
    script = f"""
const API = {_js(api_url)}, TOKEN = {_js(token)}, BANDS = {_js(band_colors)};
let map, fitted = false;
const routes = {{}}, riders = {{}}, zoneDots = [];
function riderIcon(alert) {{
  return {{ path: google.maps.SymbolPath.CIRCLE, scale: 9, fillColor: alert ? '#E4553F' : '#E8A33D',
           fillOpacity: 1, strokeColor: '#15181A', strokeWeight: 3 }};
}}
async function refresh() {{
  let data;
  try {{
    const r = await fetch(API + '/api/fleet/live', {{ headers: {{ Authorization: 'Bearer ' + TOKEN }} }});
    if (!r.ok) throw new Error(r.status);
    data = await r.json();
  }} catch (e) {{
    const n = document.getElementById('note'); n.style.display = 'block';
    n.textContent = 'Live feed unavailable (' + e.message + ') - is the API running at ' + API + '?';
    return;
  }}
  const note = document.getElementById('note');
  note.style.display = 'block';
  note.textContent = data.length ? data.length + ' active deliver' + (data.length === 1 ? 'y' : 'ies') + ' · live'
                                 : 'No active deliveries - plan one in Plan & dispatch';
  const bounds = new google.maps.LatLngBounds();
  const seen = new Set();
  zoneDots.splice(0).forEach((z) => z.setMap(null));
  data.forEach((n) => {{
    seen.add(n.order_id);
    if (!routes[n.order_id] || routes[n.order_id].rid !== n.route_id) {{
      if (routes[n.order_id]) routes[n.order_id].line.setMap(null);
      const path = google.maps.geometry.encoding.decodePath(n.polyline);
      routes[n.order_id] = {{ rid: n.route_id, path,
        line: new google.maps.Polyline({{ path, map, strokeColor: '#4FD48A', strokeOpacity: 0.85, strokeWeight: 4 }}) }};
    }}
    routes[n.order_id].path.forEach((p) => bounds.extend(p));
    n.zones.filter((z) => z.ahead && z.pm25 !== null && !z.estimated).forEach((z) => {{
      zoneDots.push(new google.maps.Circle({{ map, center: {{ lat: z.lat, lng: z.lng }}, radius: 220,
        strokeWeight: z.simulated ? 2 : 0, strokeColor: '#E8A33D', fillColor: BANDS[z.band] || '#8E948F', fillOpacity: 0.45 }}));
    }});
    const pos = {{ lat: n.position.lat, lng: n.position.lng }};
    const alert = n.alerts.length > 0;
    if (!riders[n.order_id]) {{
      const m = new google.maps.Marker({{ map, position: pos, zIndex: 20, icon: riderIcon(alert),
        label: {{ text: n.rider_id.replace('rider-', ''), color: '#12140F', fontSize: '11px', fontWeight: '700' }} }});
      const info = new google.maps.InfoWindow();
      m.addListener('click', () => {{ info.setContent(m.get('html')); info.open(map, m); }});
      riders[n.order_id] = m;
    }}
    const m = riders[n.order_id];
    m.setPosition(pos); m.setIcon(riderIcon(alert));
    m.set('html', '<div style="font:12px sans-serif;color:#111"><b>' + n.rider_name + '</b> → ' + n.drop_name
      + '<br>' + Math.round(n.progress * 100) + '% · ' + n.minutes_remaining.toFixed(0) + ' min left · dose '
      + n.dose_so_far.toFixed(0) + '/' + n.dose_total.toFixed(0) + (alert ? '<br><b style="color:#b3261e">Spike alert on route</b>' : '') + '</div>');
  }});
  Object.keys(riders).forEach((id) => {{
    if (!seen.has(id)) {{ riders[id].setMap(null); delete riders[id]; if (routes[id]) {{ routes[id].line.setMap(null); delete routes[id]; }} }}
  }});
  if (!fitted && data.length) {{ map.fitBounds(bounds, 50); fitted = true; }}
}}
function initMap() {{
  map = new google.maps.Map(document.getElementById('map'), {{
    styles: STYLE, center: {{ lat: 28.56, lng: 77.22 }}, zoom: 11, disableDefaultUI: true, zoomControl: true, gestureHandling: 'greedy'
  }});
  refresh(); setInterval(refresh, 3000);
}}
"""
    return _BASE.format(height=height, style=json.dumps(DARK_STYLE), script=script, key=key)
