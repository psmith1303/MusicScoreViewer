const SHELL_CACHE = "folio-v5";
const PDF_CACHE = "folio-pdfs-v1";
const MAX_CACHED_PDFS = 30;

const SHELL_URLS = [
  "/",
  "/app.css",
  "/app.js",
  "/modules/state.js",
  "/modules/utils.js",
  "/modules/dom.js",
  "/modules/api.js",
  "/modules/views.js",
  "/modules/theme.js",
  "/modules/library.js",
  "/modules/viewer.js",
  "/modules/annotations.js",
  "/modules/setlists.js",
  "/modules/dialog-handlers.js",
  "/modules/keyboard.js",
  "/modules/touch.js",
  "/modules/cache.js",
  "/manifest.json",
  "/favicon.ico",
  "/apple-touch-icon.png",
  "/icon-192.png",
  "/icon-512.png",
];

// ---------------------------------------------------------------------------
// IndexedDB helpers for LRU metadata
// ---------------------------------------------------------------------------

function openLruDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open("folio-lru", 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("entries")) {
        const store = db.createObjectStore("entries", { keyPath: "path" });
        store.createIndex("lastUsed", "lastUsed");
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function touchLruEntry(path, size) {
  const db = await openLruDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("entries", "readwrite");
    tx.objectStore("entries").put({ path, lastUsed: Date.now(), size: size || 0 });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function removeLruEntry(path) {
  const db = await openLruDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("entries", "readwrite");
    tx.objectStore("entries").delete(path);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getAllLruEntries() {
  const db = await openLruDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("entries", "readonly");
    const req = tx.objectStore("entries").index("lastUsed").getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function clearAllLruEntries() {
  const db = await openLruDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("entries", "readwrite");
    tx.objectStore("entries").clear();
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ---------------------------------------------------------------------------
// LRU eviction — remove oldest entries to stay at or below MAX_CACHED_PDFS
// ---------------------------------------------------------------------------

async function evictIfNeeded() {
  const entries = await getAllLruEntries(); // sorted by lastUsed ascending
  if (entries.length <= MAX_CACHED_PDFS) return;

  const cache = await caches.open(PDF_CACHE);
  const toEvict = entries.slice(0, entries.length - MAX_CACHED_PDFS);
  for (const entry of toEvict) {
    const cacheKey = "/api/pdf?path=" + encodeURIComponent(entry.path);
    await cache.delete(cacheKey);
    await removeLruEntry(entry.path);
  }
}

// ---------------------------------------------------------------------------
// URL normalization — strip cache-buster _t param from PDF URLs
// ---------------------------------------------------------------------------

function pdfCacheKey(url) {
  const path = new URL(url).searchParams.get("path");
  return "/api/pdf?path=" + encodeURIComponent(path);
}

function getPathFromPdfUrl(url) {
  return new URL(url).searchParams.get("path");
}

// ---------------------------------------------------------------------------
// Install / Activate
// ---------------------------------------------------------------------------

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((n) => n !== SHELL_CACHE && n !== PDF_CACHE)
          .map((n) => caches.delete(n))
      )
    )
  );
  self.clients.claim();
});

// ---------------------------------------------------------------------------
// Fetch handlers
// ---------------------------------------------------------------------------

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // PDF fetch: cache-first with LRU tracking
  if (url.pathname === "/api/pdf" && e.request.method === "GET") {
    e.respondWith(handlePdfFetch(e.request));
    return;
  }

  // Library/annotations GET: network-first with cache fallback
  if (
    e.request.method === "GET" &&
    (url.pathname === "/api/library" || url.pathname === "/api/annotations")
  ) {
    e.respondWith(handleApiGetFetch(e.request));
    return;
  }

  // Other API calls: pass through
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  // CDN resources (pdf.js): cache-first
  if (url.origin !== self.location.origin) {
    e.respondWith(
      caches.match(e.request).then((cached) => {
        if (cached) return cached;
        return fetch(e.request).then((resp) => {
          if (resp.ok) {
            const clone = resp.clone();
            caches.open(SHELL_CACHE).then((c) => c.put(e.request, clone));
          }
          return resp;
        });
      })
    );
    return;
  }

  // App shell: network-first with cache fallback
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        if (resp.ok) {
          const clone = resp.clone();
          caches.open(SHELL_CACHE).then((c) => c.put(e.request, clone));
        }
        return resp;
      })
      .catch(() => caches.match(e.request))
  );
});

