import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { BacktestRunSummary } from "../../api/backtests";
import { StrategyDoctorPanel } from "./StrategyDoctorPanel";
import { strategyDoctorVerdict } from "./strategyVerdict";

const completedRun: BacktestRunSummary = {
  id: 1,
  name: "生产策略体检",
  status: "completed",
  progress: 100,
  start_date: "2026-01-01",
  end_date: "2026-05-01",
  strategies: ["first_board"],
  resource_tier: "full",
  final_equity: 530000,
  summary: {
    total_return_pct: 6.0,
    win_rate_pct: 56.2,
    max_drawdown_pct: -7.4,
    sharpe: 1.1,
    total_trades: 88,
  },
  created_at: "2026-05-01T10:00:00",
};

describe("StrategyDoctorPanel", () => {
  it("turns a completed run into a plain-language verdict", () => {
    const verdict = strategyDoctorVerdict([completedRun]);
    expect(verdict.title).toBe("值得继续验证");
    expect(verdict.detail).toContain("胜率 56.2%");
    expect(verdict.action).toContain("样本外");
  });

  it("renders beginner-first actions", () => {
    const html = renderToStaticMarkup(
      <StrategyDoctorPanel
        runs={[completedRun]}
        loading={false}
        onQuickCheck={vi.fn()}
        onOpenSignals={vi.fn()}
        onOpenCompare={vi.fn()}
      />,
    );
    expect(html).toContain("策略医生");
    expect(html).toContain("一键体检");
    expect(html).toContain("看最近信号");
    expect(html).toContain("比较策略");
  });
});
