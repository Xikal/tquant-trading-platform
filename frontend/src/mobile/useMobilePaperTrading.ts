import { useCallback, useEffect, useState } from "react"
import { api } from "../api/client"
import { appApi } from "../api/appClient"
import type {
  PaperAccount,
  PaperAgentRun,
  PaperAutoTradingStatus,
  PaperGroupedPerformance,
  PaperOrderCreate,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperStockPnlResponse,
  PaperTrade
} from "../types"
import type { RiskEventItem } from "../types"

export function useMobilePaperTrading(enabled: boolean) {
  const [paperAccount, setPaperAccount] = useState<PaperAccount | null>(null)
  const [paperPositions, setPaperPositions] = useState<PaperPosition[]>([])
  const [paperOrders, setPaperOrders] = useState<PaperOrder[]>([])
  const [paperTrades, setPaperTrades] = useState<PaperTrade[]>([])
  const [paperPerformance, setPaperPerformance] = useState<PaperPerformance | null>(null)
  const [paperStrategyPerformance, setPaperStrategyPerformance] = useState<PaperGroupedPerformance[]>([])
  const [paperMarketPerformance, setPaperMarketPerformance] = useState<PaperGroupedPerformance[]>([])
  const [paperStockPnl, setPaperStockPnl] = useState<PaperStockPnlResponse | null>(null)
  const [paperAutoTradingStatus, setPaperAutoTradingStatus] = useState<PaperAutoTradingStatus | null>(null)
  const [paperRecentRuns, setPaperRecentRuns] = useState<PaperAgentRun[]>([])
  const [paperRiskEvents, setPaperRiskEvents] = useState<RiskEventItem[]>([])
  const [paperLoading, setPaperLoading] = useState("")
  const [paperError, setPaperError] = useState("")
  const [paperMessage, setPaperMessage] = useState("")

  const loadPaper = useCallback(async () => {
    try {
      setPaperLoading("paper")
      setPaperError("")
      setPaperMessage("")
      const payload = await appApi.getPaperSummary()
      setPaperAccount(payload.account ?? null)
      setPaperPositions(payload.positions ?? [])
      setPaperOrders(payload.orders ?? [])
      setPaperTrades(payload.trades ?? [])
      setPaperPerformance(payload.performance ?? null)
      setPaperStrategyPerformance(payload.strategy_performance ?? [])
      setPaperMarketPerformance(payload.market_performance ?? [])
      setPaperStockPnl(payload.stock_pnl ?? null)
      setPaperAutoTradingStatus(payload.auto_trading_status ?? null)
      setPaperRecentRuns(payload.recent_runs ?? [])
      setPaperRiskEvents(payload.risk_events ?? [])
    } catch (error) {
      setPaperError(error instanceof Error ? error.message : "模拟盘数据加载失败")
      setPaperAccount(null)
      setPaperPositions([])
      setPaperOrders([])
      setPaperTrades([])
      setPaperPerformance(null)
      setPaperStrategyPerformance([])
      setPaperMarketPerformance([])
      setPaperStockPnl(null)
      setPaperAutoTradingStatus(null)
      setPaperRecentRuns([])
      setPaperRiskEvents([])
    } finally {
      setPaperLoading("")
    }
  }, [])

  const submitPaperOrder = useCallback(async (payload: PaperOrderCreate) => {
    try {
      setPaperLoading("paper_order")
      setPaperError("")
      setPaperMessage("")
      await api.createPaperOrder(payload)
      setPaperMessage("模拟委托已提交")
      await loadPaper()
      return true
    } catch (error) {
      setPaperError(error instanceof Error ? error.message : "模拟委托提交失败")
      return false
    } finally {
      setPaperLoading("")
    }
  }, [loadPaper])

  useEffect(() => {
    if (enabled && !paperAccount && !paperLoading) {
      void loadPaper()
    }
  }, [enabled, loadPaper, paperAccount, paperLoading])

  return {
    paperAccount,
    paperPositions,
    paperOrders,
    paperTrades,
    paperPerformance,
    paperStrategyPerformance,
    paperMarketPerformance,
    paperStockPnl,
    paperAutoTradingStatus,
    paperRecentRuns,
    paperRiskEvents,
    paperLoading,
    paperError,
    paperMessage,
    loadPaper,
    submitPaperOrder
  }
}
