import { afterEach, describe, expect, it, vi } from "vitest";
import { installChunkErrorReload, isChunkLoadError, reloadForStaleChunk } from "./chunkReload";

describe("frontend-next chunk reload guard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("recognizes stale dynamic import and chunk load failures", () => {
    expect(isChunkLoadError(new Error("Failed to fetch dynamically imported module: /next/assets/PlaybookPage-old.js"))).toBe(true);
    expect(isChunkLoadError("ChunkLoadError: Loading chunk 42 failed")).toBe(true);
    expect(isChunkLoadError(new Error("ordinary render failure"))).toBe(false);
  });

  it("reloads at most once inside the cooldown window", () => {
    const win = fakeWindow();
    vi.spyOn(Date, "now").mockReturnValue(1_000);

    expect(reloadForStaleChunk(win)).toBe(true);
    expect(reloadForStaleChunk(win)).toBe(false);
    expect(win.location.reload).toHaveBeenCalledTimes(1);
  });

  it("listens for vite preload errors and prevents default handling", () => {
    const win = fakeWindow();
    vi.spyOn(Date, "now").mockReturnValue(2_000);
    installChunkErrorReload(win);
    const event = new Event("vite:preloadError", { cancelable: true });

    const dispatched = win.dispatchEvent(event);

    expect(dispatched).toBe(false);
    expect(event.defaultPrevented).toBe(true);
    expect(win.location.reload).toHaveBeenCalledTimes(1);
  });
});

function fakeWindow(): Window {
  const listeners = new EventTarget();
  const storage = new Map<string, string>();
  return {
    addEventListener: listeners.addEventListener.bind(listeners),
    dispatchEvent: listeners.dispatchEvent.bind(listeners),
    sessionStorage: {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
      clear: () => storage.clear(),
      key: (index: number) => Array.from(storage.keys())[index] ?? null,
      get length() {
        return storage.size;
      },
    },
    location: { reload: vi.fn() },
  } as unknown as Window;
}
