import { useMemo } from "react"
import type {
  AppHomeResponse,
  AppWatchlistResponse,
  LowBuyPriorityBoardResult,
  LowBuyScreenerResult
} from "../types"
import {
  formatAmountCompact,
  type MobileHoldingRowData,
  type MobileMetricItem,
  splitPriorityItems
} from "./MobileDesignCards"
import { averageScore, hasHolding, uniqueLowBuyCandidates } from "./mobileViewModels"

export function useMobileAppViewModels({
  home,
  watchlist,
  priorityBoard,
  playbook
}: {
  home: AppHomeResponse | null
  watchlist: AppWatchlistResponse | null
  priorityBoard: LowBuyPriorityBoardResult | null
  playbook: LowBuyScreenerResult | null
}) {
  const watchlistItems = watchlist?.items ?? []
  const watchlistMap = useMemo(
    () => new Map(watchlistItems.map((item) => [item.symbol, item])),
    [watchlistItems]
  )
  const homeMap = useMemo(
    () => new Map((home?.items ?? []).map((item) => [item.symbol, item])),
    [home?.items]
  )

  const holdingRows = useMemo<MobileHoldingRowData[]>(() => {
    return watchlistItems
      .filter(hasHolding)
      .map((record) => {
        const liveCard = homeMap.get(record.symbol) ?? null
        const livePrice = liveCard?.quote.last_price ?? null
        const marketValue =
          typeof livePrice === "number" ? livePrice * record.base_position : null
        const floatingPnL =
          typeof livePrice === "number" && typeof record.cost_basis === "number"
            ? (livePrice - record.cost_basis) * record.base_position
            : null
        const floatingPnLPct =
          typeof livePrice === "number" &&
          typeof record.cost_basis === "number" &&
          record.cost_basis > 0
            ? ((livePrice - record.cost_basis) / record.cost_basis) * 100
            : null

        return {
          record,
          quote: liveCard?.quote ?? null,
          signal: liveCard?.signal ?? null,
          marketValue,
          floatingPnL,
          floatingPnLPct,
          plainActionText: liveCard?.plain_action_text,
          plainActionReason: liveCard?.plain_action_reason,
          plainExecutionText: liveCard?.plain_execution_text,
          plainInvalidCondition: liveCard?.plain_invalid_condition
        }
      })
  }, [homeMap, watchlistItems])

  const holdingsSummary = useMemo(() => {
    const totalMarketValue = holdingRows.reduce(
      (sum, row) => sum + (row.marketValue ?? 0),
      0
    )
    const totalFloatingPnL = holdingRows.reduce(
      (sum, row) => sum + (row.floatingPnL ?? 0),
      0
    )
    return {
      count: holdingRows.length,
      totalMarketValue,
      totalFloatingPnL
    }
  }, [holdingRows])

  const priorityBoardItems = priorityBoard?.items ?? []
  const playbookItems = useMemo(
    () => uniqueLowBuyCandidates([...(playbook?.confirmed_candidates ?? []), ...(playbook?.candidates ?? [])]),
    [playbook]
  )
  const playbookGroups = splitPriorityItems(playbookItems)
  const executableCount = (home?.summary.positive_t_count ?? 0) + (home?.summary.negative_t_count ?? 0)
  const monitorQualityScore = averageScore((home?.items ?? []).map((item) => item.signal.signal_score))

  const monitorMetrics: MobileMetricItem[] = [
    {
      label: "持仓自选",
      value: String(home?.summary.total ?? 0)
    },
    {
      label: "可执行",
      value: String(executableCount),
      tone: "positive"
    },
    {
      label: "高风险",
      value: String(home?.summary.high_risk_count ?? 0),
      tone: "warning"
    },
    {
      label: "质量分",
      value: monitorQualityScore
    }
  ]

  const holdingsMetrics: MobileMetricItem[] = [
    {
      label: "持仓股",
      value: String(holdingsSummary.count)
    },
    {
      label: "浮动盈亏",
      value: formatAmountCompact(holdingsSummary.totalFloatingPnL),
      tone: holdingsSummary.totalFloatingPnL >= 0 ? "positive" : "negative"
    },
    {
      label: "总市值",
      value: formatAmountCompact(holdingsSummary.totalMarketValue)
    },
    {
      label: "可用股",
      value: String(holdingRows.reduce((sum, row) => sum + row.record.available_position, 0))
    }
  ]

  const lowBuyMetrics: MobileMetricItem[] = [
    {
      label: "立即",
      value: `${playbookGroups.buyNow.length}↑`,
      tone: "positive"
    },
    {
      label: "观察",
      value: String(playbookGroups.nearEntry.length),
      tone: "warning"
    },
    {
      label: "跟踪",
      value: String(playbookGroups.watch.length)
    },
    {
      label: "深筛",
      value: String(playbook?.scanned_count ?? "--"),
      tone: "positive"
    }
  ]

  return {
    watchlistMap,
    holdingRows,
    priorityBoardItems,
    playbookItems,
    playbookGroups,
    monitorMetrics,
    holdingsMetrics,
    lowBuyMetrics
  }
}
