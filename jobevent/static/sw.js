// No persistent cache for accounts, profiles, requests, or recommendations.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate" || event.request.method !== "GET") return;
  event.respondWith(fetch(event.request).catch(() => new Response(
    '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>오프라인 · Jobevent</title><h1>인터넷에 연결되지 않았습니다.</h1><p>알림 예약은 서버에서 계속 실행됩니다. 인터넷에 연결한 뒤 다시 여세요.</p><a href="/app">다시 연결</a></html>',
    {headers: {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}}
  )));
});
