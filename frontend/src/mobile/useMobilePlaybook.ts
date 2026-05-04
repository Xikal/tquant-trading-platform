import { useEffect, useState } from "react"
import { api } from "../api/client"
import type { LowBuyScreenerResult } from "../types"
import type { MobileStrategyTabKey } from "./MobileDesignCards"

export function useMobilePlaybook(enabled: boolean) {
  const [strategyFilter, setStrategyFilter] = useState<MobileStrategyTabKey>("first_board")
  const [playbook, setPlaybook] = useState<LowBuyScreenerResult | null>(null)
  const [playbookCache, setPlaybookCache] = useState<Partial<Record<MobileStrategyTabKey, LowBuyScreenerResult>>>({})
  const [playbookLoading, setPlaybookLoading] = useState(false)
  const [playbookError, setPlaybookError] = useState("")

  async function loadMobilePlaybook(strategy: MobileStrategyTabKey = strategyFilter, force = false) {
    const cached = playbookCache[strategy]
    if (cached && !force) {
      setPlaybook(cached)
      return
    }
    try {
      setPlaybookLoading(true)
      setPlaybookError("")
      const result = await api.getLowBuyCandidates(strategy, 18, 480, false, "full")
      setPlaybook(result)
      setPlaybookCache((current) => ({ ...current, [strategy]: result }))
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

  return {
    strategyFilter,
    playbook,
    playbookLoading,
    playbookError,
    setStrategyFilter,
    loadMobilePlaybook
  }
}
