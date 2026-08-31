/* Raility service worker
 *
 * 전략 (기술 진단서 05 반영):
 *   - 앱 셸(HTML·JS·CSS·manifest)은 network-first — 배포가 기존 방문자에게
 *     즉시 도달한다. 오프라인일 때만 캐시로 내려간다.
 *   - 아이콘 등 정적 자원은 cache-first.
 *   - 외부 요청(지도 타일)은 관여하지 않는다 — 캐시가 무한정 부풀기 때문.
 */
var CACHE = 'raility-v3';
var ASSETS = [
  './', './index.html',
  './assets/app.css', './assets/app.js', './assets/graph.js', './assets/data.js',
  './assets/icon-192.png', './assets/icon-512.png',
  './manifest.webmanifest'
];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(ASSETS); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function putCopy(req, res) {
  var copy = res.clone();
  caches.open(CACHE).then(function (c) { c.put(req, copy); }).catch(function () {});
  return res;
}

self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  var url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;

  var shell = /\.(?:js|css|webmanifest)$/.test(url.pathname) ||
              /\/$|index\.html$/.test(url.pathname);
  if (shell) {
    e.respondWith(
      fetch(e.request).then(function (res) { return putCopy(e.request, res); })
        .catch(function () {
          return caches.match(e.request).then(function (hit) {
            return hit || caches.match('./index.html');
          });
        })
    );
  } else {
    e.respondWith(
      caches.match(e.request).then(function (hit) {
        return hit || fetch(e.request).then(function (res) { return putCopy(e.request, res); });
      })
    );
  }
});
