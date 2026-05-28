import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { StrategyImprovementReportResponse } from "../../api/backtests";
import { PaperExitModelShadowSummaryContent, StrategyGovernanceSummaryContent } from "./StrategyImprovementSummary";

describe("StrategyImprovementSummary", () => {
  it("renders governance layers and blocked promotion reason", () => {
    const html = renderToStaticMarkup(<StrategyGovernanceSummaryContent report={report} />);

    expect(html).toContain("生产候选");
    expect(html).toContain("深度低吸");
    expect(html).toContain("高收益高回撤");
    expect(html).toContain("首板回调");
    expect(html).toContain("暂停/降权");
    expect(html).toContain("主线首分歧低吸");
    expect(html).toContain("参数晋级保持阻断");
    expect(html).toContain("ETF T0 必须有分钟线覆盖率");
    expect(html).toContain("随机切分禁止");
    expect(html).toContain("防未来函数 pass");
  });

  it("renders paper exit model as shadow-only with safety blockers", () => {
    const html = renderToStaticMarkup(<PaperExitModelShadowSummaryContent report={report} />);

    expect(html).toContain("模型仍为 Shadow-only");
    expect(html).toContain("硬止损覆盖：禁止");
    expect(html).toContain("shadow_record_count_lt_30");
    expect(html).toContain("不下单、不改账本、不取消硬止损");
  });
});

const report: StrategyImprovementReportResponse = {
  summary: {
    overall_status: "blocked_or_research_only",
    formal_backtest_allowed: false,
    walk_forward_allowed: false,
    production_parameter_change_allowed: false,
    reason: "ETF T0 分钟线未达标。",
  },
  data_coverage: {
    status: "complete",
    coverage_pct: 100,
    full_market_trade_day_coverage_pct: 100,
    complete_trade_day_count: 466,
    trade_day_count: 466,
  },
  minute_coverage: {
    status: "partial",
    eligible_etf_minute_coverage_pct: 0,
  },
  strategy_governance: {
    status: "available",
    strategy_count: 3,
    state_counts: {
      positive_expectancy_candidate: 1,
      high_return_high_drawdown: 1,
      weak_strategy: 1,
    },
    items: [
      {
        strategy_key: "deep_pullback",
        strategy_title: "深度低吸",
        governance_state: "positive_expectancy_candidate",
        recommended_action: "optimize_with_constraints",
        profit_factor: 1.35,
        win_rate_pct: 52.1,
      },
      {
        strategy_key: "first_board",
        strategy_title: "首板回调",
        governance_state: "high_return_high_drawdown",
        recommended_action: "add_market_state_position_exit_constraints",
        profit_factor: 2.07,
        win_rate_pct: 49.31,
      },
      {
        strategy_key: "sector_mainline_first_divergence_low_buy",
        strategy_title: "主线首分歧低吸",
        governance_state: "weak_strategy",
        recommended_action: "pause_or_downgrade_production_weight",
        profit_factor: 0.86,
        win_rate_pct: 33.07,
      },
    ],
  },
  walk_forward: {
    status: "ready",
    candidate_strategy_count: 3,
    window_count: 7,
    random_split_allowed: false,
  },
  constraint_policy: {
    status: "pass",
    issue_count: 0,
  },
  temporal_guard: {
    status: "pass",
    issue_count: 0,
  },
  auxiliary_model_shadow: {
    status: "insufficient_shadow_samples",
    record_count: 0,
    settled_count: 0,
    shadow_only: true,
    hard_stop_override_allowed: false,
    promotion_ready: false,
    promotion_blockers: ["shadow_record_count_lt_30", "settled_shadow_count_lt_30"],
    action_diff: {
      same_as_rule: 0,
      more_aggressive_than_rule: 0,
      less_aggressive_than_rule: 0,
      fallback: 0,
      hard_stop_override_risk_count: 0,
    },
    outcome_summary: {
      avg_return_5d_pct: 0,
      avg_max_adverse_5d_pct: 0,
      sell_flying_rate_pct: 0,
    },
  },
  gates: [
    {
      key: "etf_t0_minute_coverage",
      status: "fail",
      severity: "blocking",
      message: "ETF T0 必须有分钟线覆盖率，不能用日线代理验收。",
    },
  ],
  next_actions: [],
};
