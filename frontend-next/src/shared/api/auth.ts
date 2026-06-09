import { requestOperation, type RequestJsonOptions } from "./client";
import type {
  AuthLoginRequest,
  AuthLogoutRequest,
  AuthMeResponse,
  AuthMfaSetupResponse,
  AuthMfaUpdateRequest,
  AuthRefreshRequest,
  AuthRegisterRequest,
  AuthTokenResponse,
} from "./types";

const ACCESS_TOKEN_KEY = "tquant:auth:access_token";
const REFRESH_TOKEN_KEY = "tquant:auth:refresh_token";
const REFRESH_SESSION_KEY = "tquant:auth:refresh_session";
const USER_CACHE_KEY = "tquant:auth:user";
const ADMIN_TOKEN_KEY = "tquant:admin_api_token";

let memoryAccessToken = "";

export function getAuthAccessToken(): string {
  if (memoryAccessToken) return memoryAccessToken;
  if (typeof localStorage === "undefined") return "";
  memoryAccessToken = localStorage.getItem(ACCESS_TOKEN_KEY) ?? "";
  return memoryAccessToken;
}

export function setAuthAccessToken(token: string): void {
  memoryAccessToken = token;
  if (typeof localStorage !== "undefined") {
    if (token) localStorage.setItem(ACCESS_TOKEN_KEY, token);
    else localStorage.removeItem(ACCESS_TOKEN_KEY);
  }
}

export function getCachedAuthUser(): AuthMeResponse["user"] | null {
  if (typeof localStorage === "undefined") return null;
  const raw = localStorage.getItem(USER_CACHE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthMeResponse["user"];
  } catch {
    localStorage.removeItem(USER_CACHE_KEY);
    return null;
  }
}

export function setCachedAuthUser(user: AuthMeResponse["user"] | null): void {
  if (typeof localStorage === "undefined") return;
  if (user) localStorage.setItem(USER_CACHE_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_CACHE_KEY);
}

export function getAuthRefreshToken(): string {
  if (typeof localStorage === "undefined") return "";
  return localStorage.getItem(REFRESH_TOKEN_KEY) ?? sessionStorage.getItem(REFRESH_TOKEN_KEY) ?? "";
}

export function hasAuthRefreshSession(): boolean {
  if (typeof localStorage === "undefined") return false;
  return Boolean(
    getAuthRefreshToken()
    || localStorage.getItem(REFRESH_SESSION_KEY)
    || sessionStorage.getItem(REFRESH_SESSION_KEY),
  );
}

export function canAttemptAuthRefresh(): boolean {
  return hasAuthRefreshSession() || Boolean(getAuthAccessToken());
}

export function currentRefreshTokenRemembered(): boolean {
  if (typeof localStorage === "undefined") return true;
  if (localStorage.getItem(REFRESH_TOKEN_KEY) || localStorage.getItem(REFRESH_SESSION_KEY)) return true;
  if (sessionStorage.getItem(REFRESH_TOKEN_KEY) || sessionStorage.getItem(REFRESH_SESSION_KEY)) return false;
  return true;
}

export function setAuthRefreshToken(token: string, remember = true, sessionActive = Boolean(token)): void {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(REFRESH_SESSION_KEY);
  sessionStorage.removeItem(REFRESH_SESSION_KEY);
  const storage = remember ? localStorage : sessionStorage;
  if (token) storage.setItem(REFRESH_TOKEN_KEY, token);
  if (sessionActive) storage.setItem(REFRESH_SESSION_KEY, "1");
}

export function clearAuthRefreshSession(): void {
  setAuthRefreshToken("", true, false);
}

export function getAdminApiToken(): string {
  if (typeof localStorage === "undefined") return "";
  return localStorage.getItem(ADMIN_TOKEN_KEY) ?? "";
}

export function setAdminApiToken(token: string): void {
  if (typeof localStorage === "undefined") return;
  if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token);
  else localStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function buildAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const accessToken = getAuthAccessToken();
  const adminToken = getAdminApiToken();
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (adminToken) headers["X-Admin-Token"] = adminToken;
  return headers;
}

export function applyAuthTokenResponse(response: AuthTokenResponse, remember = true): AuthTokenResponse {
  setAuthAccessToken(response.access_token);
  setAuthRefreshToken(response.refresh_token, remember, true);
  setCachedAuthUser(response.user);
  return response;
}

export const authApi = {
  me: (init: RequestJsonOptions = {}) => requestOperation<AuthMeResponse>("authMe", {}, init),
  login: (payload: AuthLoginRequest, remember = true) =>
    requestOperation<AuthTokenResponse>("authLogin", {}, { method: "POST", body: JSON.stringify(payload) }).then((response) =>
      applyAuthTokenResponse(response, remember),
    ),
  register: (payload: AuthRegisterRequest, remember = true) =>
    requestOperation<AuthTokenResponse>("authRegister", {}, { method: "POST", body: JSON.stringify(payload) }).then((response) =>
      applyAuthTokenResponse(response, remember),
    ),
  refresh: (payload: AuthRefreshRequest = { refresh_token: getAuthRefreshToken() }, remember = true, init: RequestJsonOptions = {}) =>
    requestOperation<AuthTokenResponse>("authRefresh", {}, { ...init, method: "POST", body: JSON.stringify(payload) }).then((response) =>
      applyAuthTokenResponse(response, remember),
    ),
  logout: (payload: AuthLogoutRequest = { refresh_token: getAuthRefreshToken() }) => {
    setAuthAccessToken("");
    clearAuthRefreshSession();
    setCachedAuthUser(null);
    return requestOperation("authLogout", {}, { method: "POST", body: JSON.stringify(payload) });
  },
  setupTotp: () => requestOperation<AuthMfaSetupResponse>("authTotpSetup", {}, { method: "POST" }),
  enableTotp: (payload: AuthMfaUpdateRequest) =>
    requestOperation<AuthMeResponse>("authTotpEnable", {}, { method: "POST", body: JSON.stringify(payload) }),
  disableTotp: (payload: AuthMfaUpdateRequest) =>
    requestOperation<AuthMeResponse>("authTotpDisable", {}, { method: "POST", body: JSON.stringify(payload) }),
};
