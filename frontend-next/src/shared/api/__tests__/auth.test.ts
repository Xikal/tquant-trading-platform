import { afterEach, describe, expect, it, vi } from "vitest";

describe("frontend-next auth adapter", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  it("stores access and refresh tokens across the selected storage", async () => {
    const localStorage = createMemoryStorage();
    const sessionStorage = createMemoryStorage();
    vi.stubGlobal("localStorage", localStorage);
    vi.stubGlobal("sessionStorage", sessionStorage);

    const { applyAuthTokenResponse, buildAuthHeaders, getAuthRefreshToken, setAdminApiToken } = await import("../auth");

    applyAuthTokenResponse(
      {
        access_token: "access-1",
        refresh_token: "refresh-1",
        expires_in: 3600,
        token_type: "bearer",
        user: {
          can_paper_trade: true,
          created_at: "2026-06-06T00:00:00Z",
          display_name: "tester",
          id: 1,
          mfa_totp_enabled: false,
          roles: ["admin"],
          username: "tester",
        },
      },
      false,
    );
    setAdminApiToken("admin-1");

    expect(getAuthRefreshToken()).toBe("refresh-1");
    expect(buildAuthHeaders()).toEqual({
      Authorization: "Bearer access-1",
      "X-Admin-Token": "admin-1",
    });
    expect(localStorage.getItem("tquant:auth:refresh_token")).toBeNull();
    expect(sessionStorage.getItem("tquant:auth:refresh_token")).toBe("refresh-1");
  });
});

function createMemoryStorage(): Storage {
  const data = new Map<string, string>();
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
