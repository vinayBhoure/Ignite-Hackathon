// Rider home + settings: deliveries, alert feed, push subscription.
// The session cookie identifies the rider; nothing here sends a rider id.
(function () {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function istTime(iso) {
    return new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });
  }

  function istStamp(iso) {
    return new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });
  }

  async function api(path, opts) {
    const resp = await fetch(path, Object.assign({ credentials: "same-origin" }, opts || {}));
    if (resp.status === 401) {
      window.location.assign("/?role=rider&reason=expired");
      throw new Error("signed out");
    }
    if (!resp.ok) throw new Error(resp.status);
    return resp.json();
  }

  // ---------------------------------------------------------------- push
  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const raw = atob((base64String + padding).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(raw, function (c) { return c.charCodeAt(0); });
  }

  async function enablePush(statusEl) {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      statusEl.textContent = "This browser can't receive push - alerts will still show in the app.";
      return;
    }
    try {
      const registration = await navigator.serviceWorker.register("/sw.js");
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        statusEl.textContent = "Notifications are off - alerts will still show in the app.";
        return;
      }
      const { public_key } = await api("/api/push/vapid-public-key");
      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key),
      });
      const json = sub.toJSON();
      await api("/api/push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rider_id: "self", subscription: { endpoint: json.endpoint, keys: json.keys } }),
      });
      statusEl.textContent = "Push is on. You'll be warned about bad air ahead even with this page closed.";
    } catch (err) {
      statusEl.textContent = "Couldn't turn on push (" + err.message + ") - alerts still show in the app.";
    }
  }

  // ---------------------------------------------------------------- home
  function orderCard(o) {
    const live = o.status !== "delivered";
    const alert = o.new_alerts ? ' <span class="chip sim">' + o.new_alerts + " air alert</span>" : "";
    return (
      '<div class="card' + (live ? " active" : "") + '">' +
      '<div class="route">' + esc(o.pickup_name) + " &rarr; " + esc(o.drop_name) + alert + "</div>" +
      '<div class="meta"><span>ETA <b>' + istTime(o.eta) + "</b></span>" +
      "<span><b>" + o.duration_min.toFixed(0) + "</b> min</span>" +
      "<span>dose <b>" + o.dose.toFixed(0) + "</b></span>" +
      '<span><span class="chip ' + (o.coverage >= 0.8 ? "high" : "low") + '">' + Math.round(o.coverage * 100) + "% coverage</span></span></div>" +
      '<div class="bar"><i style="width:' + Math.round(o.progress * 100) + '%"></i></div>' +
      (live
        ? '<a class="btn clean block" style="margin-top:12px" href="/rider/order/' + encodeURIComponent(o.order_id) + '">Navigate</a>'
        : '<p class="muted" style="margin:8px 0 0">Delivered · <span class="mono">' + esc(o.order_id) + "</span></p>") +
      "</div>"
    );
  }

  // Order ids dispatched to this rider from the console; alerts for orders
  // seeded elsewhere (not shown as deliveries here) are left out of the feed.
  let myOrders = null;

  async function refreshOrders(el) {
    try {
      const orders = await api("/api/rider/orders");
      myOrders = new Set(orders.map(function (o) { return o.order_id; }));
      if (!orders.length) {
        el.innerHTML = '<div class="empty"><b>No deliveries yet</b>Dispatch will assign your next order here.</div>';
        return;
      }
      orders.sort(function (a, b) { return (a.status === "delivered") - (b.status === "delivered"); });
      el.innerHTML = orders.map(orderCard).join("");
    } catch (e) {
      if (e.message !== "signed out") el.innerHTML = '<p class="muted">Couldn\'t load deliveries.</p>';
    }
  }

  async function refreshAlerts(el) {
    try {
      const alerts = (await api("/api/alerts?status=new")).filter(function (a) {
        return !myOrders || myOrders.has(a.order_id);
      });
      if (!alerts.length) {
        el.innerHTML = '<p class="muted">No air alerts right now.</p>';
        return;
      }
      el.innerHTML = alerts.map(function (a) {
        return (
          '<div class="alert"><div><b>' + esc(a.severity.replace("_", " ")) + "</b> air ahead " +
          (a.simulated ? '<span class="chip sim">Simulated</span>' : '<span class="chip low">Sensor</span>') +
          '<div class="muted">' + istStamp(a.ts) + " IST replay · order " + esc(a.order_id) + "</div></div>" +
          '<div style="display:flex;gap:6px"><a class="btn clean" style="font-size:12px;padding:6px 10px" href="/rider/order/' +
          encodeURIComponent(a.order_id) + '">Open</a>' +
          '<button class="btn ghost" data-ack="' + esc(a.id) + '">Dismiss</button></div></div>'
        );
      }).join("");
      el.querySelectorAll("[data-ack]").forEach(function (btn) {
        btn.addEventListener("click", async function () {
          btn.disabled = true;
          await api("/api/alerts/" + encodeURIComponent(btn.getAttribute("data-ack")) + "/ack", { method: "POST" });
          refreshAlerts(el);
        });
      });
    } catch (e) {
      if (e.message !== "signed out") el.innerHTML = '<p class="muted">Couldn\'t load alerts.</p>';
    }
  }

  async function refreshClock(el) {
    try {
      const c = await api("/api/clock");
      el.textContent = istStamp(c.now_ts) + " IST" + (c.running ? " · " + c.speed + "×" : " · paused");
    } catch (e) { /* non-critical */ }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const pushBtn = document.getElementById("enable-push");
    const pushStatus = document.getElementById("push-status");
    if (pushBtn) pushBtn.addEventListener("click", function () { enablePush(pushStatus); });

    const orders = document.getElementById("orders");
    const alerts = document.getElementById("alerts");
    const clock = document.getElementById("clock");
    async function tick() {
      if (orders) await refreshOrders(orders);
      if (alerts) refreshAlerts(alerts);
      if (clock) refreshClock(clock);
    }
    tick();
    if (orders || alerts) setInterval(tick, 5000);
  });
})();
