import { describe, expect, it, vi } from "vitest";
import { isChunkLoadError, reloadForStaleChunk } from "./chunkReload";

function makeWin() {
  const store = new Map<string, string>();
  const reload = vi.fn();
  const win = {
    location: { reload },
    sessionStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
    },
  };
  return { win, reload };
}

describe("isChunkLoadError", () => {
  it("matches stale/missing dynamic import failures", () => {
    expect(
      isChunkLoadError("Failed to fetch dynamically imported module: /assets/PlaybookPage-x.js"),
    ).toBe(true);
    expect(isChunkLoadError("Loading chunk 12 failed")).toBe(true);
    expect(isChunkLoadError(new Error("error loading dynamically imported module"))).toBe(true);
    expect(isChunkLoadError("Importing a module script failed")).toBe(true);
  });

  it("ignores unrelated errors and empty values", () => {
    expect(isChunkLoadError("TypeError: x is not a function")).toBe(false);
    expect(isChunkLoadError(undefined)).toBe(false);
    expect(isChunkLoadError(null)).toBe(false);
  });
});

describe("reloadForStaleChunk", () => {
  it("reloads once then suppresses a second reload inside the guard window", () => {
    const { win, reload } = makeWin();
    expect(reloadForStaleChunk(win, 1_000)).toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);

    // shortly after → suppressed (no reload loop)
    expect(reloadForStaleChunk(win, 5_000)).toBe(false);
    expect(reload).toHaveBeenCalledTimes(1);

    // after the guard window elapses → allowed again
    expect(reloadForStaleChunk(win, 20_000)).toBe(true);
    expect(reload).toHaveBeenCalledTimes(2);
  });

  it("still reloads when sessionStorage is unavailable", () => {
    const reload = vi.fn();
    const win = { location: { reload } };
    expect(reloadForStaleChunk(win, 1_000)).toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
