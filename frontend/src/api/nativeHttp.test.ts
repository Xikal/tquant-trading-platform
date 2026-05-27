import { describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();

vi.mock("@capacitor/core", () => ({
  Capacitor: {
    isNativePlatform: () => true,
  },
  CapacitorHttp: {
    request: requestMock,
  },
}));

describe("nativeRequest", () => {
  it("preserves http status on auth failures", async () => {
    requestMock.mockResolvedValueOnce({
      status: 401,
      headers: { "content-type": "application/json" },
      data: JSON.stringify({ detail: "登录已失效" }),
    });
    const { nativeRequest } = await import("./nativeHttp");

    await expect(nativeRequest("/api/protected")).rejects.toMatchObject({
      message: "登录已失效",
      status: 401,
    });
  });

  it("preserves http status for plain text errors", async () => {
    requestMock.mockResolvedValueOnce({
      status: 503,
      headers: { "content-type": "text/plain" },
      data: "service unavailable",
    });
    const { nativeRequest } = await import("./nativeHttp");

    await expect(nativeRequest("/api/market/pulse")).rejects.toMatchObject({
      message: "service unavailable",
      status: 503,
    });
  });
});
