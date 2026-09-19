"""Minimal rider app (T1.10): /rider, /rider/order/{id}, /rider/settings.

Plain server-rendered HTML, no templating engine - deliberately thin per the
plan (P0 is push + in-app alert fallback; the full exposure-meter UI is P1).
No scoring logic here (CLAUDE.md architecture rule 1): every dynamic value
comes from the already-built core/ or the already-wired API endpoints, and
the page just calls them client-side via api/static/rider.js.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["rider"])

_STYLE = """
<style>
  body { font-family: system-ui, sans-serif; max-width: 480px; margin: 0 auto; padding: 16px; background: #0b1220; color: #e6ecf5; }
  h1 { font-size: 1.25rem; }
  .replay-bar { background: #1c2942; border-radius: 8px; padding: 8px 12px; font-size: 0.85rem; margin-bottom: 12px; }
  .replay-bar .tag { background: #f6a609; color: #1c1200; border-radius: 4px; padding: 2px 6px; font-weight: 600; margin-right: 6px; }
  .legend { display: flex; flex-wrap: wrap; gap: 6px; font-size: 0.75rem; margin: 8px 0 16px; }
  .legend span { padding: 2px 8px; border-radius: 10px; color: #0b1220; font-weight: 600; }
  .good { background: #4caf50; } .satisfactory { background: #a3d977; }
  .moderate { background: #f6c445; } .poor { background: #f28c3a; }
  .very_poor { background: #e5533d; } .severe { background: #8b1e3f; color: #fff; }
  button { background: #3b82f6; color: white; border: none; border-radius: 6px; padding: 10px 14px; font-size: 0.95rem; }
  .muted { color: #93a3bd; font-size: 0.85rem; }
  .toast { background: #1c2942; border-left: 4px solid #e5533d; border-radius: 6px; padding: 10px; margin-bottom: 8px; font-size: 0.85rem; }
  .toast button { margin-left: 8px; padding: 4px 8px; font-size: 0.75rem; }
  a { color: #7db4ff; }
  .badge { font-size: 0.7rem; background: #f6a609; color: #1c1200; border-radius: 4px; padding: 1px 6px; }
  nav a { margin-right: 12px; }
</style>
"""


def _layout(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <link rel="manifest" href="/static/manifest.json" />
  {_STYLE}
</head>
<body>
  <div class="replay-bar">
    <span class="tag">Replay</span>
    Pollution shown is <strong>historical data replayed</strong> for this demo, not live.
    Traffic and timing are live from today. <a href="/rider/settings">Settings</a>
  </div>
  <div class="legend">
    <span class="good">Good</span><span class="satisfactory">Satisfactory</span>
    <span class="moderate">Moderate</span><span class="poor">Poor</span>
    <span class="very_poor">Very poor</span><span class="severe">Severe</span>
  </div>
  <nav><a href="/rider">Home</a><a href="/rider/settings">Settings</a></nav>
  {body}
  <p class="muted">Coverage below 80% is shown as low confidence. Scores are exposure reduction estimates,
  not a medical or health claim. <a href="/rider/settings">Data and method</a></p>
  <script src="/static/rider.js"></script>
</body>
</html>"""


@router.get("/rider", response_class=HTMLResponse)
def rider_home() -> str:
    body = """
    <h1>Rider <span id="rider-id" class="badge"></span></h1>
    <p>Enable push so you're alerted the moment a route you're on crosses into
    unhealthy air, and get a reroute suggestion.</p>
    <button id="enable-push">Enable push notifications</button>
    <p id="push-status" class="muted"></p>
    <h2>Active alerts</h2>
    <div id="toasts"><p class="muted">Loading...</p></div>
    """
    return _layout("Rider - Exposure-Aware Fleet Routing", body)


@router.get("/rider/order/{order_id}", response_class=HTMLResponse)
def rider_order(order_id: str) -> str:
    body = f"""
    <h1>Order {order_id}</h1>
    <p class="muted">Full order detail (route map, ETA, dose) is a later screen.
    This view exists so an alert can deep-link somewhere concrete.</p>
    <p><a href="/rider">&larr; Back to alerts</a></p>
    """
    return _layout(f"Order {order_id} - Rider", body)


@router.get("/rider/settings", response_class=HTMLResponse)
def rider_settings() -> str:
    body = """
    <h1>Settings</h1>
    <p>Rider id: <span id="rider-id" class="badge"></span> (from the <code>?rider_id=</code>
    link your dispatcher sent, or a demo id if you opened this directly).</p>
    <button id="enable-push">Enable push notifications</button>
    <p id="push-status" class="muted"></p>
    <h2>Data and method</h2>
    <p class="muted">PM2.5 zones come from a historical sensor dataset, replayed on a demo clock -
    they are <strong>not live</strong>. Google traffic/routing is live from today. Spikes you see
    labeled "Simulated" are injected for the demo, not real sensor readings. Scores show exposure
    reduction, never a health or medical claim.</p>
    """
    return _layout("Settings - Rider", body)
