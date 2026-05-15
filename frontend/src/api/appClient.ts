import type {
  AppBootstrapResponse,
  AppAndroidUpdateResponse,
  AppLowBuyResponse,
  AppInstrumentSearchResponse,
  AuthMeResponse,
  AuthMfaSetupResponse,
  AuthTokenResponse,
  AppHomeResponse,
  AppLowBuyDetailResponse,
  AppMutationResponse,
  AppPaperSummaryResponse,
  AppSectorExclusionsResponse,
  AppWatchlistDetailResponse,
  AppWatchlistResponse,
  WatchlistItem
} from "../types"
import {
  clearAuthTokens,
  invalidateCache,
  setAuthTokens
} from "./base"
import { apiClient } from "./httpClient"

const request = apiClient.request
const requestCached = apiClient.requestCached

function invalidateAppCaches() {
  invalidateCache([
    "/app/home",
    "/app/watchlist",
    "/app/low-buy"
  ])
}

async function requestCachedOffline<T>(path: string, ttlMs: number): Promise<T> {
  return requestCached<T>(path, ttlMs)
}

export const appApi = {
  login: (payload: { username: string; password: string; device_name?: string; mfa_code?: string; remember?: boolean }) => {
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
  setupTotp: () => request<AuthMfaSetupResponse>("/auth/mfa/totp/setup", {
    method: "POST",
    body: JSON.stringify({})
  }),
  enableTotp: (code: string) => request<AuthMeResponse>("/auth/mfa/totp/enable", {
    method: "POST",
    body: JSON.stringify({ code })
  }),
  disableTotp: (code: string) => request<AuthMeResponse>("/auth/mfa/totp/disable", {
    method: "POST",
    body: JSON.stringify({ code })
  }),
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
  getPaperSummary: () => requestCachedOffline<AppPaperSummaryResponse>("/app/paper/summary", 8000),
  searchInstruments: (keyword: string, kind: "all" | "stock" | "etf" = "all") =>
    requestCached<AppInstrumentSearchResponse>(
      `/app/instruments/search?keyword=${encodeURIComponent(keyword)}&kind=${kind}&page=1&page_size=20`,
      60_000
    ),
  getSectorExclusions: () => requestCached<AppSectorExclusionsResponse>("/app/settings/sector-exclusions", 30_000),
  updateSectorExclusions: (excluded_sectors: string[]) =>
    request<AppSectorExclusionsResponse>("/app/settings/sector-exclusions", {
      method: "PUT",
      body: JSON.stringify({ excluded_sectors })
    }).then((result) => {
      invalidateAppCaches()
      invalidateCache(["/app/settings/sector-exclusions"])
      return result
    }),
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
