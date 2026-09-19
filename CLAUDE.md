# CLAUDE.md

Guidance for Claude (and any coding agent) working in this repo. Read this first, then `docs/prd.md`.

## Project

**Exposure-Aware Fleet Routing (Delhi NCR).** Routes and assigns delivery riders by time **and** PM2.5 exposure, so delivery windows are still met while each rider's cumulative dose drops and is spread fairly.

- Google Routes API generates 1 to 3 traffic-aware candidate routes.
- Neo4j scores each route against a zone-level PM2.5 layer (H3 zones, built from historical sensor CSVs, **replayed** as a timeline).
- Gemini normalizes place queries and writes one-sentence grounded explanations.
- Web push alerts riders on spike and reroute.

Demo is a **replay** of historical data, and the UI must say so. Source of truth: `docs/prd.md` (PDF copy in `docs/`). If code and PRD disagree, stop and ask.

## Team and tracks

| Track | Owner | Scope |
|---|---|---|
| A: Core package | Teammate | `core/` scoring brains: places, routing, exposure, kg, dispatch, seeding |
| B: Front doors | Vinay | FastAPI service, Streamlit console, replay clock, spike injector, alerts, web push, minimal rider page |

**Stay in your lane.** Track B owns `api/`, `ui/`, `core/clock/`, `core/alerts/`. Do not edit Track A modules; raise it instead. `core/db/client.py` is shared: reuse it if it exists.

Implementation plan for Track B: `docs/TrackB_Implementation_Plan.md`. **API ships before UI**, because Track A tests against it.

## Stack

Python, FastAPI (API, rider app, push, clock), Streamlit (dispatcher console), Neo4j AuraDB, Google Maps (Geocoding, Routes, Maps JS), Gemini (Flash-class), H3 zones, Render hosting (two web services). Check `requirements.txt` for pinned versions before adding a dependency.

## Repository layout

Current (verify with `ls` before assuming):

```text
dataset/cleaned/   aggregated_15min.csv, zone_readings_interpolated.csv, zoned_readings.csv
dataset/recent-20/ raw subset
docs/              PRD (pdf + prd.md)
app.py             existing entry point (verify what it does)
test_connections.py  connection smoke test (verify what it checks)
render.yaml, requirements.txt, .env.example, README.md
```

Target layout from the PRD (create only as the plan says):

```text
core/    places/ routing/ exposure/ dispatch/ kg/ alerts/ clock/ db/ (+ tests)
etl/     profile, clean, aggregate, zones, load, seed
api/     FastAPI app, rider app static files, sw.js
ui/      Streamlit entry + pages/ (order-prefixed)
tests/
```

Do not move or rename existing files (for example `app.py`) without approval.

## Commands

Verify against the repo before relying on these.

```bash
pip install -r requirements.txt
python test_connections.py                      # sanity-check Neo4j / keys
uvicorn api.main:app --reload --port 8000       # API (once api/ exists)
streamlit run ui/app.py                         # console (once ui/ exists)
pytest                                          # tests
```

Render start commands (PRD §15):

```text
streamlit run ui/app.py --server.port $PORT --server.address 0.0.0.0
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

## Environment

Copy `.env.example` to `.env`. **Never commit `.env` or print secrets.**

`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `GOOGLE_MAPS_SERVER_KEY`, `GOOGLE_MAPS_BROWSER_KEY` (referrer-restricted), `GEMINI_API_KEY`, `TAVILY_API_KEY` (if the template has it), `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`, `DEMO_AREA_BOUNDS`, `H3_RES`, `SENSOR_RADIUS_KM`, and `USE_MOCKS` (Track B mock flag).

Any new variable must also be added to `.env.example`.

## Architecture rules (non-negotiable)

1. **No scoring logic in `api/` or `ui/`.** Both call `core/`. Streamlit calls `core` directly; REST serves the rider app and scripted tests.
2. `core/` functions are plain, importable, and independent of Streamlit and FastAPI.
3. Streamlit reruns on every interaction: keep state in `st.session_state` and Neo4j, not module globals.
4. Google and Gemini calls live **behind `core/`** so both UIs share caching and keys.
5. Load **aggregates only** into Neo4j. Never raw 2.5-second rows.
6. **Geocoder is the source of truth for coordinates.** Gemini never is.
7. The replay clock is **derived, not ticked**: `now = anchor_ts + speed * (wall_now - wall_anchor)`, stored in one `DemoClock` node. It must survive Render sleep.
8. No local files for state (Render disk is ephemeral). State lives in Neo4j.
9. Store only derived scores and zone lists from Google routes, not raw geometry beyond the session. Draw routes on Google Maps only.

