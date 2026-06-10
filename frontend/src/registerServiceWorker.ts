import { reloadForStaleChunk } from "./app/chunkReload";

export function registerServiceWorker() {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return;
  }
  // When a freshly deployed service worker takes control of an already-open tab,
  // realign the page with the new asset generation once (guards against loops).
  // Skip the first-install transition (no prior controller) to avoid a needless reload.
  let hadController = Boolean(navigator.serviceWorker.controller);
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (hadController) {
      reloadForStaleChunk(window);
    }
    hadController = true;
  });
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/tquant-sw.js").catch(() => {
      // Static cache is an optimization only; app behavior must not depend on it.
    });
  });
}
