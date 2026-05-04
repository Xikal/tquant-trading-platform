import type { HoldingEditorSeed } from "../features/app-preview/holdingEditor"
import type { LowBuyCandidate, WatchlistItem } from "../types"
import type { MobileLowBuyCardItem } from "./MobileDesignCards"

export function hasHolding(item: WatchlistItem) {
  return item.base_position > 0 || item.available_position > 0
}

export function averageScore(values: Array<number | null | undefined>) {
  const validValues = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value))
  if (!validValues.length) {
    return "--"
  }
  return (validValues.reduce((sum, value) => sum + value, 0) / validValues.length / 10).toFixed(1)
}

export function createSeedFromWatchlist(item: WatchlistItem): HoldingEditorSeed {
  return {
    symbol: item.symbol,
    name: item.name,
    base_position: item.base_position,
    available_position: item.available_position,
    cost_basis: item.cost_basis ?? null,
    memo: item.memo
  }
}

export function createSeedFromLowBuyItem(
  item: MobileLowBuyCardItem,
  existing?: WatchlistItem
): HoldingEditorSeed {
  if (existing) {
    return createSeedFromWatchlist(existing)
  }

  return {
    symbol: item.symbol,
    name: item.name,
    base_position: 100,
    available_position: 0,
    cost_basis: item.latest_price,
    memo: `来自${item.strategy_title || "选股宝典"}`
  }
}

export function createSeedFromDetail(
  symbol: string,
  name: string,
  price: number,
  existing?: WatchlistItem
): HoldingEditorSeed {
  if (existing) {
    return createSeedFromWatchlist(existing)
  }

  return {
    symbol,
    name,
    base_position: 100,
    available_position: 0,
    cost_basis: price,
    memo: "来自选股宝典"
  }
}

export function uniqueLowBuyCandidates(items: LowBuyCandidate[]) {
  const seen = new Set<string>()
  return items.filter((item) => {
    if (!item.symbol || seen.has(item.symbol)) {
      return false
    }
    seen.add(item.symbol)
    return true
  })
}