## Domain facts

**Dose** (µg·h/m³, relative): `sum(C_zone(t_arrival) * dt_hours) * A * (1 - F_mask)`. Use PM2.5 concentration, not AQI. `A` = activity factor (default 1.0). `F_mask` = 0 for the "unmasked" baseline. Activity and mask factors are applied in the **service layer**, not in Cypher.

**Zone PM2.5:** inverse-distance-squared weighting of sensors within R (default 3 km). 2 or more sensors = High confidence, 1 = Medium, 0 = no reading (zone excluded).

**Decision rule per order:** get up to 3 alternatives → compute ETA, window margin, dose, coverage → drop routes with margin below the buffer (default 2 min) → pick lowest dose (tie: shorter duration) → if none qualifies, recommend the fastest with a "window at risk" flag. Always show the delta vs the fastest route (dose % and minutes).

**Severity bands (PM2.5 µg/m³):** Good 0-30, Satisfactory 31-60, Moderate 61-90, Poor 91-120, Very poor 121-250 (alert threshold), Severe above 250. These are display heuristics on 15-minute medians.

**Spikes:** stored as separate `ZoneReading` with `source = simulated`, always labeled "Simulated". Alerts dedupe: same rider + zone within 15 replay-minutes.

**Neo4j labels:** Zone, Sensor, ZoneReading, Hub, Rider, Order, Route, Alert, PushSub, DemoClock (operational); Place, Alias, GRAPStage, Rule, VehicleType, MaskType (knowledge). Zone readings are keyed by `(h3, ts)`. Full schema and constraints: PRD §12.

## UI and copy rules

- Show **time, dose and window margin as separate numbers**. No blended "safety score".
- Show coverage % on every score. Below 80% = **low confidence**.
- Say "exposure reduction", never "health protection" or medical claims.
- Every screen: replay clock bar with a "Replay" label, PM2.5 color legend, confidence and "Simulated" badges, link to Data and method.
- Google traffic is live from the demo day while pollution is replayed historical data. Disclose this on the Data and method page.

## Working rules

- **Never assume** requirements, APIs, schema, permissions or behavior. Verify in the code or ask.
- **Plan first.** Use `/generate-plan`. No implementation until the plan is explicitly approved.
- Keep changes **small, incremental, reversible**. Do not touch unrelated code.
- Track A and Track B share **frozen schemas** (`core/schemas`). Only additive changes after freeze; both tracks review.
- Mock-first: Track B builds against mocks (`USE_MOCKS=true`), then swaps to real `core/` calls at the sync point. Fix handoff breakage before adding features.
- Do not read large CSVs in full. Use `pandas.read_csv(..., nrows=N)` or `head`.
- Never log or print push subscription endpoints or keys.

## Git

- Branch: `<type>/<module>/<short-description>` (types: feature, fix, refactor, chore, docs).
- Base branch: confirm with Vinay (`main` or `staging`).
- Conventional Commits, one logical change each, e.g. `feat(clock): add derived replay clock`.
- Never force-push shared branches. Never commit `.env`, keys or `dataset/` outputs unless already tracked.

## Testing

- Unit tests for pure logic: clock math, severity bands, alert dedupe, dose.
- Integration tests against AuraDB for clock, spike, alert and push-subscription persistence.
- Contract tests: mock and real responses validate against the same schemas.
- Push E2E: page closed, browser running, alert shown within 10 s of the tick.
- A task is done only when validation passes, tests pass, and acceptance criteria are met.

## Known constraints

- Streamlit cannot host a service worker, so push lives in the FastAPI-served rider page (`/rider`, `/rider/order/{id}`, `/rider/settings`, `/sw.js` at root).
- Web Push needs HTTPS (Render provides it), VAPID keys and explicit permission. iOS needs the site added to the Home Screen; demo on a laptop browser by default.
- Render free tier sleeps: wake both services before any demo.
- AuraDB Free can pause on inactivity: check it before a demo.
- Out of MVP: own OSM/GDS routing, live AQI fallback, ML forecasting, native apps, payments, multi-tenant accounts.