import { clearOfflineCache, readOfflineCache, writeOfflineCache } from "./offlineCache"
import { fetchWithTimeout } from "./fetchWithTimeout"
import { isPublicApiPath } from "./publicApiPaths"
import type { ApiRequestInit } from "./requestTypes"
import { queryClient } from "../app/query/queryClient"

const configuredApiBase = import.meta.env.VITE_API_BASE_URL

export const API_BASE = configuredApiBase ?? "/api"

let adminApiToken = ""
type AuthPersistenceMode = "local" | "session" | "memory"

const AUTH_ACCESS_TOKEN_KEY = "tquant:auth:access_token"
const AUTH_PERSISTENCE_MODE_KEY = "tquant:auth:persistence_mode"
const hydratedAuth = hydrateAuthAccessToken()
let authAccessToken = hydratedAuth.accessToken
let authPersistenceMode: AuthPersistenceMode = hydratedAuth.mode
let authRefreshUnavailable = false
const MAX_IDEMPOTENT_RETRIES = 2
export const DEFAULT_API_TIMEOUT_MS = 8_000

interface AuthRefreshPayload {
  access_token?: string
}

export interface BffPartialError {
  source?: string
  detail?: string
  reason?: string
  status_code?: number | null
  timeout_ms?: number | null
  fallback_source?: string
  message?: string
}

export interface BffPartialErrorPayload {
  partial_errors?: Array<BffPartialError | string> | null
}

export async function request<T>(path: string, init?: ApiRequestInit): Promise<T> {
  const { timeoutMs, fetchInit } = splitApiRequestInit(init)
  let headers = buildRequestHeaders(fetchInit)

  const method = (fetchInit?.method ?? "GET").toUpperCase()
  const canRetry = method === "GET" || method === "HEAD"

  return requestWithOfflineFallback(
    path,
    () =>
      retryRequest(async () => {
        if (!headers.Authorization && canRefreshForPath(path)) {
          if (await refreshAccessToken()) {
            headers = buildRequestHeaders(fetchInit)
          } else {
            throw authRequiredError()
          }
        }
        let response = await fetchWithTimeout(
          `${API_BASE}${path}`,
          { ...fetchInit, headers, credentials: "include" },
          timeoutMs
        )

        if (response.status === 401 && canRefreshForPath(path) && (await refreshAccessToken())) {
          response = await fetchWithTimeout(
            `${API_BASE}${path}`,
            {
              ...fetchInit,
              headers: buildRequestHeaders(fetchInit),
              credentials: "include"
            },
            timeoutMs
          )
        }

        if (!response.ok) {
          const error = await buildHttpError(response)
          throw error
        }

        const payload = await response.json() as T
        return payload
      }, canRetry),
    canRetry
  )
}

export function getBffPartialErrors(payload: unknown): BffPartialError[] {
  if (!payload || typeof payload !== "object" || !("partial_errors" in payload)) {
    return []
  }
  const errors = (payload as BffPartialErrorPayload).partial_errors
  if (!Array.isArray(errors)) {
    return []
  }
  return errors
    .map((item): BffPartialError | null => {
      if (typeof item === "string") {
        return { detail: item }
      }
      if (!item || typeof item !== "object") {
        return null
      }
      const source = typeof item.source === "string" ? item.source : undefined
      const detail = typeof item.detail === "string" ? item.detail : undefined
      const reason = typeof item.reason === "string" ? item.reason : undefined
      const status_code = typeof item.status_code === "number" ? item.status_code : null
      const timeout_ms = typeof item.timeout_ms === "number" ? item.timeout_ms : null
      const fallback_source = typeof item.fallback_source === "string" ? item.fallback_source : undefined
      const message = typeof item.message === "string" ? item.message : undefined
      if (!(source || detail || reason || message)) {
        return null
      }
      return {
        ...(source ? { source } : {}),
        ...(detail ? { detail } : {}),
        ...(reason ? { reason } : {}),
        ...(typeof item.status_code === "number" ? { status_code } : {}),
        ...(typeof item.timeout_ms === "number" ? { timeout_ms } : {}),
        ...(fallback_source ? { fallback_source } : {}),
        ...(message ? { message } : {}),
      }
    })
    .filter((item): item is BffPartialError => item !== null)
}

export function bffPartialErrorsText(payload: unknown): string {
  return getBffPartialErrors(payload)
    .map((item) => [item.source, item.detail].filter(Boolean).join("："))
    .filter(Boolean)
    .join("；")
}

