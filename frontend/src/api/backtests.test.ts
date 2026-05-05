import { describe, expect, it, vi } from "vitest";
import { backtestsApi } from "./backtests";

describe("backtestsApi", () => {
  it("targets the phase3 backtest endpoints", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "Content-Type": "application/json" }),
      json: async () => ({ items: [] }),
    } as Response);

    await backtestsApi.listBacktests({ page: 2, pageSize: 15, status: "running" });
    await backtestsApi.createBacktest({
      name: "联合回测",
      start_date: "2025-01-02",
      end_date: "2026-04-30",
      initial_capital: 500000,
      strategies: ["first_board", "volume_shrink"],
      execution_model: "open_price",
      risk_limits: {
        max_position_pct: 0.3,
        max_positions: 8,
        max_daily_loss_pct: 0.05,
        max_single_order_pct: 0.3,
        min_cash_reserve: 5000,
      },
      benchmark: "000300",
    });
    await backtestsApi.getBacktest(42);
    await backtestsApi.getBacktestEquity(42);
    await backtestsApi.getBacktestTrades(42, { page: 3, pageSize: 25 });
    await backtestsApi.cancelBacktest(42);

    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls).toEqual([
      "/api/backtests?page=2&page_size=15&status=running",
      "/api/backtests",
      "/api/backtests/42",
      "/api/backtests/42/equity",
      "/api/backtests/42/trades?page=3&page_size=25",
      "/api/backtests/42/cancel",
    ]);
    expect(fetchMock.mock.calls[1][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[5][1]?.method).toBe("POST");

    fetchMock.mockRestore();
  });
});
