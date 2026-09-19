// Shared client logic for the rider app (T1.10): service worker registration,
// push subscribe, and an in-app toast fallback when permission is denied or
// push isn't supported (PRD: "same alerts appear as in-app toasts... already
// stored as Alert nodes").

function getRiderId() {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("rider_id");
  if (fromUrl) {
    localStorage.setItem("rider_id", fromUrl);
    return fromUrl;
  }
  return localStorage.getItem("rider_id") || "demo-rider";
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

async function subscribeToPush(statusEl) {
  const riderId = getRiderId();
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    statusEl.textContent = "Push not supported in this browser - using in-app alerts only.";
    return;
  }

  try {
    const registration = await navigator.serviceWorker.register("/sw.js");
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      statusEl.textContent = "Notifications denied - falling back to in-app alerts below.";
      return;
    }

    const keyResp = await fetch("/api/push/vapid-public-key");
    const { public_key } = await keyResp.json();

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key),
    });

    const json = subscription.toJSON();
    await fetch("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rider_id: riderId,
        subscription: { endpoint: json.endpoint, keys: json.keys },
      }),
    });

    statusEl.textContent = "Push notifications enabled for rider " + riderId + ".";
  } catch (err) {
    statusEl.textContent = "Could not enable push (" + err + ") - using in-app alerts only.";
  }
}

async function pollToasts(container) {
  const riderId = getRiderId();
  try {
    const resp = await fetch("/api/alerts?rider_id=" + encodeURIComponent(riderId) + "&status=new");
    const alerts = await resp.json();
    container.innerHTML = "";
    if (!alerts.length) {
      container.innerHTML = '<p class="muted">No active alerts.</p>';
      return;
    }
    for (const alert of alerts) {
      const div = document.createElement("div");
      div.className = "toast toast-" + alert.severity;
      div.innerHTML =
        "<strong>" + alert.severity.replace("_", " ") + "</strong> spike near zone " +
        alert.h3 + " (Simulated data replay) " +
        '<button data-id="' + alert.id + '">Acknowledge</button>';
      div.querySelector("button").addEventListener("click", async () => {
        await fetch("/api/alerts/" + alert.id + "/ack", { method: "POST" });
        pollToasts(container);
      });
      container.appendChild(div);
    }
  } catch (err) {
    container.innerHTML = '<p class="muted">Could not load alerts.</p>';
  }
}

function initRiderPage() {
  const statusEl = document.getElementById("push-status");
  const enableBtn = document.getElementById("enable-push");
  const toastContainer = document.getElementById("toasts");
  const riderIdEl = document.getElementById("rider-id");

  if (riderIdEl) riderIdEl.textContent = getRiderId();
  if (enableBtn) enableBtn.addEventListener("click", () => subscribeToPush(statusEl));
  if (toastContainer) {
    pollToasts(toastContainer);
    setInterval(() => pollToasts(toastContainer), 15000);
  }
}

document.addEventListener("DOMContentLoaded", initRiderPage);
