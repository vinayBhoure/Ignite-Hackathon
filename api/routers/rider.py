"""Rider app: /rider (today's deliveries + alerts), /rider/order/{id} (live
turn-by-turn navigation) and /rider/settings. Signed-in riders only.

Server-rendered shells; every number comes from the API via
api/static/rider.js and nav.js - no scoring logic here (CLAUDE.md rule 1).
"""

from __future__ import annotations

import html

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from api.config import Settings, get_settings
from api.security import current_session
from core.auth import Session

router = APIRouter(tags=["rider"])

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;'
    '12..96,700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
)

_LEGEND = """
<div class="legend"><span><i style="background:#4FD48A"></i>Good</span><span><i style="background:#9DC64A"></i>Satisfactory</span>
<span><i style="background:#E8C23D"></i>Moderate</span><span><i style="background:#E8A33D"></i>Poor</span>
<span><i style="background:#E4553F"></i>Very poor</span><span><i style="background:#A52C24"></i>Severe</span></div>
"""

_METHOD = """
<p class="note"><b>Data and method.</b> Air quality is <b>replayed</b> historical PM2.5 (Delhi NCR, Jan 2021) on a demo
clock - not live. Routes and traffic are <b>live</b> from Google. Readings marked <b>Simulated</b> are spikes injected
for the demo. Coverage under 80% is low confidence. Figures show exposure reduction, not a health or medical claim.</p>
"""


def _rider(request: Request) -> Session | RedirectResponse:
    session = current_session(request, "rider")
    if session is None:
        return RedirectResponse("/?role=rider", status_code=303)
    return session