function splitApiRequestInit(init?: ApiRequestInit): { timeoutMs: number; fetchInit?: RequestInit } {
  if (!init) {
    return { timeoutMs: DEFAULT_API_TIMEOUT_MS }
  }
  const { timeoutMs, ...fetchInit } = init
  return { timeoutMs: timeoutMs ?? DEFAULT_API_TIMEOUT_MS, fetchInit }
}

function buildRequestHeaders(init?: RequestInit): Record<string, string> {
  const headers: Record<string, string> =
    init?.body === undefined
      ? { ...((init?.headers as Record<string, string> | undefined) ?? {}) }
      : {
          "Content-Type": "application/json",
          ...((init?.headers as Record<string, string> | undefined) ?? {})
        }
  const adminToken = getAdminApiToken()
  if (adminToken) {
    headers["X-Admin-Token"] = adminToken
  }
  const accessToken = getAuthAccessToken()
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
  }
  return headers
}

function canRefreshForPath(path: string): boolean {
  return !isPublicApiPath(path) && Boolean(getAuthAccessToken() || shouldAttemptAuthRefresh())
}

let refreshAccessPromise: Promise<AuthRefreshPayload | null> | null = null

export async function refreshAuthSession<T extends AuthRefreshPayload = AuthRefreshPayload>(): Promise<T> {
  const payload = await refreshAccessPayload()
  if (!payload) {
    throw authRequiredError()
  }
  return payload as T
}

async function refreshAccessToken(): Promise<boolean> {
  try {
    await refreshAuthSession()
    return true
  } catch {
    return false
  }
}

async function refreshAccessPayload(): Promise<AuthRefreshPayload | null> {
  if (!refreshAccessPromise) {
    refreshAccessPromise = fetchWithTimeout(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
      credentials: "include"
    })
      .then(async (response) => {
        if (!response.ok) {
          clearAuthTokens()
          return null
        }
        const payload = (await response.json()) as AuthRefreshPayload
        if (!payload.access_token) {
          clearAuthTokens()
          return null
        }
        setAuthTokens(payload.access_token)
        return payload
      })
      .catch(() => {
        clearAuthTokens()
        return null
      })
      .finally(() => {
        refreshAccessPromise = null
      })
  }
  return refreshAccessPromise
}

function authRequiredError(): Error {
  const error = new Error("登录已失效，请重新登录") as Error & { status?: number }
  error.status = 401
  return error
}

async function requestWithOfflineFallback<T>(
  path: string,
  operation: () => Promise<T>,
  canUseFallback: boolean
): Promise<T> {
  try {
    const payload = await operation()
    if (canUseFallback) {
      await writeOfflineCache(path, payload, getAuthAccessToken() || getAdminApiToken() || "cookie")
    }
    return payload
  } catch (error) {
    const fallback =
      canUseFallback && isRetryableError(error)
        ? await readOfflineCache<T>(path, getAuthAccessToken() || getAdminApiToken() || "cookie")
        : null
    if (fallback !== null) {
      return fallback
    }
    throw error
  }
}

async function retryRequest<T>(operation: () => Promise<T>, canRetry: boolean): Promise<T> {
  let lastError: unknown
  for (let attempt = 0; attempt <= (canRetry ? MAX_IDEMPOTENT_RETRIES : 0); attempt += 1) {
    try {
      return await operation()
    } catch (error) {
      lastError = error
      if (!canRetry || attempt >= MAX_IDEMPOTENT_RETRIES || !isRetryableError(error)) {
        throw error
      }
      await sleep(250 * 2 ** attempt)
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Request failed")
}

async function buildHttpError(response: Response): Promise<Error> {
  const contentType = response.headers.get("Content-Type") ?? ""
  let message = `Request failed: ${response.status}`
  if (contentType.includes("application/json")) {
    const payload = (await response.json()) as { detail?: string }
    message = payload.detail || message
  } else {
    message = (await response.text()) || message
  }
  const error = new Error(message) as Error & { status?: number }
  error.status = response.status
  return error
}

function isRetryableError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return true
  }
  const status = (error as Error & { status?: number }).status
  return status === undefined || status === 502 || status === 503 || status === 504
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms))
}

export function getAdminApiToken(): string {
  if (typeof window === "undefined") {
    return ""
  }
  return adminApiToken
}

export function setAdminApiToken(token: string) {
  if (typeof window === "undefined") {
    return
  }
  const nextToken = normalizeAdminApiToken(token)
  if (nextToken !== adminApiToken) {
    void clearOfflineCache()
    clearQueryApiCache()
  }
  adminApiToken = nextToken
}

export function getAuthAccessToken(): string {
  return authAccessToken
}

export function shouldAttemptAuthRefresh(): boolean {
  return authPersistenceMode !== "memory" && !authRefreshUnavailable
}

