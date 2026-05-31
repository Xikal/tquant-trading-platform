import { useEffect, useMemo, useRef } from "react"
import { appApi } from "../../api/appClient"
import { deriveDailyDecision, deriveSimpleBuckets } from "../../mobile/simpleDecision"
import { useAppPreviewStore, type AppPreviewTab } from "../../stores/appPreviewStore"
import {
  addExchangeSuffix,
  normalizeSymbol,
  resolveInstrumentIdentity,
  stripMarketSuffix,
  symbolCacheKeys,
  symbolsMatch
} from "./appPreviewSymbols"
import type {
  AppBootstrapResponse,
  AppHomeResponse,
  AppLowBuyDetailResponse,
  LowBuyPriorityBoardResult,
  AppWatchlistResponse,
  WatchlistItem
} from "../../types"

export type { AppPreviewTab } from "../../stores/appPreviewStore"

const PRIORITY_BOARD_LIMIT = 200

function formatPulseTime() {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(new Date())
}

export function useAppPreviewData(strategy = "first_board", enabled = true) {
  const locallyRemovedSymbolKeysRef = useRef<Set<string>>(new Set())
  const bootstrap = useAppPreviewStore((state) => state.bootstrap)
  const home = useAppPreviewStore((state) => state.home)
  const watchlist = useAppPreviewStore((state) => state.watchlist)
  const priorityBoard = useAppPreviewStore((state) => state.priorityBoard)
  const activeTab = useAppPreviewStore((state) => state.activeTab)
  const loading = useAppPreviewStore((state) => state.loading)
  const tabLoading = useAppPreviewStore((state) => state.tabLoading)
  const detailLoading = useAppPreviewStore((state) => state.detailLoading)
  const actionLoading = useAppPreviewStore((state) => state.actionLoading)
  const detail = useAppPreviewStore((state) => state.detail)
  const error = useAppPreviewStore((state) => state.error)
  const message = useAppPreviewStore((state) => state.message)
  const pulseTime = useAppPreviewStore((state) => state.pulseTime)
  const priorityPulseTime = useAppPreviewStore((state) => state.priorityPulseTime)
  const setBootstrap = useAppPreviewStore((state) => state.setBootstrap)
  const setHome = useAppPreviewStore((state) => state.setHome)
  const setWatchlist = useAppPreviewStore((state) => state.setWatchlist)
  const setPriorityBoard = useAppPreviewStore((state) => state.setPriorityBoard)
  const setActiveTab = useAppPreviewStore((state) => state.setActiveTab)
  const setLoading = useAppPreviewStore((state) => state.setLoading)
  const setTabLoading = useAppPreviewStore((state) => state.setTabLoading)
  const setDetailLoading = useAppPreviewStore((state) => state.setDetailLoading)
  const setActionLoading = useAppPreviewStore((state) => state.setActionLoading)
  const setDetail = useAppPreviewStore((state) => state.setDetail)
  const setError = useAppPreviewStore((state) => state.setError)
  const setMessage = useAppPreviewStore((state) => state.setMessage)
  const setPulseTime = useAppPreviewStore((state) => state.setPulseTime)
  const setPriorityPulseTime = useAppPreviewStore((state) => state.setPriorityPulseTime)
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
    if (payload.priority_board) {
      setPriorityBoard(payload.priority_board)
      setPriorityPulseTime(formatPulseTime())
    }
    setPulseTime(formatPulseTime())
    return payload
  }

  async function loadWatchlist() {
    const payload = await appApi.getWatchlist()
    setWatchlist(filterWatchlistPayload(payload))
    return payload
  }

  async function loadPriorityBoard() {
    const payload = await appApi.getLowBuy(strategy, PRIORITY_BOARD_LIMIT)
    setPriorityBoard(payload.priority_board)
    setPriorityPulseTime(formatPulseTime())
    return payload.priority_board
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
      if (!priorityBoard) {
        void loadPriorityBoard().catch(() => {
          // 优先级榜预取失败不阻塞首屏
        })
      }
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
    const intervalMs = activeTab === "home" ? 20000 : 30000
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
