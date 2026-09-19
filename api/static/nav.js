// Live rider navigation. Position comes from the server, derived from the
// replay clock (departure + elapsed replay time along the real route); this
// page draws it on a Google map, shows the next turn from the Routes API
// steps, and offers a cleaner reroute when a spike appears ahead.
(function () {
  "use strict";

  const CFG = window.AEVORA || {};
  const POLL_MS = 3000;
  const BANDS = {
    good: "#4FD48A", satisfactory: "#9DC64A", moderate: "#E8C23D",
    poor: "#E8A33D", very_poor: "#E4553F", severe: "#A52C24",
  };
  const ARROWS = {
    TURN_LEFT: "←", TURN_RIGHT: "→", TURN_SLIGHT_LEFT: "↖", TURN_SLIGHT_RIGHT: "↗",
    TURN_SHARP_LEFT: "↙", TURN_SHARP_RIGHT: "↘", UTURN_LEFT: "↶", UTURN_RIGHT: "↷",
    ROUNDABOUT_LEFT: "⟲", ROUNDABOUT_RIGHT: "⟳", RAMP_LEFT: "↖", RAMP_RIGHT: "↗",
    FORK_LEFT: "↖", FORK_RIGHT: "↗", MERGE: "⤴", STRAIGHT: "↑", DEPART: "↑",
    NAME_CHANGE: "↑",
  };
  const STYLE = [
    { elementType: "geometry", stylers: [{ color: "#1c2022" }] },
    { elementType: "labels.text.fill", stylers: [{ color: "#8e948f" }] },
    { elementType: "labels.text.stroke", stylers: [{ color: "#15181a" }] },
    { featureType: "poi", stylers: [{ visibility: "off" }] },
    { featureType: "transit", stylers: [{ visibility: "off" }] },
    { featureType: "road", elementType: "geometry", stylers: [{ color: "#2f3537" }] },
    { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#454c4e" }] },
    { featureType: "road.arterial", elementType: "labels.text.fill", stylers: [{ color: "#a7ada7" }] },
    { featureType: "water", elementType: "geometry", stylers: [{ color: "#101b20" }] },
  ];

  let map, routeId = null, path = [], cum = [], doneLine, aheadLine, casing, riderMarker, destMarker;
  let zoneCircles = [], follow = true, fitted = false, lastPos = null, animFrame = null;
  let dismissed = new Set(), current = null, preview = null, busy = false;

  const $ = function (id) { return document.getElementById(id); };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmtDist(m) { return m < 950 ? Math.max(10, Math.round(m / 10) * 10) + " m" : (m / 1000).toFixed(1) + " km"; }
  function ist(iso, withDay) {
    const opts = { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false };
    if (withDay) { opts.weekday = "short"; opts.day = "2-digit"; opts.month = "short"; }
    return new Date(iso).toLocaleString("en-IN", opts);
  }

  async function api(p, opts) {
    const r = await fetch(p, Object.assign({ credentials: "same-origin" }, opts || {}));
    if (r.status === 401) { window.location.assign("/?role=rider&reason=expired"); throw new Error("signed out"); }
    const body = await r.json().catch(function () { return {}; });
    if (!r.ok) throw new Error((body.error && body.error.message) || ("HTTP " + r.status));
    return body;
  }

  // ------------------------------------------------------------ geometry
  function buildCum(pts) {
    const out = [0];
    for (let i = 1; i < pts.length; i++) {
      out.push(out[i - 1] + google.maps.geometry.spherical.computeDistanceBetween(pts[i - 1], pts[i]));
    }
    return out;
  }
  function splitAt(meters) {
    if (!path.length) return [[], []];
    let i = 1;
    while (i < cum.length && cum[i] < meters) i++;
    if (i >= cum.length) return [path.slice(), [path[path.length - 1]]];
    const span = cum[i] - cum[i - 1];
    const t = span ? (meters - cum[i - 1]) / span : 0;
    const mid = google.maps.geometry.spherical.interpolate(path[i - 1], path[i], t);
    return [path.slice(0, i).concat([mid]), [mid].concat(path.slice(i))];
  }

  // ------------------------------------------------------------ map
  function riderIcon(heading) {
    return {
      path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW, scale: 6.5, rotation: heading || 0,
      fillColor: "#E8A33D", fillOpacity: 1, strokeColor: "#12140F", strokeWeight: 2,
    };
  }

  function buildRoute(nav) {
    routeId = nav.route_id;
    path = google.maps.geometry.encoding.decodePath(nav.polyline);
    cum = buildCum(path);
    [casing, doneLine, aheadLine].forEach(function (l) { if (l) l.setMap(null); });
    casing = new google.maps.Polyline({ map: map, path: path, strokeColor: "#0B0F10", strokeWeight: 10, strokeOpacity: 0.9, zIndex: 1 });
    doneLine = new google.maps.Polyline({ map: map, path: [], strokeColor: "#6A716E", strokeWeight: 5, strokeOpacity: 0.9, zIndex: 2 });
    aheadLine = new google.maps.Polyline({ map: map, path: path, strokeColor: "#4FD48A", strokeWeight: 6, zIndex: 3 });
    const end = path[path.length - 1];
    if (destMarker) destMarker.setMap(null);
    destMarker = new google.maps.Marker({
      map: map, position: end, zIndex: 8, title: nav.drop_name,
      label: { text: "B", color: "#0C1A12", fontWeight: "700" },
      icon: { path: google.maps.SymbolPath.CIRCLE, scale: 11, fillColor: "#4FD48A", fillOpacity: 1, strokeColor: "#12140F", strokeWeight: 2 },
    });
  }

  function moveRider(pos) {
    const target = new google.maps.LatLng(pos.lat, pos.lng);
    if (!riderMarker) {
      riderMarker = new google.maps.Marker({ map: map, position: target, zIndex: 20, icon: riderIcon(0) });
      lastPos = target;
      if (!fitted) { map.setCenter(target); map.setZoom(15); fitted = true; }
      return;
    }
    const from = lastPos || target;
    const moved = google.maps.geometry.spherical.computeDistanceBetween(from, target);
    if (moved > 2) riderMarker.setIcon(riderIcon(google.maps.geometry.spherical.computeHeading(from, target)));
    if (animFrame) cancelAnimationFrame(animFrame);
    const start = performance.now(), dur = Math.min(POLL_MS - 200, 1600);
    (function step(now) {
      const t = Math.min((now - start) / dur, 1);
      riderMarker.setPosition(google.maps.geometry.spherical.interpolate(from, target, t));
      if (t < 1) animFrame = requestAnimationFrame(step);
    })(start);
    lastPos = target;
    if (follow) map.panTo(target);
  }

  function drawZones(nav) {
    zoneCircles.forEach(function (c) { c.setMap(null); });
    zoneCircles = nav.zones
      .filter(function (z) { return z.ahead && z.pm25 !== null && !z.estimated; })
      .map(function (z) {
        return new google.maps.Circle({
          map: map, center: { lat: z.lat, lng: z.lng }, radius: 230, zIndex: 0,
          fillColor: BANDS[z.band] || "#8E948F", fillOpacity: z.simulated ? 0.55 : 0.32,
          strokeColor: "#E8A33D", strokeWeight: z.simulated ? 2 : 0,
        });
      });
  }

  // ------------------------------------------------------------ panels
  function renderTurn(nav) {
    const steps = nav.steps || [];
    if (nav.status === "arrived" || !steps.length) {
      $("turn-arrow").textContent = "✓";
      $("turn-dist").textContent = nav.status === "arrived" ? "Arrived" : "–";
      $("turn-text").textContent = nav.drop_name;
      return;
    }
    const stepTotal = steps.reduce(function (s, x) { return s + x.distance_m; }, 0);
    const traveled = stepTotal * nav.progress;
    let endOfCurrent = 0;
    for (let i = 0; i <= nav.current_step; i++) endOfCurrent += steps[i].distance_m;
    const next = steps[nav.current_step + 1];
    $("turn-dist").textContent = fmtDist(Math.max(endOfCurrent - traveled, 0));
    if (next) {
      $("turn-arrow").textContent = ARROWS[next.maneuver] || "↑";
      $("turn-text").textContent = next.instruction.split("\n")[0];
    } else {
      $("turn-arrow").textContent = "⚑";
      $("turn-text").textContent = "Arrive at " + nav.drop_name;
    }
  }

  function renderStats(nav) {
    $("s-eta").textContent = ist(nav.eta);
    $("s-min").textContent = nav.minutes_remaining.toFixed(0);
    $("s-km").textContent = (nav.distance_remaining_m / 1000).toFixed(1);
    $("s-dose").textContent = nav.dose_so_far.toFixed(0) + "/" + nav.dose_total.toFixed(0);
    $("s-clock").textContent = ist(nav.replay_now, true) + (nav.clock_running ? " · " + nav.clock_speed + "×" : " · paused");
    $("s-conf").innerHTML = '<span class="chip ' + (nav.confidence === "high" ? "high" : "low") + '">' +
      Math.round(nav.coverage * 100) + "% coverage · " + nav.confidence + " confidence</span>";
    $("s-min").className = "v" + (nav.window_margin_min < 2 ? " bad" : "");
    const bad = nav.next_bad_zone;
    if (bad && nav.status !== "arrived") {
      const mins = Math.max((new Date(bad.reach_ts || bad.bucket) - new Date(nav.replay_now)) / 60000, 0);
      $("ahead").innerHTML = '<span class="chip" style="background:' + (BANDS[bad.band] || "#E4553F") + ';color:#12140F">' +
        esc((bad.band || "").replace("_", " ")) + "</span> PM2.5 <b class=\"mono\">" + Math.round(bad.pm25) +
        "</b> ahead in ~" + mins.toFixed(0) + " min" + (bad.simulated ? ' <span class="chip sim">Simulated</span>' : "");
    } else {
      $("ahead").innerHTML = '<span class="muted">No Poor-or-worse air reported ahead.</span>';
    }
  }

  function renderSpike(nav) {
    const open = (nav.alerts || []).filter(function (a) { return !dismissed.has(a.id); });
    const box = $("spike");
    if (!open.length || nav.status === "arrived") { box.style.display = "none"; return; }
    const a = open[0];
    $("spike-title").textContent = a.severity.replace("_", " ").replace(/^./, function (c) { return c.toUpperCase(); }) + " air ahead";
    $("spike-src").textContent = a.simulated ? "Simulated" : "Sensor reading";
    $("spike-src").className = "chip " + (a.simulated ? "sim" : "low");
    $("spike-body").textContent = "PM2.5 spike on your route at " + ist(a.ts) + " IST replay time. A cleaner way may be available.";
    box.style.display = "block";
  }

  function render(nav) {
    current = nav;
    if (nav.route_id !== routeId) buildRoute(nav);
    const [done, ahead] = splitAt(cum[cum.length - 1] * nav.progress);
    doneLine.setPath(done);
    aheadLine.setPath(ahead);
    moveRider(nav.position);
    drawZones(nav);
    renderTurn(nav);
    renderStats(nav);
    renderSpike(nav);
    if (nav.status === "arrived") {
      $("arrived").style.display = "block";
      $("arrived-text").textContent = nav.pickup_name + " → " + nav.drop_name + " · dose " + nav.dose_so_far.toFixed(0);
    }
  }

  async function poll() {
    if (busy) return;
    try {
      render(await api("/api/rider/orders/" + encodeURIComponent(CFG.orderId) + "/navigation"));
    } catch (e) {
      if (e.message !== "signed out") $("turn-text").textContent = "Can't load navigation: " + e.message;
    }
  }

  // ------------------------------------------------------------ reroute
  async function openReroute() {
    const btn = $("see-reroute");
    btn.disabled = true; btn.textContent = "Checking live routes…";
    try {
      preview = await api("/api/rider/orders/" + encodeURIComponent(CFG.orderId) + "/reroute");
      $("m-msg").textContent = preview.message;
      $("m-cur").innerHTML = preview.current_minutes.toFixed(0) + " min<br><span class=\"muted\">dose " + preview.current_dose.toFixed(0) + "</span>";
      if (preview.best) {
        $("m-new").innerHTML = preview.best.minutes.toFixed(0) + " min<br><span class=\"muted\">dose " + preview.best.dose.toFixed(0) +
          (preview.dose_saved_pct > 0 ? " · −" + preview.dose_saved_pct.toFixed(0) + "%" : "") + "</span>";
      }
      $("m-take").style.display = preview.best && preview.recommend_switch ? "" : "none";
      $("m-keep").textContent = preview.recommend_switch ? "Keep current" : "OK, keep my route";
      $("modal").style.display = "flex";
    } catch (e) {
      $("spike-body").textContent = "Couldn't check reroute: " + e.message;
    } finally {
      btn.disabled = false; btn.textContent = "See cleaner route";
    }
  }

  async function takeReroute() {
    if (!preview || !preview.best) return;
    busy = true;
    const btn = $("m-take");
    btn.disabled = true; btn.textContent = "Switching…";
    try {
      const nav = await api("/api/rider/orders/" + encodeURIComponent(CFG.orderId) + "/reroute", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ route_id: preview.best.route_id }),
      });
      $("modal").style.display = "none";
      busy = false;
      render(nav);
    } catch (e) {
      $("m-msg").textContent = "Couldn't switch: " + e.message;
      busy = false;
    } finally {
      btn.disabled = false; btn.textContent = "Take cleaner route";
    }
  }

  async function dismissSpike() {
    const open = (current && current.alerts) || [];
    open.forEach(function (a) { dismissed.add(a.id); });
    $("spike").style.display = "none";
    await Promise.all(open.map(function (a) {
      return api("/api/alerts/" + encodeURIComponent(a.id) + "/ack", { method: "POST" }).catch(function () {});
    }));
  }

  // ------------------------------------------------------------ boot
  window.AEVORA_init = function () {
    map = new google.maps.Map($("map"), {
      styles: STYLE, center: { lat: 28.56, lng: 77.22 }, zoom: 13,
      disableDefaultUI: true, zoomControl: true, gestureHandling: "greedy",
    });
    map.addListener("dragstart", function () { follow = false; });
    poll();
    setInterval(poll, POLL_MS);
  };

  document.addEventListener("DOMContentLoaded", function () {
    $("recenter").addEventListener("click", function () {
      follow = true;
      if (riderMarker) { map.panTo(riderMarker.getPosition()); map.setZoom(15); }
    });
    $("see-reroute").addEventListener("click", openReroute);
    $("dismiss-spike").addEventListener("click", dismissSpike);
    $("m-take").addEventListener("click", takeReroute);
    $("m-keep").addEventListener("click", function () { $("modal").style.display = "none"; dismissSpike(); });

    if (!CFG.mapsKey) { $("turn-text").textContent = "Google Maps key is not configured."; return; }
    const s = document.createElement("script");
    s.src = "https://maps.googleapis.com/maps/api/js?key=" + encodeURIComponent(CFG.mapsKey) +
      "&libraries=geometry&loading=async&callback=AEVORA_init";
    s.async = true;
    document.head.appendChild(s);
  });
})();