async function handlePdfFetch(request) {
  const cacheKey = pdfCacheKey(request.url);
  const pdfPath = getPathFromPdfUrl(request.url);
  const cache = await caches.open(PDF_CACHE);

  // Check cache first
  const cached = await cache.match(cacheKey);
  if (cached) {
    // Update LRU timestamp in background
    if (pdfPath) touchLruEntry(pdfPath, 0).catch(() => {});
    return cached;
  }

  // Network fetch
  const resp = await fetch(request);
  if (resp.ok && pdfPath) {
    const clone = resp.clone();
    await cache.put(cacheKey, clone);
    const size = parseInt(resp.headers.get("content-length") || "0", 10);
    await touchLruEntry(pdfPath, size);
    evictIfNeeded().catch(() => {});
  }
  return resp;
}

async function handleApiGetFetch(request) {
  try {
    const resp = await fetch(request);
    if (resp.ok) {
      const clone = resp.clone();
      const cache = await caches.open(SHELL_CACHE);
      await cache.put(request, clone);
    }
    return resp;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ error: "Offline" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

// ---------------------------------------------------------------------------
// Message handler — page ↔ SW communication
// ---------------------------------------------------------------------------

self.addEventListener("message", (e) => {
  const { type, payload } = e.data;
  const port = e.ports[0];

  if (type === "cache-pdf") {
    handleCachePdf(payload.path, port);
  } else if (type === "evict-pdf") {
    handleEvictPdf(payload.path, port);
  } else if (type === "get-cache-status") {
    handleGetCacheStatus(port);
  } else if (type === "clear-pdf-cache") {
    handleClearPdfCache(port);
  } else if (type === "cache-library") {
    handleCacheLibrary(port);
  }
});

async function handleCachePdf(path, port) {
  try {
    const cache = await caches.open(PDF_CACHE);
    const cacheKey = "/api/pdf?path=" + encodeURIComponent(path);
    const url = cacheKey + "&_t=" + Date.now();

    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    await cache.put(cacheKey, resp.clone());
    const size = parseInt(resp.headers.get("content-length") || "0", 10);
    await touchLruEntry(path, size);
    await evictIfNeeded();

    port.postMessage({ ok: true });
  } catch (err) {
    port.postMessage({ ok: false, error: err.message });
  }
}

async function handleEvictPdf(path, port) {
  try {
    const cache = await caches.open(PDF_CACHE);
    const cacheKey = "/api/pdf?path=" + encodeURIComponent(path);
    await cache.delete(cacheKey);
    await removeLruEntry(path);
    port.postMessage({ ok: true });
  } catch (err) {
    port.postMessage({ ok: false, error: err.message });
  }
}

async function handleGetCacheStatus(port) {
  try {
    const entries = await getAllLruEntries();
    const paths = new Set(entries.map((e) => e.path));
    port.postMessage({ ok: true, cachedPaths: Array.from(paths) });
  } catch (err) {
    port.postMessage({ ok: false, error: err.message, cachedPaths: [] });
  }
}

async function handleClearPdfCache(port) {
  try {
    await caches.delete(PDF_CACHE);
    await clearAllLruEntries();
    port.postMessage({ ok: true });
  } catch (err) {
    port.postMessage({ ok: false, error: err.message });
  }
}

async function handleCacheLibrary(port) {
  try {
    const resp = await fetch("/api/library");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const cache = await caches.open(SHELL_CACHE);
    await cache.put("/api/library", resp);
    port.postMessage({ ok: true });
  } catch (err) {
    port.postMessage({ ok: false, error: err.message });
  }
}
