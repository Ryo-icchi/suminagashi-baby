// すみながし Service Worker — オフラインでも遊べるように全アセットをキャッシュ
// HTML はネットワーク優先（更新が1回の起動で届く）・静的アセットはキャッシュ優先
const CACHE = "suminagashi-v15";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icon-180.png",
  "./icon-192.png",
  "./icon-512.png"
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  const isHTML = e.request.mode === "navigate" ||
                 url.pathname.endsWith("/") || url.pathname.endsWith("/index.html");

  if (isHTML) {
    // ネットワーク優先: オンラインなら常に最新。取れたらキャッシュ更新。オフライン時のみキャッシュ
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return res;
        })
        .catch(() =>
          caches.match(e.request).then((hit) => hit || caches.match("./index.html"))
        )
    );
  } else {
    // 静的アセット: キャッシュ優先・なければネットワーク（取得できたらキャッシュに追加）
    e.respondWith(
      caches.match(e.request).then(
        (hit) =>
          hit ||
          fetch(e.request).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(e.request, copy));
            return res;
          })
      )
    );
  }
});
