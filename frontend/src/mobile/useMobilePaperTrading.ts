import { useEffect, useState } from "react"
import { api } from "../api/client"
import type {
  PaperAccount,
  PaperGroupedPerformance,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperTrade
} from "../types"

export function useMobilePaperTrading(enabled: boolean) {
  const [paperAccount, setPaperAccount] = useState<PaperAccount | null>(null)
  const [paperPositions, setPaperPositions] = useState<PaperPosition[]>([])
  const [paperOrders, setPaperOrders] = useState<PaperOrder[]>([])
  const [paperTrades, setPaperTrades] = useState<PaperTrade[]>([])
  const [paperPerformance, setPaperPerformance] = useState<PaperPerformance | null>(null)
  const [paperStrategyPerformance, setPaperStrategyPerformance] = useState<PaperGroupedPerformance[]>([])
  const [paperMarketPerformance, setPaperMarketPerformance] = useState<PaperGroupedPerformance[]>([])
  const [paperLoading, setPaperLoading] = useState("")
  const [paperError, setPaperError] = useState("")
  const [paperMessage] = useState("")

  async function loadPaper() {
    try {
      setPaperLoading("paper")
      setPaperError("")
      const [
        accountResult,
        positionsResult,
        ordersResult,
        tradesResult,
        performanceResult,
        strategyResult,
        marketResult
      ] = await Promise.allSettled([
        api.getPaperAccount(),
        api.getPaperPositions(),
        api.getPaperOrders(80),
        api.getPaperTrades(80),
        api.getPaperPerformance(),
        api.getPaperPerformanceByStrategy(),
        api.getPaperPerformanceByMarketState()
      ])
      if (accountResult.status === "fulfilled") setPaperAccount(accountResult.value)
      if (positionsResult.status === "fulfilled") setPaperPositions(positionsResult.value.positions)
      if (ordersResult.status === "fulfilled") setPaperOrders(ordersResult.value)
      if (tradesResult.status === "fulfilled") setPaperTrades(tradesResult.value.trades)
      if (performanceResult.status === "fulfilled") setPaperPerformance(performanceResult.value)
      if (strategyResult.status === "fulfilled") setPaperStrategyPerformance(strategyResult.value)
      if (marketResult.status === "fulfilled") setPaperMarketPerformance(marketResult.value)
      const rejected = [accountResult, positionsResult, ordersResult, tradesResult, performanceResult, strategyResult, marketResult]
        .find((result): result is PromiseRejectedResult => result.status === "rejected")
      if (rejected) {
        setPaperError(rejected.reason instanceof Error ? rejected.reason.message : "模拟盘加载失败")
      }
    } finally {
      setPaperLoading("")
    }
  }

  useEffect(() => {
    if (enabled && !paperAccount && !paperLoading) {
      void loadPaper()
    }
  }, [enabled, paperAccount, paperLoading])

  return {
    paperAccount,
    paperPositions,
    paperOrders,
    paperTrades,
    paperPerformance,
    paperStrategyPerformance,
    paperMarketPerformance,
    paperLoading,
    paperError,
    paperMessage,
    loadPaper
  }
}
