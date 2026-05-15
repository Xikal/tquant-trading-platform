import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { BacktestDashboard } from "./BacktestDashboard";
import { resourceTierHint } from "./backtestDisplay";
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
  resource_tier: "full",
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
  result: {
    attribution: {
      version: "backtest-attribution-v1",
      industry: [
        {
          bucket: "软件",
          signal_count: 8,
          trade_count: 5,
          win_rate_pct: 60,
          avg_return_pct: 2.4,
          net_pnl: 12800,
        },
      ],
      market_state: [
        {
          bucket: "repair",
          signal_count: 6,
          trade_count: 4,
          win_rate_pct: 75,
          avg_return_pct: 3.1,
          net_pnl: 16800,
        },
      ],
      data_quality: [
        {
          bucket: "ok",
          signal_count: 7,
          trade_count: 5,
          win_rate_pct: 60,
          avg_return_pct: 2.4,
          net_pnl: 12800,
        },
        {
          bucket: "missing_bar",
          signal_count: 1,
          rejected_order_count: 1,
          trade_count: 0,
          win_rate_pct: 0,
          avg_return_pct: 0,
          net_pnl: 0,
        },
      ],
      data_quality_summary: {
        quality_tag: "warning",
        missing_bar_count: 1,
      },
    },
    metrics: {
      sortino_ratio: 1.8,
      calmar_ratio: 2.4,
      benchmark_alpha_pct: 7.3,
      information_ratio: 0.92,
    },
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
          resource_tier: "full",
          max_position_pct: "30",
          max_positions: "8",
          max_daily_loss_pct: "5",
          max_single_order_pct: "30",
          min_cash_reserve: "5000",
          benchmark: "000300",
        }}
        runs={[
          { ...run, id: 1, status: "pending" },
          { ...run, id: 6, status: "queued", progress: null },
          { ...run, id: 2, status: "running" },
          run,
          { ...run, id: 7, status: "succeeded" },
          { ...run, id: 4, status: "failed" },
          { ...run, id: 5, status: "cancelled" },
          { ...run, id: 8, status: "deleted" },
        ]}
        selectedRun={run}
        equity={equity}
        trades={trades}
        loading=""
        error=""
        notice=""
        research={{
          optimizationForm: {
            name: "first_board 参数优化",
            strategy: "first_board",
            train_start: "2024-01-02",
            train_end: "2025-12-31",
            test_start: "2026-01-02",
            test_end: "2026-04-30",
            initial_capital: "500000",
            execution_model: "open_price",
            optimization_target: "sharpe",
            min_score: "70,75",
            max_position_pct: "0.2,0.3",
            max_holding_days: "3,5",
            stop_loss_pct: "-0.03,-0.05",
            take_profit_pct: "0.08,0.12",
          },
          optimizations: [
            {
              id: 9,
              name: "first_board 参数优化",
              strategy: "first_board",
              status: "completed",
              progress_pct: 100,
              best_params: { min_score: 75 },
              best_is_score: 1.6,
              best_oos_score: 0.9,
              oos_downgrade: false,
              candidates: [
                {
                  rank: 1,
                  params: { min_score: 75 },
                  total_return_pct: 18.2,
                  win_rate_pct: 61.5,
                  stop_loss_rate_pct: 8.2,
                  max_drawdown_pct: -5.4,
                  profit_factor: 1.8,
                  sharpe: 1.6,
                  sample: "is",
                },
              ],
            },
          ],
          selectedOptimizationId: 9,
          selectedOptimization: {
            id: 9,
            name: "first_board 参数优化",
            strategy: "first_board",
            status: "completed",
            progress_pct: 100,
            best_params: { min_score: 75 },
            best_is_score: 1.6,
            best_oos_score: 0.9,
            oos_downgrade: false,
            candidates: [
              {
                rank: 1,
                params: { min_score: 75 },
                total_return_pct: 18.2,
                win_rate_pct: 61.5,
                stop_loss_rate_pct: 8.2,
                max_drawdown_pct: -5.4,
                profit_factor: 1.8,
                sharpe: 1.6,
                sample: "is",
              },
            ],
          },
          validationForm: {
            name: "first_board Walk-Forward 验证",
            strategy: "first_board",
            start_date: "2024-01-02",
            end_date: "2026-04-30",
            window_count: "4",
            train_ratio: "0.75",
            initial_capital: "500000",
            execution_model: "open_price",
            optimization_target: "sharpe",
            auto_promote_state_params: false,
          },
          validations: [
            {
              id: 11,
              name: "first_board Walk-Forward 验证",
              strategy: "first_board",
              status: "completed",
              progress_pct: 100,
              avg_oos_sharpe: 0.8,
              oos_pass_rate: 0.75,
              pbo_risk: "medium",
              stability_conclusion: "该策略在 3/4 窗口样本外盈利，稳定性良好",
              windows: [
                {
                  index: 1,
                  train_start: "2024-01-02",
                  train_end: "2025-07-01",
                  test_start: "2025-07-02",
                  test_end: "2026-01-02",
                  train_sharpe: 1.2,
                  test_sharpe: 0.9,
                  test_return_pct: 6.5,
                  test_max_drawdown_pct: -3.1,
                  best_params: { min_score: 75 },
                },
              ],
            },
          ],
          selectedValidationId: 11,
          selectedValidation: {
            id: 11,
            name: "first_board Walk-Forward 验证",
            strategy: "first_board",
            status: "completed",
            progress_pct: 100,
            avg_oos_sharpe: 0.8,
            oos_pass_rate: 0.75,
            pbo_risk: "medium",
            stability_conclusion: "该策略在 3/4 窗口样本外盈利，稳定性良好",
            windows: [
              {
                index: 1,
                train_start: "2024-01-02",
                train_end: "2025-07-01",
                test_start: "2025-07-02",
                test_end: "2026-01-02",
                train_sharpe: 1.2,
                test_sharpe: 0.9,
                test_return_pct: 6.5,
                test_max_drawdown_pct: -3.1,
                best_params: { min_score: 75 },
              },
            ],
          },
          completedRuns: [],
          compareRunIds: "42,45,47",
          compareResult: {
            items: [
              {
                run_id: 42,
                name: "first_board 联合回测",
                metrics: { total_return_pct: 12.4, sharpe: 1.32, max_drawdown_pct: -6.2 },
                equity: equity,
              },
            ],
          },
          monthlyReturns: {
            run_id: 42,
            items: [
              { month: "2026-01", return_pct: 3.2, benchmark_return_pct: 1.1, trade_count: 8 },
            ],
          },
          attribution: {
            strategy: [
              { bucket: "first_board", trade_count: 12, win_rate_pct: 58.3, net_pnl: 18200 },
            ],
            industry: run.result?.attribution?.industry,
            market_state: run.result?.attribution?.market_state,
            data_quality: run.result?.attribution?.data_quality,
          },
          correlation: {
            strategies: ["first_board", "volume_shrink"],
            matrix: [
              [1, 0.42],
              [0.42, 1],
            ],
          },
          loading: "",
          error: "",
          notice: "",
        }}
        researchActions={{
          onOptimizationFormChange: vi.fn(),
          onSubmitOptimization: vi.fn(),
          onSelectOptimization: vi.fn(),
          onCancelOptimization: vi.fn(),
          onDeleteOptimization: vi.fn(),
          onValidationFormChange: vi.fn(),
          onSubmitValidation: vi.fn(),
          onSelectValidation: vi.fn(),
          onCancelValidation: vi.fn(),
          onDeleteValidation: vi.fn(),
          onPromoteValidationStateParams: vi.fn(),
          onCompareRunIdsChange: vi.fn(),
          onRunCompare: vi.fn(),
          onRefreshResearch: vi.fn(),
        }}
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
    expect(resourceTierHint("full")).toContain("覆盖完整交易成本和风控口径");
    expect(html).toContain("pending");
    expect(html).toContain("queued");
    expect(html).toContain("running");
    expect(html).toContain("completed");
    expect(html).toContain("succeeded");
    expect(html).toContain("failed");
    expect(html).toContain("cancelled");
    expect(html).toContain("deleted");
    expect(html).toContain("<svg");
    expect(html).toContain("300059");
    expect(html).toContain("first_board");
    expect(html).toContain("Sortino");
    expect(html).toContain("Calmar");
    expect(html).toContain("Alpha");
    expect(html).toContain("IR");
    expect(html).toContain("+7.30%");
    expect(html).toContain("分桶归因");
    expect(html).toContain("软件");
    expect(html).toContain("repair");
    expect(html).toContain("missing_bar");
    expect(html).toContain("自动找更稳参数");
    expect(html).toContain("参数排名");
    expect(html).toContain("防过拟合检查");
    expect(html).toContain("过拟合风险");
    expect(html).toContain("回测对比");
    expect(html).toContain("归因面板");
    expect(html).toContain("月度收益");
    expect(html).toContain("相关性矩阵");
    expect(html).toContain("该策略在 3/4 窗口样本外盈利");
  });
});
