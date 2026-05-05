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
    await backtestsApi.deleteBacktest(42);

    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls).toEqual([
      "/api/backtests?limit=15&offset=15&status=running",
      "/api/backtests",
      "/api/backtests/42",
      "/api/backtests/42/equity",
      "/api/backtests/42/trades?limit=25&offset=50",
      "/api/backtests/42/cancel",
      "/api/backtests/42",
    ]);
    expect(fetchMock.mock.calls[1][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[5][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[6][1]?.method).toBe("DELETE");

    fetchMock.mockRestore();
  });

  it("targets the phase2 research endpoints", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "Content-Type": "application/json" }),
      json: async () => ({ items: [] }),
    } as Response);

    await backtestsApi.listOptimizations({ page: 2, pageSize: 10, status: "running" });
    await backtestsApi.createOptimization({
      name: "first_board 参数优化",
      strategy: "first_board",
      param_grid: {
        min_score: [70, 75],
        max_holding_days: [3, 5],
        stop_loss_pct: [-0.03, -0.05],
      },
      train_start: "2024-01-02",
      train_end: "2025-12-31",
      test_start: "2026-01-02",
      test_end: "2026-04-30",
      optimization_target: "sharpe",
      initial_capital: 500000,
      execution_model: "open_price",
    });
    await backtestsApi.getOptimization(9);
    await backtestsApi.cancelOptimization(9);
    await backtestsApi.deleteOptimization(9);
    await backtestsApi.listValidations({ page: 1, pageSize: 5 });
    await backtestsApi.createValidation({
      name: "first_board Walk-Forward 验证",
      strategy: "first_board",
      start_date: "2024-01-02",
      end_date: "2026-04-30",
      window_count: 4,
      train_ratio: 0.75,
      initial_capital: 500000,
      execution_model: "open_price",
    });
    await backtestsApi.getValidation(11);
    await backtestsApi.cancelValidation(11);
    await backtestsApi.deleteValidation(11);
    await backtestsApi.compareBacktests([42, 45, 47]);
    await backtestsApi.getMonthlyReturns(42);
    await backtestsApi.getAttribution(42);
    await backtestsApi.getStrategyCorrelation(42);

    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls).toEqual([
      "/api/backtests/optimize?limit=10&offset=10&status=running",
      "/api/backtests/optimize",
      "/api/backtests/optimize/9",
      "/api/backtests/optimize/9/cancel",
      "/api/backtests/optimize/9",
      "/api/backtests/validate?limit=5&offset=0",
      "/api/backtests/validate",
      "/api/backtests/validate/11",
      "/api/backtests/validate/11/cancel",
      "/api/backtests/validate/11",
      "/api/backtests/compare",
      "/api/backtests/42/monthly-returns",
      "/api/backtests/42/attribution",
      "/api/backtests/42/strategy-correlation",
    ]);
    expect(fetchMock.mock.calls[1][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[3][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[4][1]?.method).toBe("DELETE");
    expect(fetchMock.mock.calls[6][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[8][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[9][1]?.method).toBe("DELETE");
    expect(fetchMock.mock.calls[10][1]?.method).toBe("POST");

    fetchMock.mockRestore();
  });

  it("normalizes nested optimization result payloads", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "Content-Type": "application/json" }),
      json: async () => ({
        id: 9,
        name: "参数优化",
        strategy_key: "first_board",
        status: "succeeded",
        result: {
          best_is: {
            score: 1.23,
            params: { min_score: 80 },
            metrics: { sharpe: 1.4 },
          },
          best_oos: {
            score: 0.91,
            params: { min_score: 85 },
            metrics: { sharpe: 1.1 },
          },
          oos_downgrade: true,
          candidates: [{ rank: 1, params: { min_score: 85 }, sharpe: 1.1 }],
        },
      }),
    } as Response);

    const detail = await backtestsApi.getOptimization(9);

    expect(detail.strategy).toBe("first_board");
    expect(detail.best_params).toEqual({ min_score: 85 });
    expect(detail.best_is_score).toBe(1.23);
    expect(detail.best_is_metrics?.sharpe).toBe(1.4);
    expect(detail.best_oos_score).toBe(0.91);
    expect(detail.best_oos_metrics?.sharpe).toBe(1.1);
    expect(detail.oos_downgrade).toBe(true);
    expect(detail.candidates?.[0]?.rank).toBe(1);

    fetchMock.mockRestore();
  });

  it("normalizes nested walk-forward validation result payloads", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "Content-Type": "application/json" }),
      json: async () => ({
        id: 11,
        name: "稳定性验证",
        strategy_key: "volume_shrink",
        status: "succeeded",
        result: {
          window_count: 4,
          avg_is_sharpe: 1.08,
          avg_oos_sharpe: 0.72,
          oos_pass_rate: 75,
          pbo_risk: "medium",
          downgrade_review: true,
          stability_conclusion: "样本外表现降级，建议保守使用",
          windows: [{ window_index: 1, test_sharpe: 0.8 }],
        },
      }),
    } as Response);

    const detail = await backtestsApi.getValidation(11);

    expect(detail.strategy).toBe("volume_shrink");
    expect(detail.window_count).toBe(4);
    expect(detail.avg_is_sharpe).toBe(1.08);
    expect(detail.avg_oos_sharpe).toBe(0.72);
    expect(detail.oos_pass_rate).toBe(75);
    expect(detail.pbo_risk).toBe("medium");
    expect(detail.downgrade_review).toBe(true);
    expect(detail.stability_conclusion).toBe("样本外表现降级，建议保守使用");
    expect(detail.windows?.[0]?.window_index).toBe(1);

    fetchMock.mockRestore();
  });
});
