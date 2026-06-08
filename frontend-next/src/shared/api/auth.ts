import { requestOperation } from "./client";
import type {
  AuthLoginRequest,
  AuthLogoutRequest,
  AuthMeResponse,
  AuthMfaSetupResponse,
  AuthMfaUpdateRequest,
  AuthRefreshRequest,
  AuthRegisterRequest,
  AuthTokenResponse,
  PaperAccessResponse,
} from "./types";

const ACCESS_TOKEN_KEY = "tquant:auth:access_token";
const REFRESH_TOKEN_KEY = "tquant:auth:refresh_token";
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

export function getAuthRefreshToken(): string {
  if (typeof localStorage === "undefined") return "";
  return localStorage.getItem(REFRESH_TOKEN_KEY) ?? sessionStorage.getItem(REFRESH_TOKEN_KEY) ?? "";
}

export function currentRefreshTokenRemembered(): boolean {
  if (typeof localStorage === "undefined") return true;
  if (localStorage.getItem(REFRESH_TOKEN_KEY)) return true;
  if (sessionStorage.getItem(REFRESH_TOKEN_KEY)) return false;
  return true;
}

export function setAuthRefreshToken(token: string, remember = true): void {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  if (!token) return;
  const storage = remember ? localStorage : sessionStorage;
  storage.setItem(REFRESH_TOKEN_KEY, token);
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
  setAuthRefreshToken(response.refresh_token, remember);
  return response;
}

export const authApi = {
  me: () => requestOperation<AuthMeResponse>("authMe"),
  paperAccess: () => requestOperation<PaperAccessResponse>("authPaperAccess"),
  login: (payload: AuthLoginRequest, remember = true) =>
    requestOperation<AuthTokenResponse>("authLogin", {}, { method: "POST", body: JSON.stringify(payload) }).then((response) =>
      applyAuthTokenResponse(response, remember),
    ),
  register: (payload: AuthRegisterRequest, remember = true) =>
    requestOperation<AuthTokenResponse>("authRegister", {}, { method: "POST", body: JSON.stringify(payload) }).then((response) =>
      applyAuthTokenResponse(response, remember),
    ),
  refresh: (payload: AuthRefreshRequest = { refresh_token: getAuthRefreshToken() }, remember = true) =>
    requestOperation<AuthTokenResponse>("authRefresh", {}, { method: "POST", body: JSON.stringify(payload) }).then((response) =>
      applyAuthTokenResponse(response, remember),
    ),
  logout: (payload: AuthLogoutRequest = { refresh_token: getAuthRefreshToken() }) => {
    setAuthAccessToken("");
    setAuthRefreshToken("", true);
    return requestOperation("authLogout", {}, { method: "POST", body: JSON.stringify(payload) });
  },
  setupTotp: () => requestOperation<AuthMfaSetupResponse>("authTotpSetup", {}, { method: "POST" }),
  enableTotp: (payload: AuthMfaUpdateRequest) =>
    requestOperation<AuthMeResponse>("authTotpEnable", {}, { method: "POST", body: JSON.stringify(payload) }),
  disableTotp: (payload: AuthMfaUpdateRequest) =>
    requestOperation<AuthMeResponse>("authTotpDisable", {}, { method: "POST", body: JSON.stringify(payload) }),
};
