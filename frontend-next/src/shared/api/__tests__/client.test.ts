import { describe, expect, it, vi } from "vitest";
import { ApiError, ApiTransportError } from "../errors";

describe("frontend-next operation client", () => {
  it("builds read operation URLs through generated operation wrappers", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const { apiClient } = await import("../client");
    await apiClient.lowBuyQuotes(["000001", "510300"]);
    await apiClient.lowBuyPriorityBoard(36, "baseline");
    await apiClient.strategyTrackingDetail("track-1");
    await apiClient.backtestRunEquity(24);
    await apiClient.sectorExclusions();

    expect(paths(fetchMock)).toEqual([
      "/api/screeners/low-buy/quotes?symbols=000001%2C510300",
      "/api/screeners/low-buy/priority-board?limit=30&refresh=cache&strategy_variant=baseline",
      "/api/strategy-tracking/items/track-1",
      "/api/backtests/24/equity",
      "/api/settings/sector-exclusions",
    ]);

    vi.unstubAllGlobals();
  });

  it("keeps analysis requests scoped to the analysis API", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ symbol: "000001" }));
    vi.stubGlobal("fetch", fetchMock);

    const { apiClient } = await import("../client");
    await apiClient.analyzeSymbol({ symbol: "000001", mode: "auto" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/analyze",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ symbol: "000001", mode: "auto" }),
      }),
    );

    vi.unstubAllGlobals();
  });

  it("retries read requests once for rate limited responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "slow down" }, 429, { "Retry-After": "0" }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const { requestJson } = await import("../client");
    await expect(requestJson("/api/read")).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    vi.unstubAllGlobals();
  });

  it("retries transient server errors for read requests", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "bad gateway" }, 502))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const { requestJson } = await import("../client");
    await expect(requestJson("/api/read")).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    vi.unstubAllGlobals();
  });

  it("does not retry write requests on rate limits", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "slow down" }, 429, { "Retry-After": "0" }));
    vi.stubGlobal("fetch", fetchMock);

    const { requestJson } = await import("../client");
    await expect(requestJson("/api/write", { method: "POST", body: "{}" })).rejects.toBeInstanceOf(ApiError);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it("parses non-json error responses without reading the body twice", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("service unavailable", { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    const { requestJson } = await import("../client");
    await expect(requestJson("/api/write", { method: "POST", body: "{}" })).rejects.toMatchObject({
      status: 503,
      detail: "service unavailable",
    } satisfies Partial<ApiError>);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it("refreshes an expired access token once for read requests and retries the original request", async () => {
    vi.stubGlobal("localStorage", createMemoryStorage([["tquant:auth:access_token", "old-access"], ["tquant:auth:refresh_token", "refresh-1"]]));
    vi.stubGlobal("sessionStorage", createMemoryStorage());
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ access_token: "new-access", refresh_token: "refresh-2", expires_in: 3600, token_type: "bearer", user: authUser() }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const { requestJson } = await import("../client");
    await expect(requestJson("/api/read")).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual(["/api/read", "/api/auth/refresh", "/api/read"]);
    expect(fetchMock.mock.calls[2]?.[1]).toEqual(expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer new-access" }) }));
    vi.unstubAllGlobals();
  });

  it("refreshes read requests through the httpOnly refresh cookie when no JS refresh token is exposed", async () => {
    vi.resetModules();
    const localStorage = createMemoryStorage([["tquant:auth:access_token", "old-access"], ["tquant:auth:refresh_session", "1"]]);
    vi.stubGlobal("localStorage", localStorage);
    vi.stubGlobal("sessionStorage", createMemoryStorage());
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ access_token: "cookie-access", refresh_token: "", expires_in: 3600, token_type: "bearer", user: authUser() }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const { requestJson } = await import("../client");
    await expect(requestJson("/api/read")).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual(["/api/read", "/api/auth/refresh", "/api/read"]);
    expect(fetchMock.mock.calls[1]?.[1]).toEqual(expect.objectContaining({
      body: JSON.stringify({ refresh_token: "" }),
      credentials: "include",
      method: "POST",
    }));
    expect(fetchMock.mock.calls[2]?.[1]).toEqual(expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer cookie-access" }) }));
    expect(localStorage.getItem("tquant:auth:refresh_session")).toBe("1");
    vi.unstubAllGlobals();
  });

  it("does not refresh and retry write requests on 401 responses", async () => {
    vi.stubGlobal("localStorage", createMemoryStorage([["tquant:auth:access_token", "old-access"], ["tquant:auth:refresh_token", "refresh-1"]]));
    vi.stubGlobal("sessionStorage", createMemoryStorage());
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "expired" }, 401));
    vi.stubGlobal("fetch", fetchMock);

    const { requestJson } = await import("../client");
    await expect(requestJson("/api/write", { method: "POST", body: "{}" })).rejects.toMatchObject({ status: 401 } satisfies Partial<ApiError>);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it("classifies request timeouts as transport errors", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { requestJson } = await import("../client");
    const request = requestJson("/api/slow", { timeoutMs: 10, retry: false });
    const assertion = expect(request).rejects.toMatchObject({ kind: "timeout" } satisfies Partial<ApiTransportError>);
    await vi.advanceTimersByTimeAsync(10);

    await assertion;
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("cancels retry-after waits through AbortSignal", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "slow down" }, 429, { "Retry-After": "20" }));
    vi.stubGlobal("fetch", fetchMock);

    const { requestJson } = await import("../client");
    const request = requestJson("/api/read", { signal: controller.signal });
    const assertion = expect(request).rejects.toMatchObject({ kind: "aborted" } satisfies Partial<ApiTransportError>);
    await vi.advanceTimersByTimeAsync(1);
    controller.abort();
    await assertion;

    expect(fetchMock).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("propagates AbortSignal through requestOperation fetches", async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { requestOperation } = await import("../client");
    const request = requestOperation("monitorWorkspace", {}, { signal: controller.signal, retry: false });
    controller.abort();

    await expect(request).rejects.toMatchObject({ kind: "aborted" } satisfies Partial<ApiTransportError>);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/bff/v1/workspace/monitor",
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
    vi.unstubAllGlobals();
  });

  it("passes request init through read wrappers used by TanStack Query", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    const signal = new AbortController().signal;

    const { apiClient } = await import("../client");
    await apiClient.monitorWorkspace("action", 18, { signal });
    await apiClient.backtestRuns(undefined, { signal });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.map((call) => call.at(1)).every((init) => (init as RequestInit | undefined)?.signal instanceof AbortSignal)).toBe(true);
    vi.unstubAllGlobals();
  });
});

function jsonResponse(payload: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function paths(fetchMock: ReturnType<typeof vi.fn>): string[] {
  return fetchMock.mock.calls.map((call) => String(call[0]));
}

function authUser() {
  return {
    can_paper_trade: true,
    created_at: "2026-06-06T00:00:00Z",
    display_name: "tester",
    id: 1,
    mfa_totp_enabled: false,
    roles: ["admin"],
    username: "tester",
  };
}

function createMemoryStorage(entries: [string, string][] = []): Storage {
  const data = new Map<string, string>(entries);
  return {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => Array.from(data.keys())[index] ?? null,
    removeItem: (key) => data.delete(key),
    setItem: (key, value) => data.set(key, value),
  };
}
