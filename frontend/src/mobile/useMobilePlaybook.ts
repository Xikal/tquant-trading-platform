import { useEffect } from "react"
import { appApi } from "../api/appClient"
import { strategiesApi } from "../api/strategies"
import type { AppLowBuyResponse, LowBuyScreenerResult } from "../types"
import { useMobileUiStore } from "../stores/mobileUiStore"
import { useServerState } from "../state/serverState"
import type { MobileStrategyTabKey, MobileStrategyTabOption } from "./MobileDesignCards"

const APP_LOW_BUY_TIERS = new Set(["core", "auxiliary"])
const mobilePlaybookKey = (strategy: MobileStrategyTabKey) => ["mobile", "playbook", strategy] as const

export function useMobilePlaybook(enabled: boolean) {
  const strategyFilter = useMobileUiStore((state) => state.strategyFilter)
  const strategyTabs = useMobileUiStore((state) => state.strategyTabs)
  const [playbook, setPlaybook] = useServerState<LowBuyScreenerResult | null>(mobilePlaybookKey(strategyFilter), null)
  const playbookLoading = useMobileUiStore((state) => state.playbookLoading)
  const playbookError = useMobileUiStore((state) => state.playbookError)
  const setStrategyFilter = useMobileUiStore((state) => state.setStrategyFilter)
  const setStrategyTabs = useMobileUiStore((state) => state.setStrategyTabs)
  const setPlaybookLoading = useMobileUiStore((state) => state.setPlaybookLoading)
  const setPlaybookError = useMobileUiStore((state) => state.setPlaybookError)

  async function loadMobilePlaybook(strategy: MobileStrategyTabKey = strategyFilter, force = false) {
    if (playbook && strategy === strategyFilter && !force) {
      return
    }
    try {
      setPlaybookLoading(true)
      setPlaybookError("")
      const result = toMobileScreenerResult(await appApi.getLowBuy(strategy, 18))
      setPlaybook(result)
    } catch (err) {
      setPlaybookError(err instanceof Error ? err.message : "选股宝典加载失败")
    } finally {
      setPlaybookLoading(false)
    }
  }

  useEffect(() => {
    if (!enabled) {
      return
    }
    void loadMobilePlaybook(strategyFilter)
  }, [enabled, strategyFilter])

  useEffect(() => {
    if (!enabled) {
      return
    }
    let cancelled = false
    strategiesApi.getStrategyMeta()
      .then((result) => {
        if (cancelled) return
        const nextTabs = (result.strategies ?? [])
          .filter((item) => (
            item.enabled !== false &&
            item.visibility === "full" &&
            APP_LOW_BUY_TIERS.has(item.tier)
          ))
          .map((item) => ({
            key: item.key,
            label: item.display_name || item.name || item.key
          }))
        if (nextTabs.length) {
          setStrategyTabs(nextTabs)
          setStrategyFilter((current) => (
            nextTabs.some((item) => item.key === current) ? current : nextTabs[0].key
          ))
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [enabled])

  return {
    strategyFilter,
    strategyTabs,
    playbook,
    playbookLoading,
    playbookError,
    setStrategyFilter,
    loadMobilePlaybook
  }
}

function toMobileScreenerResult(payload: AppLowBuyResponse): LowBuyScreenerResult {
  const board = payload.priority_board
  return {
    strategy_key: payload.strategy.strategy_key,
    strategy_title: payload.strategy.strategy_title,
    strategy_subtitle: payload.strategy.strategy_subtitle,
    strategy_logic: payload.strategy.strategy_logic,
    requested_mode: "quick",
    response_mode: payload.is_stale ? "quick" : "full",
    as_of_date: payload.summary.as_of_date || payload.updated_at,
    latest_trade_date: payload.summary.latest_trade_date,
    pool_size: payload.summary.pool_size,
    scanned_count: payload.summary.scanned_count,
    matched_count: payload.summary.matched_count,
    requested_scan_limit: 0,
    active_scan_limit: 0,
    full_scan_ready: payload.summary.full_scan_ready,
    full_scan_in_progress: payload.summary.full_scan_in_progress,
    full_scan_updated_at: payload.updated_at,
    market_state: board.market_state,
    market_state_text: board.market_state_text,
    market_state_category: board.market_state_category,
    market_state_category_text: board.market_state_category_text,
    data_quality: board.data_quality,
    data_quality_text: board.data_quality_text,
    data_quality_tags: board.data_quality_tags,
    market_bonus: board.market_bonus,
    market_state_strength: board.market_state_strength,
    regime_confidence: board.regime_confidence,
    state_persistence_days: board.state_persistence_days,
    transition_risk: board.transition_risk,
    breadth_ready: board.breadth_ready,
    emotion_ready: board.emotion_ready,
    stock_up_ratio: board.stock_up_ratio,
    stock_median_change: board.stock_median_change,
    style_divergence: board.style_divergence,
    hot_turnover: board.hot_turnover,
    hot_overlap_ratio: board.hot_overlap_ratio,
    limit_down_count: board.limit_down_count,
    limit_up_count: board.limit_up_count,
    board_height: board.board_height,
    previous_board_height: board.previous_board_height,
    promotion_ratio: board.promotion_ratio,
    broken_board_ratio: board.broken_board_ratio,
    promotion_break_gap: board.promotion_break_gap,
    promotion_break_pressure: board.promotion_break_pressure,
    high_flyer_retreat_ratio: board.high_flyer_retreat_ratio,
    high_flyer_gap_speed: board.high_flyer_gap_speed,
    distribution_pressure: board.distribution_pressure,
    hot_industries: board.hot_industries,
    hot_industry_source: board.hot_industry_source,
    hot_industry_source_text: board.hot_industry_source_text,
    mainline_lifecycle_state: board.mainline_lifecycle_state,
    mainline_lifecycle_text: board.mainline_lifecycle_text,
    portfolio_risk: board.portfolio_risk,
    retracement_distribution: {},
    filters: { source: "app_low_buy_snapshot", stale: payload.is_stale },
    strategy_notes: payload.warnings,
    performance: null,
    close_review_trade_date: null,
    close_review_updated_at: null,
    close_review_items: [],
    confirmed_candidates: payload.confirmed_candidates,
    history_sections: [],
    candidates: payload.watch_candidates,
  }
}
