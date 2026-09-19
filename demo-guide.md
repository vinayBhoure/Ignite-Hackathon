# Aevora — Demo Guide (user journeys)

A 5–6 minute walkthrough told through the two people who use Aevora: **Priya, the dispatcher** at the South Delhi Hub, and **Rider 1**, who is out on the road.

Each step gives:
- **Do**: exactly what to click
- **See**: what should appear
- **Say**: the one line to tell the judges

Live traffic changes minute to minute, so the minutes and dose numbers you get will vary a little.

---

## Before you start (5 minutes before judging)

1. **Start both services** (two terminals, from the repo root, with `.venv` active):
   ```bash
   uvicorn api.main:app --port 8010
   streamlit run ui/app.py --server.port 8501
   ```
2. **Wake AuraDB.** Open `http://127.0.0.1:8010/health`. The first request after a long idle can take a few seconds.
3. **Use two browser windows side by side:**
   - Left, dispatcher: `http://127.0.0.1:8010/`
   - Right, rider: `http://127.0.0.1:8010/?role=rider`
   - Separate *windows*, not tabs, so both stay visible.
4. **Reset the stage** in the console:
   - Click **Demo start**.
   - Click **Clear spikes**.
   - Set the speed dropdown to **10×**.
   - Leave the clock **paused**.
   - Check that **Live fleet** shows **0** deliveries on the road.

   If old deliveries are still showing: press **Play** at **600×** for a few seconds until they arrive, then click **Demo start** again.

### Demo accounts

| Who | Sign in with | Password |
|---|---|---|
| Dispatcher | `dispatch@aevora.in` | `aevora-dispatch` |
| Rider 1 | `+91 99000 00001` | `aevora-rider` |
| Riders 2–8 | `+91 99000 00002` … `00008` | `aevora-rider` |

The sign-in page's **Demo accounts** panel has **Fill dispatcher** and **Fill rider 1** buttons.

---

## Act 1 — The dispatcher starts the shift (≈45 s)

| | |
|---|---|
| **Do** | Left window: watch the intro (or press any key to skip). Choose **Dispatcher** → sign in. |
| **See** | The Aevora scene (a rider clearing the smog), then the **Live fleet** console: replay clock, KPIs, a dark map of Delhi, and "Nobody is out yet". |
| **Say** | *"Priya runs dispatch for 8 riders at the South Delhi Hub. Delhi's air is among the worst on earth, and her riders breathe it for 10 hours a day."* |

**Point at:**
- The amber **Replay** chip and clock (*Wed 27 Jan, 14:00 IST*): *"Pollution is real sensor history, replayed. Traffic is live from Google today."*
- The **PM2.5 legend** and the **Live Google traffic** chip.

## Act 2 — Planning a delivery (≈75 s)

| | |
|---|---|
| **Do** | Sidebar → **Plan & dispatch**. Pickup is already *South Delhi Hub*. Drop: `Karol Bagh`. Click **Find cleanest route**. |
| **See** | A recommendation banner, a dark Google map with the recommended route in **green** and the alternatives in **grey**, zone circles coloured by PM2.5, and **Compare routes** cards. |
| **Say** | *"Google gives us up to three live, traffic-aware routes for a two-wheeler. Aevora scores each one against a pollution graph in Neo4j, zone by zone, using the moment the rider will actually reach each zone."* |

**Point at the route cards:**
- **Time, dose, window margin and coverage are separate numbers.** *"We never blend them into one 'safety score'. The dispatcher sees the trade-off."*
- The **coverage %** and the **high/low confidence** chip. *"Where sensors are thin, we say so."*
- The **Turn by turn** list at the bottom: real Google instructions.

| | |
|---|---|
| **Do** | Keep the recommended route. Rider: **Rider 1**. Click **Dispatch to rider**. |
| **See** | "Dispatched ord-… to Rider 1". On **Live fleet** the delivery appears on the map and under **On the road**. |

## Act 3 — The rider's shift begins (≈45 s)

| | |
|---|---|
| **Do** | Right window: choose **Rider**, sign in as `+91 99000 00001` / `aevora-rider`. |
| **See** | "Hi, Rider 1" and the delivery card: *South Delhi Hub → Karol Bagh*, with ETA, minutes, dose, coverage and a **Navigate** button. |
| **Do** | Click **Enable push notifications** and allow them. Then click **Navigate**. |
| **See** | Full-screen navigation: next-turn banner (e.g. *"40 m · Make a U-turn…"*), the rider arrow on the route, and a bottom sheet with **ETA · min left · km left · dose so far / trip**. |
| **Say** | *"The rider gets normal turn-by-turn navigation. The difference is that the route was chosen for their lungs as well as the clock."* |

