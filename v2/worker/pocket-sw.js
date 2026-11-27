"use strict";
// Installable shell only. Documents and API answers are never cached: every request goes to the worker.
const SHELL = "pocket-shell-v1";
const FILES = ["/v2/pocket", "/v2/pocket.css", "/v2/pocket.js", "/v2/pocket-icon.svg", "/v2/pocket.webmanifest"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(SHELL).then(cache => cache.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => key !== SHELL).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || !FILES.includes(url.pathname)) return;
  // Network first, so an updated worker always wins; the cache only covers a restart gap.
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok) {
      const copy = response.clone();
      caches.open(SHELL).then(cache => cache.put(event.request, copy));
    }
    return response;
  }).catch(() => caches.match(event.request)));
});
