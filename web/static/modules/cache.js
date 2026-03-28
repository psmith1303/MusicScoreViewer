// ---------------------------------------------------------------------------
// Offline cache management — MessageChannel communication with service worker
// ---------------------------------------------------------------------------

import { getState } from "./state.js";
import { libraryBody, libraryStatus } from "./dom.js";

// ---------------------------------------------------------------------------
// SW communication
// ---------------------------------------------------------------------------

function swMessage(type, payload = {}) {
  return new Promise((resolve, reject) => {
    const sw = navigator.serviceWorker?.controller;
    if (!sw) {
      reject(new Error("No active service worker"));
      return;
    }
    const ch = new MessageChannel();
    ch.port1.onmessage = (e) => resolve(e.data);
    sw.postMessage({ type, payload }, [ch.port2]);
    setTimeout(() => reject(new Error("SW message timeout")), 30000);
  });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function cachePdf(path) {
  return swMessage("cache-pdf", { path });
}

export async function evictPdf(path) {
  return swMessage("evict-pdf", { path });
}

export async function getCacheStatus() {
  try {
    const result = await swMessage("get-cache-status");
    return new Set(result.cachedPaths || []);
  } catch {
    return new Set();
  }
}

export async function clearPdfCache() {
  return swMessage("clear-pdf-cache");
}

export async function cacheLibrary() {
  return swMessage("cache-library");
}

// ---------------------------------------------------------------------------
// UI — per-row cache buttons in library table
// ---------------------------------------------------------------------------

let _cachedPaths = new Set();

export async function refreshCacheStatus() {
  _cachedPaths = await getCacheStatus();
  updateCacheButtons();
}

function updateCacheButtons() {
  const rows = libraryBody.querySelectorAll("tr");
  for (const row of rows) {
    const filepath = row.dataset.filepath;
    if (!filepath) continue;
    const btn = row.querySelector(".cache-btn");
    if (!btn) continue;
    const cached = _cachedPaths.has(filepath);
    btn.textContent = cached ? "\u2713" : "\u2B07";
    btn.title = cached ? "Remove from offline cache" : "Download for offline use";
    btn.classList.toggle("cached", cached);
  }
}

export function isCached(filepath) {
  return _cachedPaths.has(filepath);
}

export async function toggleCache(filepath, btn) {
  const cached = _cachedPaths.has(filepath);
  btn.disabled = true;
  btn.textContent = "\u2026";

  try {
    if (cached) {
      await evictPdf(filepath);
      _cachedPaths.delete(filepath);
    } else {
      const result = await cachePdf(filepath);
      if (result.ok) {
        _cachedPaths.add(filepath);
      } else {
        throw new Error(result.error || "Cache failed");
      }
    }
  } catch (err) {
    console.error("Cache toggle failed:", err);
  } finally {
    btn.disabled = false;
    const nowCached = _cachedPaths.has(filepath);
    btn.textContent = nowCached ? "\u2713" : "\u2B07";
    btn.title = nowCached ? "Remove from offline cache" : "Download for offline use";
    btn.classList.toggle("cached", nowCached);
  }
}

// ---------------------------------------------------------------------------
// Offline dialog handlers
// ---------------------------------------------------------------------------

export function initCacheUI() {
  const btnOffline = document.getElementById("btn-offline");
  const offlineDialog = document.getElementById("offline-dialog");
  const offlineClose = document.getElementById("offline-close");
  const btnRefreshLibrary = document.getElementById("btn-refresh-library");
  const btnClearPdfs = document.getElementById("btn-clear-pdfs");
  const offlineStatus = document.getElementById("offline-status");

  if (!btnOffline || !offlineDialog) return;

  btnOffline.addEventListener("click", async () => {
    offlineStatus.textContent = "Checking cache\u2026";
    offlineDialog.showModal();
    const paths = await getCacheStatus();
    offlineStatus.textContent = `${paths.size} PDF${paths.size !== 1 ? "s" : ""} cached for offline use (max ${30}).`;
  });

  offlineClose.addEventListener("click", () => offlineDialog.close());

  btnRefreshLibrary.addEventListener("click", async () => {
    btnRefreshLibrary.disabled = true;
    btnRefreshLibrary.textContent = "Refreshing\u2026";
    try {
      const result = await cacheLibrary();
      offlineStatus.textContent = result.ok
        ? "Library cached for offline use."
        : `Failed: ${result.error}`;
    } catch (err) {
      offlineStatus.textContent = `Failed: ${err.message}`;
    } finally {
      btnRefreshLibrary.disabled = false;
      btnRefreshLibrary.textContent = "Refresh Library Cache";
    }
  });

  btnClearPdfs.addEventListener("click", async () => {
    btnClearPdfs.disabled = true;
    btnClearPdfs.textContent = "Clearing\u2026";
    try {
      await clearPdfCache();
      _cachedPaths.clear();
      updateCacheButtons();
      offlineStatus.textContent = "PDF cache cleared.";
    } catch (err) {
      offlineStatus.textContent = `Failed: ${err.message}`;
    } finally {
      btnClearPdfs.disabled = false;
      btnClearPdfs.textContent = "Clear PDF Cache";
    }
  });
}
