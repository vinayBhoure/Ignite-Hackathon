# Manual testing guide

Everything below was pushed to `main`. This is how to run it and click
through it yourself.

## 1. One-time setup

```bash
cd Ignite-Hackathon
python -m venv .venv               # if you don't already have .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Your `.env` (project root, gitignored) needs at minimum:
`NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `GOOGLE_MAPS_API_KEY` -
these were already filled in before this session started. `VAPID_PUBLIC_KEY`
/ `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` were added during this session (real
generated keys) so push works. `GEMINI_API_KEY` is still empty - not needed
yet since everything runs against mocks/core directly, no Gemini calls exist
yet.

## 2. Automated tests (do this first)

```bash
.venv/Scripts/python.exe -m pytest -q
```

Expect `62 passed`. These hit the real Neo4j (AuraDB), so you need network
access and a valid `.env`. If AuraDB is paused (free tier), the first query
will just be slow to wake it, not fail.

## 3. Start both servers

**Port 8000 is likely blocked on Windows** (Hyper-V/WSL port reservation -
we hit `WinError 10013` on this machine). Use 8010 instead, or run
`netsh interface ipv4 show excludedportrange protocol=tcp` to check.

Terminal 1 - API:
```bash
.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8010
```

Terminal 2 - Streamlit console:
```bash
.venv/Scripts/python.exe -m streamlit run ui/app.py --server.port 8501
```

## 4. API checklist (http://127.0.0.1:8010/docs)

- [ ] `/health` returns `{"status": "ok", "use_mocks": true}`
- [ ] `POST /api/places/resolve` with `{"query": "cp"}` returns one confident candidate
- [ ] `POST /api/places/resolve` with `{"query": "asdf"}` returns 2 low-confidence candidates, `needs_pick: true`
- [ ] `POST /api/routes/plan` with real lat/lng returns 3 routes + a recommendation
- [ ] `GET /api/zones` returns a zone list with `band`/`confidence`/`simulated`
- [ ] `GET /api/demo/clock` then `POST /api/demo/clock {"action":"pause"}` - `running` flips to `false`
- [ ] `POST /api/demo/spike {"h3": "<any h3 from /api/zones>", "pm25": 300, "duration_min": 30}` then re-`GET /api/zones` - that zone now shows `simulated: true`
- [ ] `GET /api/alerts` - lists real alerts (there are 2 pre-existing ones tied to your teammate's `rider-1` seed data)
- [ ] `GET /sw.js` - JS content, `content-type: application/javascript`, `cache-control: no-cache`
- [ ] `GET /rider?rider_id=demo-rider-1` - HTML page renders

## 5. Streamlit console checklist (http://127.0.0.1:8501)

**Home**
- [ ] Replay bar shows a date inside 2021-01-09 to 2021-01-30, with Pause/Resume, speed dropdown, Jump to start, Reset spikes
- [ ] Severity legend (6 colored chips) renders
- [ ] KPI row shows 4 numbers
- [ ] Zone map renders as colored hexagons over Delhi NCR
- [ ] Pick a zone in "Zone to spike", inject a spike, page reruns and that zone turns dark red with a Simulated badge
- [ ] Active alerts panel lists alerts with an Acknowledge button; clicking it removes that alert from the list

**Route Planner**
- [ ] Search Pickup "cp", Drop "cyber hub", click Find routes
- [ ] Green recommendation banner appears with a dose delta and extra minutes
- [ ] 3 route cards show Time / Dose / Window margin / coverage% / confidence as **separate** numbers (not one blended score)
- [ ] "Zone breakdown" expander on a card lists the zones with PM2.5 per zone
- [ ] Map below shows two markers (A/B) on a real Google map
- [ ] **Known gap:** the route line itself won't draw - Google's legacy Directions API isn't enabled on this project's key yet. You'll see a straight blue line instead (a graceful fallback we added) plus a console warning. Fix: in Google Cloud Console, enable the "Directions API" for the key in `.env` (`GOOGLE_MAPS_API_KEY`). We can't do this ourselves - it's your Cloud Console.
- [ ] Try a nonsense pickup query (e.g. "zzz123") - a "Confirm pickup" dropdown with 2 guesses appears instead of erroring

**Monitor**
- [ ] "Zones and AQI" tab: slider moves independently of the live replay clock; map and zone list update as you drag it
- [ ] "Alerts log" tab: Status filter (All/new/acked) and Rider id filter both work; Acknowledge works here too

## 6. Rider app checklist (http://127.0.0.1:8010/rider?rider_id=rider-1)

- [ ] Page loads, shows `rider-1` badge, replay bar, legend
- [ ] "Active alerts" section shows the 2 real alerts for `rider-1` (from your teammate's seed data) with Acknowledge buttons that work
- [ ] Click "Enable push notifications" - Chrome will prompt for notification permission (works over `http://127.0.0.1`/`localhost` even without HTTPS, since browsers treat localhost as a secure context; a real deploy needs HTTPS, which Render provides)
- [ ] After granting permission, the status line changes to "Push notifications enabled for rider rider-1."
- [ ] `/rider/settings` and `/rider/order/order-1` both load without errors

## 7. Things that still need you, not more code

- **Directions API** - enable it (or migrate to the newer Routes API) in Google Cloud Console for the key in `.env`, per the Route Planner gap above.
- **T2.10 sync with Track A** - `core/places`, `core/routing`, `core/exposure`, `core/dispatch`, `core/kg` don't exist yet. Everything above runs on `api/mocks/*` (USE_MOCKS=true, the default). Nothing can be swapped to real scoring until your teammate ships those modules.
- **Deploy (T2.13/T2.14)** - two Render web services, per `render.yaml`. Needs your Render dashboard; I can prep config but can't click through your account.
- **Push at scale** - works for a single browser subscription now; hasn't been tested with multiple riders/devices or an actual spike-triggers-push end-to-end run (that needs a seeded active route + a live browser subscription at the same time, which is a two-person test).
