// Recovery for "white screen on route switch after a deploy":
// when a lazily-imported route chunk fails to load (stale/missing hash after a
// new build), force a one-time reload to fetch the fresh index + chunks.
// Guarded against reload loops so a genuinely broken server does not thrash.

const RELOAD_FLAG_KEY = "tq:chunk-reload-at";
const RELOAD_GUARD_MS = 10_000;

const CHUNK_ERROR_PATTERN =
  /Loading chunk|dynamically imported module|ChunkLoadError|Importing a module script failed|error loading dynamically imported module|Failed to fetch dynamically imported module/i;

type ReloadableWindow = {
  location: { reload: () => void };
  sessionStorage?: Pick<Storage, "getItem" | "setItem">;
};

export function isChunkLoadError(message: unknown): boolean {
  if (!message) return false;
  const text =
    typeof message === "string"
      ? message
      : String((message as { message?: unknown })?.message ?? message);
  return CHUNK_ERROR_PATTERN.test(text);
}

/**
 * Reload once to recover from a stale chunk. Returns true if a reload was
 * triggered, false if suppressed by the loop guard.
 */
export function reloadForStaleChunk(win: ReloadableWindow, now: number = Date.now()): boolean {
  try {
    const last = Number(win.sessionStorage?.getItem(RELOAD_FLAG_KEY) ?? "0");
    if (last && now - last < RELOAD_GUARD_MS) {
      return false;
    }
    win.sessionStorage?.setItem(RELOAD_FLAG_KEY, String(now));
  } catch {
    // sessionStorage unavailable (private mode / blocked) — still reload once.
  }
  win.location.reload();
  return true;
}

/**
 * Install global listeners that recover from stale/missing route chunks.
 * Covers Vite's `vite:preloadError` (modulepreload failure) plus generic
 * dynamic-import failures surfaced as window errors / unhandled rejections.
 */
export function installChunkErrorReload(win: Window = window): void {
  win.addEventListener(
    "vite:preloadError" as keyof WindowEventMap,
    ((event: Event) => {
      // Prevent Vite's default rethrow (which blanks the app), then reload.
      event.preventDefault?.();
      reloadForStaleChunk(win);
    }) as EventListener,
  );

  win.addEventListener("error", (event: ErrorEvent) => {
    if (isChunkLoadError(event?.message)) {
      reloadForStaleChunk(win);
    }
  });

  win.addEventListener("unhandledrejection", (event: PromiseRejectionEvent) => {
    if (isChunkLoadError(event?.reason)) {
      reloadForStaleChunk(win);
    }
  });
}