export function setAuthTokens(accessToken: string, mode: AuthPersistenceMode = authPersistenceMode) {
  if (accessToken !== authAccessToken || mode !== authPersistenceMode) {
    void clearOfflineCache()
    clearQueryApiCache()
  }
  authAccessToken = accessToken
  authPersistenceMode = mode
  authRefreshUnavailable = false
  persistAuthAccessToken(accessToken, mode)
}

export function clearAuthTokens() {
  authAccessToken = ""
  authPersistenceMode = "memory"
  authRefreshUnavailable = true
  clearPersistedAuthAccessToken()
  void clearOfflineCache()
  clearQueryApiCache()
}

export function normalizeAdminApiToken(token: string): string {
  let cleaned = token.trim()
  for (const wrapper of ["`", "\"", "'"]) {
    if (cleaned.startsWith(wrapper) && cleaned.endsWith(wrapper) && cleaned.length >= 2) {
      cleaned = cleaned.slice(1, -1).trim()
    }
  }
  return cleaned
}

export async function requestCached<T>(path: string, ttlMs: number, init?: ApiRequestInit): Promise<T> {
  return queryClient.fetchQuery({
    queryKey: apiCacheKey(path, init),
    queryFn: () => request<T>(path, init),
    staleTime: ttlMs,
    gcTime: Math.max(ttlMs * 2, 5 * 60_000),
  })
}

export function invalidateCache(prefixes: string[]) {
  queryClient.removeQueries({
    predicate: (query) => {
      const key = query.queryKey
      return Array.isArray(key)
        && key[0] === "api-cache"
        && typeof key[2] === "string"
        && prefixes.some((prefix) => key[2].includes(prefix))
    }
  })
}

function apiCacheKey(path: string, init?: ApiRequestInit) {
  return ["api-cache", (init?.method ?? "GET").toUpperCase(), path] as const
}

function clearQueryApiCache() {
  queryClient.removeQueries({
    predicate: (query) => Array.isArray(query.queryKey) && query.queryKey[0] === "api-cache"
  })
}

function hydrateAuthAccessToken(): { accessToken: string; mode: AuthPersistenceMode } {
  if (typeof window === "undefined") {
    return { accessToken: "", mode: "memory" }
  }
  clearLegacyLocalAuthAccessToken()
  const mode = hydrateAuthPersistenceMode()
  return {
    accessToken: mode === "memory" ? "" : readSessionAuthAccessToken(),
    mode
  }
}

function hydrateAuthPersistenceMode(): AuthPersistenceMode {
  if (typeof window === "undefined") {
    return "memory"
  }
  try {
    const mode = window.localStorage.getItem(AUTH_PERSISTENCE_MODE_KEY)
    return mode === "local" || mode === "session" ? mode : "memory"
  } catch {
    return "memory"
  }
}

function persistAuthAccessToken(accessToken: string, mode: AuthPersistenceMode) {
  if (typeof window === "undefined") {
    return
  }
  try {
    // Never persist bearer tokens in localStorage. A short-lived sessionStorage
    // copy keeps same-tab refresh usable when the httpOnly refresh cookie is not
    // available, while long-lived restore still relies on the secure cookie.
    window.localStorage.removeItem(AUTH_ACCESS_TOKEN_KEY)
    if (mode === "local" || mode === "session") {
      window.sessionStorage.setItem(AUTH_ACCESS_TOKEN_KEY, accessToken)
      window.localStorage.setItem(AUTH_PERSISTENCE_MODE_KEY, mode)
    } else {
      window.sessionStorage.removeItem(AUTH_ACCESS_TOKEN_KEY)
      window.localStorage.removeItem(AUTH_PERSISTENCE_MODE_KEY)
    }
  } catch {
    // Browser storage can be disabled; the in-memory token still works for this tab.
  }
}

function clearPersistedAuthAccessToken() {
  if (typeof window === "undefined") {
    return
  }
  try {
    window.localStorage.removeItem(AUTH_ACCESS_TOKEN_KEY)
    window.localStorage.removeItem(AUTH_PERSISTENCE_MODE_KEY)
    window.sessionStorage.removeItem(AUTH_ACCESS_TOKEN_KEY)
  } catch {
    // Ignore storage cleanup failures.
  }
}

function clearLegacyLocalAuthAccessToken() {
  try {
    window.localStorage.removeItem(AUTH_ACCESS_TOKEN_KEY)
  } catch {
    // Ignore storage cleanup failures.
  }
}

function readSessionAuthAccessToken(): string {
  try {
    return window.sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY) ?? ""
  } catch {
    return ""
  }
}
