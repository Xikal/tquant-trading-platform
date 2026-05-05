import { useEffect, useState } from "react"
import { api } from "../api/client"
import { strategiesApi } from "../api/strategies"
import type { LowBuyScreenerResult } from "../types"
import type { MobileStrategyTabKey, MobileStrategyTabOption } from "./MobileDesignCards"

export function useMobilePlaybook(enabled: boolean) {
  const [strategyFilter, setStrategyFilter] = useState<MobileStrategyTabKey>("first_board")
  const [strategyTabs, setStrategyTabs] = useState<MobileStrategyTabOption[]>([])
  const [playbook, setPlaybook] = useState<LowBuyScreenerResult | null>(null)
  const [playbookCache, setPlaybookCache] = useState<Record<string, LowBuyScreenerResult>>({})
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

  useEffect(() => {
    if (!enabled) {
      return
    }
    let cancelled = false
    strategiesApi.getStrategyMeta()
      .then((result) => {
        if (cancelled) return
        const nextTabs = (result.strategies ?? []).map((item) => ({
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
