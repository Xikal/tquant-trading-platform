export function registerServiceWorker() {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return;
  }
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/tquant-sw.js").catch(() => {
      // Static cache is an optimization only; app behavior must not depend on it.
    });
  });
}
