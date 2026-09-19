// Rider app service worker (T1.9/T1.10). Served at site root (not /static/sw.js)
// so its scope covers the whole origin, per the Push API requirement that a
// service worker can only control paths at or below its own location.
// Streamlit cannot host this itself (PRD) - that's why push lives here.

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (err) {
    payload = { title: "Exposure alert", body: event.data ? event.data.text() : "" };
  }

  const title = payload.title || "Exposure alert";
  const options = {
    body: payload.body || "",
    icon: payload.icon || "/static/icon.png",
    data: { url: payload.url || "/rider" },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/rider";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url === url && "focus" in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(url);
      }
    })
  );
});
