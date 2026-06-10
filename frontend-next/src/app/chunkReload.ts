const RELOAD_MARK_KEY = "tquant:frontend-next:chunk-reload-at";
const RELOAD_COOLDOWN_MS = 10_000;

export function installChunkErrorReload(win: Window = window): void {
  win.addEventListener("vite:preloadError", (event) => {
    event.preventDefault();
    reloadForStaleChunk(win);
  });
  win.addEventListener("error", (event) => {
    if (isChunkLoadError(event.error ?? event.message)) reloadForStaleChunk(win);
  });
  win.addEventListener("unhandledrejection", (event) => {
    if (isChunkLoadError(event.reason)) reloadForStaleChunk(win);
  });
}

export function reloadForStaleChunk(win: Window = window): boolean {
  const now = Date.now();
  const previousRaw = win.sessionStorage.getItem(RELOAD_MARK_KEY);
  const previous = Number(previousRaw ?? "0");
  if (previousRaw && Number.isFinite(previous) && now - previous < RELOAD_COOLDOWN_MS) return false;
  win.sessionStorage.setItem(RELOAD_MARK_KEY, String(now));
  win.location.reload();
  return true;
}

export function isChunkLoadError(value: unknown): boolean {
  const text = chunkErrorText(value);
  if (!text) return false;
  return [
    "failed to fetch dynamically imported module",
    "error loading dynamically imported module",
    "importing a module script failed",
    "chunkloaderror",
    "loading chunk",
    "vite:preloaderror",
    "dynamically imported module",
  ].some((pattern) => text.includes(pattern));
}

function chunkErrorText(value: unknown): string {
  if (value instanceof Error) return `${value.name} ${value.message}`.toLowerCase();
  if (typeof value === "string") return value.toLowerCase();
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return [record.name, record.message, record.type, record.reason].filter(Boolean).join(" ").toLowerCase();
  }
  return "";
}
