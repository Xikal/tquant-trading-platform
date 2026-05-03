import { isNativeHttpRuntime, nativeRequest } from "./nativeHttp"

const isNativeTarget = import.meta.env.VITE_APP_TARGET === "native"
const configuredApiBase = import.meta.env.VITE_API_BASE_URL
const configuredAdminToken = import.meta.env.VITE_ADMIN_API_TOKEN

export const API_BASE = configuredApiBase ?? (isNativeTarget ? "__NATIVE_API_BASE_REQUIRED__" : "/api")

const responseCache = new Map<string, { expiresAt: number; payload: unknown }>()
const inFlightRequests = new Map<string, Promise<unknown>>()
let adminApiToken = configuredAdminToken ? normalizeAdminApiToken(configuredAdminToken) : ""
let authAccessToken = ""
const MAX_IDEMPOTENT_RETRIES = 2
const OFFLINE_CACHE_PREFIX = "weis_quant:api:"
const OFFLINE_CACHE_TTL_MS = 6 * 60 * 60 * 1000
const OFFLINE_CACHEABLE_PATHS = [
  "/agent/reports/daily",
  "/app/home",
  "/market/breadth",
  "/monitor/snapshot",
  "/paper/account",
  "/paper/performance",
  "/paper/performance/dashboard",
  "/paper/positions",
  "/screeners/low-buy",
  "/watchlist"
]

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (API_BASE === "__NATIVE_API_BASE_REQUIRED__") {
    throw new Error("Native build requires VITE_API_BASE_URL to point at the backend /api endpoint.")
  }

  const headers = buildRequestHeaders(init)

  const method = (init?.method ?? "GET").toUpperCase()
  const canRetry = method === "GET" || method === "HEAD"

  if (isNativeHttpRuntime(isNativeTarget)) {
    return requestWithOfflineFallback(
      path,
      () =>
        retryRequest(
          () =>
            nativeRequest<T>(`${API_BASE}${path}`, {
              ...init,
              headers
            }),
          canRetry
        ),
      canRetry
    )
  }

  return requestWithOfflineFallback(
    path,
    () =>
      retryRequest(async () => {
        let response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: "include" })

        if (response.status === 401 && canRefreshForPath(path) && (await refreshAccessToken())) {
          response = await fetch(`${API_BASE}${path}`, {
            ...init,
            headers: buildRequestHeaders(init),
            credentials: "include"
          })
        }

        if (!response.ok) {
          const error = await buildHttpError(response)
          throw error
        }

        return response.json() as Promise<T>
      }, canRetry),
    canRetry
  )
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
  return !path.startsWith("/auth/")
}

let refreshAccessPromise: Promise<boolean> | null = null

async function refreshAccessToken(): Promise<boolean> {
  if (isNativeTarget) {
    return false
  }
  if (!refreshAccessPromise) {
    refreshAccessPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
      credentials: "include"
    })
      .then(async (response) => {
        if (!response.ok) {
          clearAuthTokens()
          return false
        }
        const payload = (await response.json()) as { access_token?: string }
        if (!payload.access_token) {
          clearAuthTokens()
          return false
        }
        setAuthTokens(payload.access_token)
        return true
      })
      .catch(() => {
        clearAuthTokens()
        return false
      })
      .finally(() => {
        refreshAccessPromise = null
      })
  }
  return refreshAccessPromise
}

async function requestWithOfflineFallback<T>(
  path: string,
  operation: () => Promise<T>,
  canUseFallback: boolean
): Promise<T> {
  try {
    const payload = await operation()
    if (canUseFallback) {
      writeOfflineCache(path, payload)
    }
    return payload
  } catch (error) {
    const fallback = canUseFallback && isRetryableError(error) ? readOfflineCache<T>(path) : null
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
  if (configuredAdminToken) {
    return normalizeAdminApiToken(configuredAdminToken)
  }
  if (typeof window === "undefined") {
    return ""
  }
  return adminApiToken
}

export function setAdminApiToken(token: string) {
  if (typeof window === "undefined" || configuredAdminToken) {
    return
  }
  adminApiToken = normalizeAdminApiToken(token)
}

export function getAuthAccessToken(): string {
  return authAccessToken
}

export function setAuthTokens(accessToken: string) {
  authAccessToken = accessToken
}

export function clearAuthTokens() {
  authAccessToken = ""
  clearOfflineCache()
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

export async function requestCached<T>(path: string, ttlMs: number, init?: RequestInit): Promise<T> {
  const cacheKey = `${init?.method ?? "GET"}:${path}`
  const now = Date.now()
  const cached = responseCache.get(cacheKey)
  if (cached && cached.expiresAt > now) {
    return cached.payload as T
  }

  const pending = inFlightRequests.get(cacheKey)
  if (pending) {
    return pending as Promise<T>
  }

  const promise = request<T>(path, init)
    .then((payload) => {
      responseCache.set(cacheKey, { expiresAt: Date.now() + ttlMs, payload })
      return payload
    })
    .finally(() => {
      inFlightRequests.delete(cacheKey)
    })
  inFlightRequests.set(cacheKey, promise as Promise<unknown>)
  return promise
}

export function invalidateCache(prefixes: string[]) {
  for (const key of [...responseCache.keys()]) {
    if (prefixes.some((prefix) => key.includes(prefix))) {
      responseCache.delete(key)
    }
  }
}

function shouldPersistOffline(path: string): boolean {
  return OFFLINE_CACHEABLE_PATHS.some((prefix) => path.startsWith(prefix))
}

function offlineCacheKey(path: string): string {
  return `${OFFLINE_CACHE_PREFIX}${offlineAuthScope()}:${path}`
}

function writeOfflineCache(path: string, payload: unknown) {
  if (typeof window === "undefined" || !shouldPersistOffline(path)) {
    return
  }
  try {
    window.localStorage.setItem(
      offlineCacheKey(path),
      JSON.stringify({
        expiresAt: Date.now() + OFFLINE_CACHE_TTL_MS,
        payload
      })
    )
  } catch {
    // localStorage may be unavailable or full; memory cache remains the fast path.
  }
}

function readOfflineCache<T>(path: string): T | null {
  if (typeof window === "undefined" || !shouldPersistOffline(path)) {
    return null
  }
  try {
    const raw = window.localStorage.getItem(offlineCacheKey(path))
    if (!raw) {
      return null
    }
    const parsed = JSON.parse(raw) as { expiresAt?: number; payload?: T }
    if (!parsed.expiresAt || parsed.expiresAt <= Date.now()) {
      window.localStorage.removeItem(offlineCacheKey(path))
      return null
    }
    return parsed.payload ?? null
  } catch {
    return null
  }
}

function offlineAuthScope(): string {
  const token = getAuthAccessToken() || getAdminApiToken() || "cookie"
  let hash = 5381
  for (let index = 0; index < token.length; index += 1) {
    hash = (hash * 33) ^ token.charCodeAt(index)
  }
  return `${hash >>> 0}`
}

function clearOfflineCache() {
  if (typeof window === "undefined") {
    return
  }
  for (const key of Object.keys(window.localStorage)) {
    if (key.startsWith(OFFLINE_CACHE_PREFIX)) {
      window.localStorage.removeItem(key)
    }
  }
}

if (typeof window !== "undefined") {
  window.setInterval(() => {
    const now = Date.now()
    for (const [key, item] of responseCache.entries()) {
      if (item.expiresAt <= now) {
        responseCache.delete(key)
      }
    }
  }, 60_000)
}
