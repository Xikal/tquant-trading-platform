import { useEffect, useMemo, useRef, useState } from "react"
import { appApi } from "../../api/appClient"
import { api } from "../../api/client"
import { deriveDailyDecision, deriveSimpleBuckets } from "../../mobile/simpleDecision"
import type {
  AppBootstrapResponse,
  AppHomeResponse,
  AppLowBuyDetailResponse,
  LowBuyPriorityBoardResult,
  AppWatchlistResponse,
  WatchlistItem
} from "../../types"

export type AppPreviewTab = "home" | "low_buy"

const PRIORITY_BOARD_LIMIT = 12
const instrumentIdentityCache = new Map<string, { symbol: string; name: string }>()

function formatPulseTime() {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(new Date())
}

function normalizeSymbol(value: string) {
  return value.trim().toUpperCase()
}

function stripMarketSuffix(value: string) {
  return normalizeSymbol(value).split(".")[0]
}

function addExchangeSuffix(value: string) {
  const normalized = normalizeSymbol(value)
  if (!normalized || normalized.includes(".")) {
    return normalized
  }

  const digits = normalized.replace(/[^0-9]/g, "")
  if (!digits) {
    return normalized
  }

  if (/^[569]/.test(digits)) {
    return `${digits}.SH`
  }
  if (/^[0123]/.test(digits)) {
    return `${digits}.SZ`
  }
  if (/^[48]/.test(digits)) {
    return `${digits}.BJ`
  }
  return normalized
}

function symbolCacheKeys(rawSymbol: string) {
  const normalized = normalizeSymbol(rawSymbol)
  const suffixed = addExchangeSuffix(normalized)
  return [...new Set([normalized, suffixed, stripMarketSuffix(normalized), stripMarketSuffix(suffixed)].filter(Boolean))]
}

function symbolsMatch(left: string, right: string) {
  const rightKeys = new Set(symbolCacheKeys(right))
  return symbolCacheKeys(left).some((key) => rightKeys.has(key))
}

function rememberInstrumentIdentity(symbol: string, name: string) {
  const identity = {
    symbol: addExchangeSuffix(symbol),
    name: name.trim() || addExchangeSuffix(symbol)
  }

  for (const key of symbolCacheKeys(symbol)) {
    instrumentIdentityCache.set(key, identity)
  }
  return identity
}

async function resolveInstrumentIdentity(
  rawSymbol: string,
  knownItems: Array<{ symbol: string; name: string }> = []
) {
  const keyword = normalizeSymbol(rawSymbol)
  if (!keyword) {
    throw new Error("代码必填")
  }

  for (const item of knownItems) {
    rememberInstrumentIdentity(item.symbol, item.name)
  }

  for (const key of symbolCacheKeys(keyword)) {
    const cached = instrumentIdentityCache.get(key)
    if (cached) {
      return cached
    }
  }

  const payload = await api.listInstruments(stripMarketSuffix(addExchangeSuffix(keyword)))
  const items = payload.items ?? []
  const exact =
    items.find((item) => symbolCacheKeys(item.symbol).some((key) => symbolCacheKeys(keyword).includes(key))) ??
    items[0]

  if (!exact) {
    throw new Error("未找到股票代码")
  }

  return rememberInstrumentIdentity(exact.symbol, exact.name)
}

