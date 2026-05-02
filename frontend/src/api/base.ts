import { isNativeHttpRuntime, nativeRequest } from "./nativeHttp"

const isNativeTarget = import.meta.env.VITE_APP_TARGET === "native"
const configuredApiBase = import.meta.env.VITE_API_BASE_URL
const configuredAdminToken = import.meta.env.VITE_ADMIN_API_TOKEN

export const API_BASE = configuredApiBase ?? (isNativeTarget ? "__NATIVE_API_BASE_REQUIRED__" : "/api")

const responseCache = new Map<string, { expiresAt: number; payload: unknown }>()
const inFlightRequests = new Map<string, Promise<unknown>>()
let adminApiToken = configuredAdminToken ? normalizeAdminApiToken(configuredAdminToken) : ""
let authAccessToken = ""

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (API_BASE === "__NATIVE_API_BASE_REQUIRED__") {
    throw new Error("Native build requires VITE_API_BASE_URL to point at the backend /api endpoint.")
  }

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

  if (isNativeHttpRuntime(isNativeTarget)) {
    return nativeRequest<T>(`${API_BASE}${path}`, {
      ...init,
      headers
    })
  }

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: "include" })

  if (!response.ok) {
    const contentType = response.headers.get("Content-Type") ?? ""
    if (contentType.includes("application/json")) {
      const payload = (await response.json()) as { detail?: string }
      throw new Error(payload.detail || `Request failed: ${response.status}`)
    }
    const message = await response.text()
    throw new Error(message || `Request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
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
