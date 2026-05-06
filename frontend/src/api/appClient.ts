import type {
  AppBootstrapResponse,
  AppAndroidUpdateResponse,
  AppLowBuyResponse,
  AuthMeResponse,
  AuthTokenResponse,
  AppHomeResponse,
  AppLowBuyDetailResponse,
  AppMutationResponse,
  AppWatchlistDetailResponse,
  AppWatchlistResponse,
  WatchlistItem
} from "../types"
import {
  clearAuthTokens,
  invalidateCache,
  request,
  requestCached,
  setAuthTokens
} from "./base"

function invalidateAppCaches() {
  invalidateCache([
    "/app/home",
    "/app/watchlist",
    "/app/low-buy"
  ])
  clearOfflineCaches(["/app/home", "/app/watchlist", "/app/low-buy"])
}

async function requestCachedOffline<T>(path: string, ttlMs: number): Promise<T> {
  try {
    const payload = await requestCached<T>(path, ttlMs)
    writeOfflineCache(path, payload)
    return payload
  } catch (error) {
    const errorText = String(error)
    if (errorText.includes("401") || errorText.includes("403")) {
      throw error
    }
    const cached = readOfflineCache<T>(path)
    if (cached) {
      return cached
    }
    throw error
  }
}

function writeOfflineCache<T>(path: string, payload: T) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(
      offlineCacheKey(path),
      JSON.stringify({ cached_at: new Date().toISOString(), payload })
    )
  } catch {
    // 离线缓存是降级能力，写入失败不影响主请求。
  }
}

function readOfflineCache<T>(path: string): T | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(offlineCacheKey(path))
    if (!raw) return null
    const parsed = JSON.parse(raw) as { payload?: T }
    return parsed.payload ?? null
  } catch {
    return null
  }
}

function offlineCacheKey(path: string): string {
  return `tquant:offline:${path}`
}

function clearOfflineCaches(prefixes: string[]) {
  if (typeof window === "undefined") return
  for (const key of Object.keys(window.localStorage)) {
    if (!key.startsWith("tquant:offline:")) continue
    if (prefixes.some((prefix) => key.includes(prefix))) {
      window.localStorage.removeItem(key)
    }
  }
}

export const appApi = {
  login: (payload: { username: string; password: string; device_name?: string; remember?: boolean }) => {
    const { remember = true, ...loginPayload } = payload
    return request<AuthTokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(loginPayload)
    }).then((result) => {
      setAuthTokens(result.access_token, remember ? "local" : "session")
      invalidateAppCaches()
      return result
    })
  },
  register: (payload: { username: string; password: string; display_name?: string; device_name?: string; remember?: boolean }) => {
    const { remember = true, ...registerPayload } = payload
    return request<AuthTokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(registerPayload)
    }).then((result) => {
      setAuthTokens(result.access_token, remember ? "local" : "session")
      invalidateAppCaches()
      return result
    })
  },
  refreshAuth: () => {
    return request<AuthTokenResponse>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({})
    }).then((result) => {
      setAuthTokens(result.access_token)
      invalidateAppCaches()
      return result
    })
  },
  logout: () => {
    clearAuthTokens()
    invalidateAppCaches()
    return request<{ message: string }>("/auth/logout", {
      method: "POST",
      body: JSON.stringify({})
    }).catch(() => ({ message: "已退出登录" }))
  },
  getMe: () => request<AuthMeResponse>("/auth/me"),
  getBootstrap: () => requestCached<AppBootstrapResponse>("/app/bootstrap", 60000),
  checkAndroidUpdate: (currentVersionCode: number) =>
    requestCached<AppAndroidUpdateResponse>(
      `/app/update/android?current_version_code=${currentVersionCode}`,
      5 * 60 * 1000
    ),
  getHome: () => requestCachedOffline<AppHomeResponse>("/app/home", 8000),
  getWatchlist: () => requestCachedOffline<AppWatchlistResponse>("/app/watchlist", 8000),
  getWatchlistDetail: (symbol: string) =>
    requestCachedOffline<AppWatchlistDetailResponse>(`/app/watchlist/${encodeURIComponent(symbol)}`, 8000),
  getLowBuy: (strategy = "first_board", limit = 18) =>
    requestCachedOffline<AppLowBuyResponse>(
      `/app/low-buy?strategy=${encodeURIComponent(strategy)}&limit=${limit}&scan_mode=quick`,
      10000
    ),
  upsertWatchlist: (payload: Omit<WatchlistItem, "created_at">) =>
    request<AppMutationResponse>("/app/watchlist", {
      method: "POST",
      body: JSON.stringify(payload)
    }).then((result) => {
      invalidateAppCaches()
      return result
    }),
  deleteWatchlist: (symbol: string) =>
    request<AppMutationResponse>(`/app/watchlist/${encodeURIComponent(symbol)}`, {
      method: "DELETE"
    }).then((result) => {
      invalidateAppCaches()
      return result
    }),
  getLowBuyDetail: (symbol: string, strategy = "first_board", scanLimit = 72) =>
    requestCachedOffline<AppLowBuyDetailResponse>(
      `/app/low-buy/${encodeURIComponent(symbol)}?strategy=${encodeURIComponent(strategy)}&scan_limit=${scanLimit}`,
      10000
    ),
  favoriteLowBuy: (
    symbol: string,
    payload: {
      name?: string
      base_position?: number
      available_position?: number
      cost_basis?: number | null
      memo?: string
    }
  ) =>
    request<AppMutationResponse>(`/app/low-buy/${encodeURIComponent(symbol)}/favorite`, {
      method: "POST",
      body: JSON.stringify(payload)
    }).then((result) => {
      invalidateAppCaches()
      return result
    })
}