export function useAppPreviewData(strategy = "first_board", enabled = true) {
  const locallyRemovedSymbolKeysRef = useRef<Set<string>>(new Set())
  const [bootstrap, setBootstrap] = useState<AppBootstrapResponse | null>(null)
  const [home, setHome] = useState<AppHomeResponse | null>(null)
  const [watchlist, setWatchlist] = useState<AppWatchlistResponse | null>(null)
  const [priorityBoard, setPriorityBoard] = useState<LowBuyPriorityBoardResult | null>(null)
  const [activeTab, setActiveTab] = useState<AppPreviewTab>("home")
  const [loading, setLoading] = useState(true)
  const [tabLoading, setTabLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [detail, setDetail] = useState<AppLowBuyDetailResponse | null>(null)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [pulseTime, setPulseTime] = useState("--")
  const [priorityPulseTime, setPriorityPulseTime] = useState("--")
  const dailyDecision = useMemo(() => deriveDailyDecision(priorityBoard), [priorityBoard])
  const simpleBuckets = useMemo(
    () => priorityBoard?.simple_buckets ?? deriveSimpleBuckets(priorityBoard?.items ?? []),
    [priorityBoard]
  )

  function isLocallyRemoved(symbol: string) {
    const removedKeys = locallyRemovedSymbolKeysRef.current
    return symbolCacheKeys(symbol).some((key) => removedKeys.has(key))
  }

  function markLocallyRemoved(symbol: string) {
    for (const key of symbolCacheKeys(symbol)) {
      locallyRemovedSymbolKeysRef.current.add(key)
    }
  }

  function unmarkLocallyRemoved(symbol: string) {
    for (const key of symbolCacheKeys(symbol)) {
      locallyRemovedSymbolKeysRef.current.delete(key)
    }
  }

  function buildHomeSummary(items: AppHomeResponse["items"]) {
    return {
      total: items.length,
      positive_t_count: items.filter((item) => item.signal.action === "positive_t").length,
      negative_t_count: items.filter((item) => item.signal.action === "negative_t").length,
      hold_count: items.filter((item) => item.signal.action === "hold").length,
      high_risk_count: items.filter((item) => item.signal.risk_level === "high").length
    }
  }

  function filterHomePayload(payload: AppHomeResponse): AppHomeResponse {
    const items = payload.items.filter((item) => !isLocallyRemoved(item.symbol))
    if (items.length === payload.items.length) {
      return payload
    }
    return {
      ...payload,
      items,
      summary: buildHomeSummary(items)
    }
  }

  function filterWatchlistPayload(payload: AppWatchlistResponse): AppWatchlistResponse {
    const items = payload.items.filter((item) => !isLocallyRemoved(item.symbol))
    return items.length === payload.items.length ? payload : { ...payload, items }
  }

  function upsertLocalWatchlistItem(item: WatchlistItem) {
    setWatchlist((current) => {
      if (!current) {
        return current
      }
      const nextItems = current.items.filter((existing) => !symbolsMatch(existing.symbol, item.symbol))
      return {
        ...current,
        items: [item, ...nextItems],
        updated_at: formatPulseTime()
      }
    })
  }

  function findKnownWatchSymbol(rawSymbol: string) {
    const knownItems = [
      ...(watchlist?.items ?? []).map((item) => item.symbol),
      ...(home?.items ?? []).map((item) => item.symbol)
    ]
    return knownItems.find((symbol) => symbolsMatch(symbol, rawSymbol)) ?? normalizeSymbol(rawSymbol)
  }

  function findKnownInstrument(rawSymbol: string) {
    return [
      ...(watchlist?.items ?? []).map((item) => ({ symbol: item.symbol, name: item.name })),
      ...(home?.items ?? []).map((item) => ({ symbol: item.symbol, name: item.name })),
      ...(priorityBoard?.items ?? []).map((item) => ({ symbol: item.symbol, name: item.name }))
    ].find((item) => symbolsMatch(item.symbol, rawSymbol))
  }

  async function deleteWatchlistWithFallback(rawSymbol: string) {
    const normalized = normalizeSymbol(rawSymbol)
    const knownSymbol = findKnownWatchSymbol(normalized)
    const candidates = [
      knownSymbol,
      normalized,
      addExchangeSuffix(normalized),
      stripMarketSuffix(normalized)
    ].filter(Boolean)
    const uniqueCandidates = [...new Set(candidates)]
    let lastError: unknown = null

    for (const candidate of uniqueCandidates) {
      try {
        return {
          deletedSymbol: candidate,
          result: await appApi.deleteWatchlist(candidate)
        }
      } catch (err) {
        lastError = err
        if (!(err instanceof Error) || !err.message.includes("不存在")) {
          throw err
        }
      }
    }

    throw lastError instanceof Error ? lastError : new Error("移除失败")
  }

  async function loadBootstrap() {
    const payload = await appApi.getBootstrap()
    setBootstrap(payload)
    return payload
  }

  async function loadHome() {
    const payload = await appApi.getHome()
    setHome(filterHomePayload(payload))
    setPulseTime(formatPulseTime())
    return payload
  }

  async function loadWatchlist() {
    const payload = await appApi.getWatchlist()
    setWatchlist(filterWatchlistPayload(payload))
    return payload
  }

  async function loadPriorityBoard() {
    const payload = await api.getLowBuyPriorityBoard(PRIORITY_BOARD_LIMIT)
    setPriorityBoard(payload)
    setPriorityPulseTime(formatPulseTime())
    return payload
  }

  async function loadInitial() {
    if (!enabled) {
      setLoading(false)
      return
    }
    try {
      setLoading(true)
      setError("")
      await Promise.all([loadBootstrap(), loadHome(), loadWatchlist()])
      void loadPriorityBoard().catch(() => {
        // 优先级榜预取失败不阻塞首屏
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : "App 预览加载失败")
    } finally {
      setLoading(false)
    }
  }

  async function refreshAfterHoldingMutation() {
    await Promise.all([loadHome(), loadWatchlist()])
    if (activeTab === "low_buy") {
      void loadPriorityBoard().catch(() => {
        // 榜单刷新不阻塞持仓保存结果
      })
    }
  }

  async function refreshActiveTab() {
    if (!enabled) {
      return
    }
    try {
      setError("")
      setTabLoading(true)
      if (activeTab === "home") {
        await Promise.all([loadHome(), loadWatchlist()])
      } else {
        await loadPriorityBoard()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "刷新失败")
    } finally {
      setTabLoading(false)
    }
  }

  async function openCandidate(symbol: string, detailStrategy = strategy) {
    try {
      setError("")
      setDetailLoading(true)
      const payload = await appApi.getLowBuyDetail(symbol, detailStrategy, 160)
      setDetail(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : "候选详情加载失败")
    } finally {
      setDetailLoading(false)
    }
  }

  async function saveHolding(payload: Omit<WatchlistItem, "created_at">, successMessage = "持仓已保存") {
    try {
      setActionLoading(true)
      setError("")
      const rawSymbol = normalizeSymbol(payload.symbol)
      let resolvedSymbol = rawSymbol
      let resolvedName = payload.name.trim()
      const knownInstrument = findKnownInstrument(rawSymbol)
      if (knownInstrument) {
        resolvedSymbol = knownInstrument.symbol
        resolvedName = resolvedName || knownInstrument.name
      } else if (!resolvedName || !resolvedSymbol.includes(".")) {
        const knownItems = [
          ...(watchlist?.items ?? []).map((item) => ({ symbol: item.symbol, name: item.name })),
          ...(home?.items ?? []).map((item) => ({ symbol: item.symbol, name: item.name })),
          ...(priorityBoard?.items ?? []).map((item) => ({ symbol: item.symbol, name: item.name }))
        ]
        try {
          const resolved = await resolveInstrumentIdentity(rawSymbol, knownItems)
          resolvedSymbol = resolved.symbol
          resolvedName = resolved.name
        } catch {
          resolvedSymbol = addExchangeSuffix(rawSymbol)
          resolvedName = resolvedName || resolvedSymbol
        }
      }
      const normalizedPayload = {
        ...payload,
        symbol: resolvedSymbol,
        name: resolvedName,
        memo: payload.memo ?? ""
      }
      const result = await appApi.upsertWatchlist(normalizedPayload)
      unmarkLocallyRemoved(normalizedPayload.symbol)
      upsertLocalWatchlistItem(normalizedPayload)
      setMessage(successMessage || result.message)
      setDetail((current) =>
        current && current.candidate.symbol === normalizedPayload.symbol
          ? {
              ...current,
              favorite_status: {
                in_watchlist: true,
                watchlist_symbol: normalizedPayload.symbol
              }
            }
          : current
      )
      void refreshAfterHoldingMutation().catch((err) => {
        setError(err instanceof Error ? err.message : "持仓刷新失败")
      })
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : "持仓保存失败")
      return false
    } finally {
      setActionLoading(false)
    }
  }

  async function removeWatchItem(symbol: string) {
    try {
      setActionLoading(true)
      setError("")
      const { deletedSymbol, result } = await deleteWatchlistWithFallback(symbol)
      markLocallyRemoved(deletedSymbol)
      markLocallyRemoved(symbol)
      setHome((current) => (current ? filterHomePayload(current) : current))
      setWatchlist((current) => (current ? filterWatchlistPayload(current) : current))
      setMessage(result.message || `${deletedSymbol} 已移除`)
      setDetail((current) =>
        current && symbolsMatch(current.candidate.symbol, deletedSymbol)
          ? {
              ...current,
              favorite_status: {
                in_watchlist: false,
                watchlist_symbol: null
              }
            }
          : current
      )
      void refreshAfterHoldingMutation().catch((err) => {
        setError(err instanceof Error ? err.message : "持仓刷新失败")
      })
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : "移除失败")
      return false
    } finally {
      setActionLoading(false)
    }
  }

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    void loadInitial()
  }, [strategy, enabled])

  useEffect(() => {
    if (!enabled || loading || activeTab !== "low_buy" || priorityBoard) {
      return
    }
    void loadPriorityBoard().catch((err) => {
      setError(err instanceof Error ? err.message : "选股宝典加载失败")
    })
  }, [activeTab, loading, priorityBoard, enabled])

  useEffect(() => {
    if (!enabled || loading) {
      return
    }
    const intervalMs = activeTab === "home" ? 10000 : 6000
    const timer = window.setInterval(() => {
      void refreshActiveTab()
    }, intervalMs)
    return () => window.clearInterval(timer)
  }, [activeTab, loading, enabled])

  useEffect(() => {
    if (!message) {
      return
    }
    const timer = window.setTimeout(() => {
      setMessage("")
    }, 2400)
    return () => window.clearTimeout(timer)
  }, [message])

  return {
    bootstrap,
    home,
    watchlist,
    priorityBoard,
    dailyDecision,
    simpleBuckets,
    activeTab,
    loading,
    tabLoading,
    detailLoading,
    actionLoading,
    detail,
    error,
    message,
    pulseTime,
    priorityPulseTime,
    setActiveTab,
    setDetail,
    setMessage,
    refreshActiveTab,
    openCandidate,
    saveHolding,
    removeWatchItem
  }
}
