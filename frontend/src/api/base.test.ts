import { afterEach, describe, expect, it, vi } from "vitest";
import { PUBLIC_API_PATHS, isPublicApiPath } from "./publicApiPaths";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function memoryStorage(initial: Record<string, string> = {}): Storage {
  const store = new Map(Object.entries(initial));
  return {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => store.get(key) ?? null,
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
  };
}

function installBrowserAuthStorage(mode: "local" | "session") {
  vi.stubGlobal("window", {
    localStorage: memoryStorage({ "tquant:auth:persistence_mode": mode }),
    sessionStorage: memoryStorage(),
  });
}

async function loadBaseApi() {
  vi.resetModules();
  return import("./base");
}

describe("api auth refresh", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("refreshes before protected POST requests when only the httpOnly refresh cookie can restore auth", async () => {
    installBrowserAuthStorage("local");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: "fresh-access" }))
      .mockResolvedValueOnce(jsonResponse({ stream_token: "stream-token", expires_in: 3600 }));
    vi.stubGlobal("fetch", fetchMock);
    const { request } = await loadBaseApi();

    await expect(request("/intraday/subscribe", { method: "POST" })).resolves.toEqual({
      stream_token: "stream-token",
      expires_in: 3600,
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/auth/refresh");
    expect(String(fetchMock.mock.calls[1][0])).toBe("/api/intraday/subscribe");
    expect(fetchMock.mock.calls[1][1]?.headers).toMatchObject({
      Authorization: "Bearer fresh-access",
    });
  });

  it("retries a protected request once after a stale access token gets a 401", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "登录已失效，请重新登录" }, 401))
      .mockResolvedValueOnce(jsonResponse({ access_token: "fresh-access" }))
      .mockResolvedValueOnce(jsonResponse({ stream_token: "stream-token", expires_in: 3600 }));
    vi.stubGlobal("fetch", fetchMock);
    const { request, setAuthTokens } = await loadBaseApi();
    setAuthTokens("stale-access", "session");

    await expect(request("/intraday/subscribe", { method: "POST" })).resolves.toEqual({
      stream_token: "stream-token",
      expires_in: 3600,
    });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/intraday/subscribe");
    expect(fetchMock.mock.calls[0][1]?.headers).toMatchObject({
      Authorization: "Bearer stale-access",
    });
    expect(String(fetchMock.mock.calls[1][0])).toBe("/api/auth/refresh");
    expect(String(fetchMock.mock.calls[2][0])).toBe("/api/intraday/subscribe");
    expect(fetchMock.mock.calls[2][1]?.headers).toMatchObject({
      Authorization: "Bearer fresh-access",
    });
  });

  it("does not pre-refresh public bootstrap requests", async () => {
    installBrowserAuthStorage("local");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ default_refresh_seconds: 20 }));
    vi.stubGlobal("fetch", fetchMock);
    const { request } = await loadBaseApi();

    await expect(request("/app/bootstrap")).resolves.toEqual({ default_refresh_seconds: 20 });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/app/bootstrap");
  });

  it("uses the centralized public API allowlist for bootstrap and update endpoints", () => {
    expect(PUBLIC_API_PATHS).toContain("/app/bootstrap");
    expect(isPublicApiPath("/app/bootstrap")).toBe(true);
    expect(isPublicApiPath("/app/update/android/stable")).toBe(true);
    expect(isPublicApiPath("/intraday/subscribe")).toBe(false);
    expect(isPublicApiPath("/auth/refresh")).toBe(true);
  });

  it("shares one refresh request between explicit session restore and protected SSE subscribe", async () => {
    installBrowserAuthStorage("local");
    const user = {
      id: 1,
      username: "tester",
      display_name: "tester",
      can_paper_trade: true,
      roles: [],
      created_at: "2026-06-02T10:00:00+08:00",
    };
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      const path = String(url);
      if (path === "/api/auth/refresh") {
        return Promise.resolve(jsonResponse({ access_token: "fresh-access", token_type: "bearer", expires_in: 1800, user }));
      }
      if (path === "/api/intraday/subscribe") {
        return Promise.resolve(jsonResponse({ stream_token: "stream-token", expires_in: 3600 }));
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });
    vi.stubGlobal("fetch", fetchMock);
    const { refreshAuthSession, request } = await loadBaseApi();

    await expect(Promise.all([
      refreshAuthSession(),
      request("/intraday/subscribe", { method: "POST" }),
    ])).resolves.toEqual([
      { access_token: "fresh-access", token_type: "bearer", expires_in: 1800, user },
      { stream_token: "stream-token", expires_in: 3600 },
    ]);

    const refreshCalls = fetchMock.mock.calls.filter(([url]) => String(url) === "/api/auth/refresh");
    expect(refreshCalls).toHaveLength(1);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === "/api/intraday/subscribe")).toBe(true);
  });

  it("keeps refresh-cookie restore enabled after a transient refresh outage", async () => {
    installBrowserAuthStorage("local");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "temporary unavailable" }, 503))
      .mockResolvedValueOnce(jsonResponse({ access_token: "fresh-access" }))
      .mockResolvedValueOnce(jsonResponse({ stream_token: "stream-token", expires_in: 3600 }));
    vi.stubGlobal("fetch", fetchMock);
    const { request, shouldAttemptAuthRefresh } = await loadBaseApi();

    await expect(request("/intraday/subscribe", { method: "POST" })).rejects.toMatchObject({ status: 401 });
    expect(shouldAttemptAuthRefresh()).toBe(true);

    await expect(request("/intraday/subscribe", { method: "POST" })).resolves.toEqual({
      stream_token: "stream-token",
      expires_in: 3600,
    });
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === "/api/auth/refresh")).toHaveLength(2);
  });
});
