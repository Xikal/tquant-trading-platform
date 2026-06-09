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

    const { applyAuthTokenResponse, buildAuthHeaders, getAuthRefreshToken, hasAuthRefreshSession, setAdminApiToken } = await import("../auth");

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
    expect(hasAuthRefreshSession()).toBe(true);
    expect(buildAuthHeaders()).toEqual({
      Authorization: "Bearer access-1",
      "X-Admin-Token": "admin-1",
    });
    expect(localStorage.getItem("tquant:auth:refresh_token")).toBeNull();
    expect(sessionStorage.getItem("tquant:auth:refresh_token")).toBe("refresh-1");
    expect(sessionStorage.getItem("tquant:auth:refresh_session")).toBe("1");
  });

  it("tracks httpOnly cookie backed refresh sessions without exposing the refresh token", async () => {
    const localStorage = createMemoryStorage();
    const sessionStorage = createMemoryStorage();
    vi.stubGlobal("localStorage", localStorage);
    vi.stubGlobal("sessionStorage", sessionStorage);

    const {
      applyAuthTokenResponse,
      canAttemptAuthRefresh,
      clearAuthRefreshSession,
      currentRefreshTokenRemembered,
      getAuthRefreshToken,
      hasAuthRefreshSession,
      setAuthAccessToken,
    } = await import("../auth");

    expect(hasAuthRefreshSession()).toBe(false);
    expect(canAttemptAuthRefresh()).toBe(false);
    setAuthAccessToken("old-access");
    expect(canAttemptAuthRefresh()).toBe(true);

    applyAuthTokenResponse(authToken({ refresh_token: "" }), true);

    expect(getAuthRefreshToken()).toBe("");
    expect(hasAuthRefreshSession()).toBe(true);
    expect(currentRefreshTokenRemembered()).toBe(true);
    expect(localStorage.getItem("tquant:auth:refresh_token")).toBeNull();
    expect(localStorage.getItem("tquant:auth:refresh_session")).toBe("1");

    clearAuthRefreshSession();
    expect(hasAuthRefreshSession()).toBe(false);
    expect(localStorage.getItem("tquant:auth:refresh_session")).toBeNull();

    applyAuthTokenResponse(authToken({ refresh_token: "" }), false);
    expect(hasAuthRefreshSession()).toBe(true);
    expect(currentRefreshTokenRemembered()).toBe(false);
    expect(localStorage.getItem("tquant:auth:refresh_session")).toBeNull();
    expect(sessionStorage.getItem("tquant:auth:refresh_session")).toBe("1");
  });
});

function authToken(overrides: Partial<Awaited<ReturnType<typeof baseAuthToken>>> = {}) {
  return {
    ...baseAuthToken(),
    ...overrides,
  };
}

function baseAuthToken() {
  return {
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
  };
}

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
