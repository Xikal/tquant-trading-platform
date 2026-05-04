import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it, vi } from "vitest"
import { MobileAuthScreen } from "./MobileAuthScreen"
import { createSeedFromDetail, createSeedFromWatchlist, hasHolding } from "./mobileViewModels"
import type { WatchlistItem } from "../types"

describe("MobileAuthScreen", () => {
  it("renders the unified mobile login entry", () => {
    const html = renderToStaticMarkup(
      <MobileAuthScreen loading={false} error="" onSubmit={vi.fn()} />
    )

    expect(html).toContain("登录进入工作台")
    expect(html).toContain("盘中监控、选股宝典、模拟交易统一接入")
    expect(html).toContain("开户注册")
  })
})

describe("mobileViewModels", () => {
  const watchItem: WatchlistItem = {
    symbol: "510300",
    name: "沪深300ETF",
    base_position: 1000,
    available_position: 600,
    cost_basis: 3.45,
    memo: "底仓",
    created_at: "2026-05-04 10:00:00"
  }

  it("builds holding editor seed from an existing watchlist item", () => {
    const seed = createSeedFromWatchlist(watchItem)

    expect(seed.symbol).toBe("510300")
    expect(seed.base_position).toBe(1000)
    expect(seed.cost_basis).toBe(3.45)
    expect(hasHolding(watchItem)).toBe(true)
  })

  it("keeps existing holding data when opening from a detail card", () => {
    const seed = createSeedFromDetail("510300", "沪深300ETF", 3.6, watchItem)

    expect(seed.base_position).toBe(1000)
    expect(seed.cost_basis).toBe(3.45)
  })
})