## Act 4 — The air changes (≈60 s)

| | |
|---|---|
| **Do** | Left window, **Live fleet** → scroll to **Demo: spike the air ahead of a rider**. Delivery: *Rider 1 → Karol Bagh*. Zone: one marked **avoidable** that's **5+ minutes ahead** (it's selected by default). Keep **320 µg/m³**. Click **Inject simulated spike**. |
| **See** | Left: the **Alert feed** shows *"Severe air ahead of rider-1 … Simulated"*. Right, within a few seconds: a red **"Severe air ahead · Simulated"** banner on the rider's navigation, and a push notification if enabled. |
| **Say** | *"A pollution spike appears on the rider's path, say a garbage fire. It's clearly labelled **Simulated**; we never pass off injected data as real. Aevora only alerts when the air gets **worse than what we planned for**. It doesn't nag about air we already accounted for."* |

> Pick a zone marked **avoidable**. Zones marked **on every route** can't be routed around, so the rider will honestly be told to keep their route.

## Act 5 — The rider decides (≈45 s)

| | |
|---|---|
| **Do** | Right window: **See cleaner route**. |
| **See** | A modal comparing **Stay on route** and **Cleaner route**, e.g. *"Reroute adds +2 min and cuts exposure 22% for the rest of this ride."* |
| **Say** | *"No black box. The rider sees exactly what it costs: two extra minutes for a fifth less PM2.5."* |
| **Do** | **Take cleaner route**. |
| **See** | The new live route is drawn, the next turn updates, the trip dose drops, and the alert clears. |

## Act 6 — On the road to arrival (≈45 s)

| | |
|---|---|
| **Do** | Left window: press **Play** (at **10×** or **30×**). Keep both windows visible. |
| **See** | Right: the arrow moves along the real roads, the travelled path turns grey, and the next turn, km left and **dose so far** count up. Left: the rider moves on the fleet map and the progress bar fills. |
| **Say** | *"Everything runs on a replay clock stored in Neo4j, so it survives restarts. At 30× a 40-minute ride takes about 80 seconds."* |
| **See (end)** | **"✓ Arrived · Karol Bagh"** with **"Delivered … dose 52"**, and the rider shows as available again on the console. |

## Act 7 — Trust and transparency (≈30 s, optional)

| | |
|---|---|
| **Do** | Sidebar → **Air & alerts**. Drag the **Replay moment** slider. Switch to **Alert log**. |
| **See** | The zone layer at any moment in January 2021 (with confidence and sensor counts), plus every alert with its status and a **Simulated / Sensor reading** label. |
| **Say** | *"Every number traces back to a zone reading in the graph. **Data and method** at the bottom of every screen says exactly what's live, what's replayed and what's simulated."* |

---

## If something goes wrong

| Symptom | Fix |
|---|---|
| Typing on the sign-in page does nothing | The intro is still playing. Press any key or **Skip** first. |
| Console says "Dispatcher sign-in required" | Click **Go to sign in**. You'll come straight back. |
| Map is plain grey for a second | Tiles are still loading. Wait 2–3 s. |
| "Your current route is still the best option" | The spiked zone is on every route. Click **Clear spikes** and pick a zone marked **avoidable**. |
| No push notification | The in-app banner and alert list still work. Push needs browser permission (and HTTPS off localhost). |
| "Couldn't get routes" | Check internet and the Google key (Routes, Geocoding and Maps JS APIs enabled). |
| `WinError 10013` on port 8000 | Use `--port 8010` as above. |
| An old delivery reappears after **Demo start** | Press **Play** at 600× until it arrives, then **Demo start** again. |

## Reset between runs (30 s)

1. **Clear spikes**.
2. Let any rider arrive: **Play** at 600×.
3. **Demo start**.
4. Set speed to **10×** and pause.
5. For a fresh story each run, use another rider (Rider 2 → `+91 99000 00002`) or another drop that has avoidable zones: **Mayur Vihar**, **Okhla**, **Saket**.

## One-line pitch

**Aevora routes delivery riders around Delhi's worst air — live Google traffic plus a Neo4j pollution graph. It cuts each rider's PM2.5 dose while still meeting the delivery window, and it tells the dispatcher and the rider exactly what the cleaner route costs.**
