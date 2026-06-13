import { describe, expect, it } from "vitest";
import {
  RUNTIME_API_BASE_URL_STORAGE_KEY,
  clearRuntimeApiBaseUrl,
  getRuntimeApiBaseUrl,
  getEffectiveApiBaseUrl,
  normalizeApiBaseUrl,
  resolveApiUrl,
  setRuntimeApiBaseUrl,
} from "./runtimeBaseUrl";

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key: string) => values.get(key) ?? null,
    key: (index: number) => Array.from(values.keys())[index] ?? null,
    removeItem: (key: string) => {
      values.delete(key);
    },
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
  };
}

describe("runtimeBaseUrl", () => {
  it("normalizes http base urls and removes trailing slashes", () => {
    expect(normalizeApiBaseUrl(" http://127.0.0.1:8000/// ")).toBe("http://127.0.0.1:8000");
    expect(normalizeApiBaseUrl("https://example.test/api/")).toBe("https://example.test/api");
  });

  it("rejects non-http runtime base urls", () => {
    expect(normalizeApiBaseUrl("file:///tmp/app")).toBe("");
    expect(normalizeApiBaseUrl("javascript:alert(1)")).toBe("");
  });

  it("persists and clears runtime api base url", () => {
    const storage = memoryStorage();

    expect(setRuntimeApiBaseUrl(" http://localhost:8000/ ", storage)).toBe("http://localhost:8000");
    expect(storage.getItem(RUNTIME_API_BASE_URL_STORAGE_KEY)).toBe("http://localhost:8000");
    expect(getRuntimeApiBaseUrl(storage)).toBe("http://localhost:8000");

    clearRuntimeApiBaseUrl(storage);
    expect(getRuntimeApiBaseUrl(storage)).toBe("");
  });

  it("uses runtime base before build base when resolving api urls", () => {
    const storage = memoryStorage();
    setRuntimeApiBaseUrl("http://127.0.0.1:9000", storage);

    expect(resolveApiUrl("/api/local/status", { buildBase: "https://prod.example", storage })).toBe(
      "http://127.0.0.1:9000/api/local/status",
    );
  });

  it("keeps relative urls when no base url is configured", () => {
    expect(resolveApiUrl("/api/local/status", { buildBase: "", storage: memoryStorage() })).toBe("/api/local/status");
  });

  it("uses desktop build base when no runtime base url is configured", () => {
    expect(getEffectiveApiBaseUrl({ buildBase: "http://127.0.0.1:8000", storage: memoryStorage() })).toBe("http://127.0.0.1:8000");
    expect(resolveApiUrl("/api/local/status", { buildBase: "http://127.0.0.1:8000", storage: memoryStorage() })).toBe(
      "http://127.0.0.1:8000/api/local/status",
    );
  });
});
