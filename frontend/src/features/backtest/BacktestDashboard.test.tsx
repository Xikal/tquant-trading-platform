import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { BacktestDashboard } from "./BacktestDashboard";
import type { BacktestRunDetail, BacktestTrade, EquityPoint } from "../../api/backtests";

const run: BacktestRunDetail = {
  id: 42,
  name: "first_board 联合回测",
  status: "completed",
  progress: 100,
  start_date: "2025-01-02",
  end_date: "2026-04-30",
  initial_capital: 500000,
  strategies: ["first_board", "volume_shrink"],
  execution_model: "open_price",
  benchmark: "000300",
  risk_limits: {
    max_position_pct: 0.3,
    max_positions: 8,
    max_daily_loss_pct: 0.05,
    max_single_order_pct: 0.3,
    min_cash_reserve: 5000,
  },
  summary: {
    total_return_pct: 12.4,
    benchmark_return_pct: 5.1,
    sharpe: 1.32,
    max_drawdown_pct: -6.2,
    win_rate_pct: 58.5,
    total_trades: 34,
    profit_factor: 1.48,
  },
  created_at: "2026-05-05T09:30:00",
};

const equity: EquityPoint[] = [
  { date: "2025-01-02", nav: 1, benchmark_nav: 1, drawdown_pct: 0 },
  { date: "2025-02-02", nav: 1.08, benchmark_nav: 1.02, drawdown_pct: -1.5 },
  { date: "2025-03-02", nav: 1.12, benchmark_nav: 1.05, drawdown_pct: -0.5 },
];

const trades: BacktestTrade[] = [
  {
    id: 1,
    trade_date: "2025-02-03",
    symbol: "300059",
    side: "buy",
    quantity: 1000,
    price: 18.6,
    net_amount: -18620,
    strategy: "first_board",
    return_pct: null,
    exit_reason: "",
  },
];

describe("BacktestDashboard", () => {
  it("renders phase3 form, statuses, equity chart, and trades", () => {
    const html = renderToStaticMarkup(
      <BacktestDashboard
        form={{
          name: "联合回测",
          start_date: "2025-01-02",
          end_date: "2026-04-30",
          initial_capital: "500000",
          strategies: ["first_board"],
          execution_model: "open_price",
          max_position_pct: "30",
          max_positions: "8",
          max_daily_loss_pct: "5",
          max_single_order_pct: "30",
          min_cash_reserve: "5000",
          benchmark: "000300",
        }}
        runs={[
          { ...run, id: 1, status: "pending" },
          { ...run, id: 2, status: "running" },
          run,
          { ...run, id: 4, status: "failed" },
          { ...run, id: 5, status: "cancelled" },
        ]}
        selectedRun={run}
        equity={equity}
        trades={trades}
        loading=""
        error=""
        notice=""
        onFormChange={vi.fn()}
        onToggleStrategy={vi.fn()}
        onSubmit={vi.fn()}
        onRefresh={vi.fn()}
        onSelectRun={vi.fn()}
        onCancelRun={vi.fn()}
      />
    );

    expect(html).toContain("提交回测任务");
    expect(html).toContain("日期范围");
    expect(html).toContain("执行模型");
    expect(html).toContain("pending");
    expect(html).toContain("running");
    expect(html).toContain("completed");
    expect(html).toContain("failed");
    expect(html).toContain("cancelled");
    expect(html).toContain("<svg");
    expect(html).toContain("300059");
    expect(html).toContain("first_board");
  });
});
