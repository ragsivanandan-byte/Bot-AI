"use strict";
// Service worker de Leçons Audio : garde l'application disponible hors ligne.
// Stratégie « cache d'abord, mise à jour en arrière-plan » : l'app s'ouvre
// instantanément même sans réseau (métro, avion) et se met à jour au lancement
// suivant. Les fichiers audio, eux, sont dans IndexedDB (pas dans ce cache).
// Changer le numéro à chaque mise en ligne : tous les fichiers sont alors
// re-téléchargés ensemble (jamais de mélange ancienne/nouvelle version).
const CACHE = "lecons-audio-v2";
const ASSETS = [
  "./", "index.html", "audio.css", "app.js", "mp4audio.js", "detect.js",
  "manifest.webmanifest", "icon-180.png", "icon-192.png", "icon-512.png",
];

self.addEventListener("install", (event) => {
  // « reload » : ignore le cache HTTP du navigateur (sinon fichiers périmés possibles).
  const fresh = ASSETS.map((u) => new Request(u, { cache: "reload" }));
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(fresh)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("lecons-audio-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(req, { ignoreSearch: true }) ||
        (req.mode === "navigate" ? await cache.match("./") : undefined);
      const network = fetch(req)
        .then((res) => {
          // Pas de réponse redirigée en cache : Safari refuse de la servir à une navigation.
          if (res.ok && res.type === "basic" && !res.redirected) cache.put(req, res.clone());
          return res;
        })
        .catch(() => undefined);
      if (cached) { event.waitUntil(network); return cached; }
      return (await network) || new Response("Hors ligne", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } });
    }),
  );
});