def _page(title: str, session: Session, body: str, *, scripts: str = "", body_class: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#101314">
<title>{html.escape(title)} · Aevora</title>
<link rel="manifest" href="/static/manifest.json">
{_FONTS}
<link rel="stylesheet" href="/static/aevora.css">
</head>
<body class="{body_class}">
{body}
{scripts}
</body>
</html>"""


def _top(session: Session, back: bool = False) -> str:
    left = '<a class="brand" href="/rider">' + ("&larr; " if back else "") + "Aevora</a>"
    return (
        f'<header class="top">{left}<div class="who"><b>{html.escape(session.name)}</b>'
        f'<a href="/rider/settings">Settings</a><a href="/logout?role=rider">Sign out</a></div></header>'
    )


@router.get("/rider", response_class=HTMLResponse, include_in_schema=False)
def rider_home(request: Request):
    session = _rider(request)
    if isinstance(session, RedirectResponse):
        return session
    first = html.escape(session.name.split()[0])
    body = f"""
{_top(session)}
<main class="wrap">
  <div class="replay"><span class="chip replay">Replay</span><span id="clock" class="mono">&nbsp;</span>
    <span>air replayed · traffic live</span></div>
  <h1>Hi, {first} {html.escape(session.name.split()[-1])}</h1>
  <p class="muted">Deliveries assigned to you by dispatch.</p>
  <div id="orders"><div class="empty">Loading your deliveries&hellip;</div></div>
  <h2>Air alerts</h2>
  <div id="alerts"><p class="muted">Loading&hellip;</p></div>
  <h2>Notifications</h2>
  <button id="enable-push" class="btn ghost block" type="button">Enable push notifications</button>
  <p id="push-status" class="muted"></p>
  {_LEGEND}
  {_METHOD}
</main>"""
    return _page("Today", session, body, scripts='<script src="/static/rider.js"></script>')


@router.get("/rider/order/{order_id}", response_class=HTMLResponse, include_in_schema=False)
def rider_order(order_id: str, request: Request, settings: Settings = Depends(get_settings)):
    session = _rider(request)
    if isinstance(session, RedirectResponse):
        return session
    oid = html.escape(order_id, quote=True)
    key = html.escape(settings.google_maps_browser_key or "", quote=True)
    body = f"""
<div class="navshell">
  {_top(session, back=True)}
  <div id="map"></div>
</div>
<div class="turn" id="turn"><div class="arrow" id="turn-arrow">&uarr;</div>
  <div><div class="dist" id="turn-dist">&ndash;</div><div class="text" id="turn-text">Loading route&hellip;</div></div></div>
<div class="spike" id="spike" role="alert">
  <div><b id="spike-title">Very poor air ahead</b> <span id="spike-src" class="chip sim">Simulated</span></div>
  <div class="muted" id="spike-body" style="color:#F2C9C2">A PM2.5 spike is on your route.</div>
  <div class="row"><button class="btn clean" id="see-reroute" type="button">See cleaner route</button>
    <button class="btn ghost" id="dismiss-spike" type="button">Dismiss</button></div>
</div>
<div class="arrived" id="arrived"><b style="font-size:18px">Delivered</b>
  <p class="muted" id="arrived-text" style="margin:4px 0 12px"></p><a class="btn clean" href="/rider">Back to deliveries</a></div>
<section class="sheet" id="sheet" style="position:fixed;left:0;right:0;bottom:0;z-index:4">
  <div class="stats">
    <div class="stat"><div class="v" id="s-eta">&ndash;</div><div class="l">ETA (IST)</div></div>
    <div class="stat"><div class="v" id="s-min">&ndash;</div><div class="l">min left</div></div>
    <div class="stat"><div class="v" id="s-km">&ndash;</div><div class="l">km left</div></div>
    <div class="stat"><div class="v" id="s-dose">&ndash;</div><div class="l">dose so far / trip</div></div>
  </div>
  <div class="ahead" id="ahead"></div>
  <div class="foot"><span><span class="chip replay">Replay</span> <span id="s-clock" class="mono"></span></span>
    <span id="s-conf"></span><button class="btn ghost" id="recenter" type="button" style="padding:5px 10px;font-size:12px">Recenter</button></div>
</section>
<div class="modal" id="modal"><div class="box">
  <b style="font-size:17px">Reroute around the spike?</b>
  <p class="muted" id="m-msg" style="margin:6px 0 0"></p>
  <div class="cmp"><div><div class="muted">Stay on route</div><div class="v" id="m-cur">&ndash;</div></div>
    <div class="best"><div class="muted">Cleaner route</div><div class="v" id="m-new">&ndash;</div></div></div>
  <div style="display:flex;gap:8px"><button class="btn clean" id="m-take" type="button" style="flex:1">Take cleaner route</button>
    <button class="btn ghost" id="m-keep" type="button">Keep current</button></div>
</div></div>
"""
    scripts = (
        f'<script>window.AEVORA = {{orderId: "{oid}", mapsKey: "{key}"}};</script>'
        '<script src="/static/nav.js"></script>'
    )
    return _page("Navigate", session, body, scripts=scripts, body_class="nav")


@router.get("/rider/settings", response_class=HTMLResponse, include_in_schema=False)
def rider_settings(request: Request):
    session = _rider(request)
    if isinstance(session, RedirectResponse):
        return session
    body = f"""
{_top(session, back=True)}
<main class="wrap">
  <h1>Settings</h1>
  <p class="muted">Signed in as <b style="color:var(--bone)">{html.escape(session.name)}</b>
    (<span class="mono">{html.escape(session.sub)}</span>).</p>
  <h2>Notifications</h2>
  <p class="muted">Push lets dispatch warn you about bad air ahead even when this page is closed.
  If you decline, alerts still appear inside the app.</p>
  <button id="enable-push" class="btn primary block" type="button">Enable push notifications</button>
  <p id="push-status" class="muted"></p>
  <h2>Severity scale (PM2.5, &micro;g/m&sup3;)</h2>
  {_LEGEND}
  {_METHOD}
  <p style="margin-top:20px"><a class="btn ghost block" href="/logout?role=rider">Sign out</a></p>
</main>"""
    return _page("Settings", session, body, scripts='<script src="/static/rider.js"></script>')
