import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { StrategyImprovementReportResponse } from "../../api/backtests";
import { PaperExitModelShadowSummaryContent } from "./PaperExitModelShadowSummary";

describe("PaperExitModelShadowSummary", () => {
  it("renders paper exit model as shadow-only with safety blockers", () => {
    const html = renderToStaticMarkup(<PaperExitModelShadowSummaryContent report={report} />);

    expect(html).toContain("模型仍为仅影子验证");
    expect(html).toContain("硬止损覆盖：禁止");
    expect(html).toContain("shadow_record_count_lt_30");
    expect(html).toContain("不下单、不改账本、不取消硬止损");
    expect(html).not.toContain("Fallback");
    expect(html).not.toContain("Shadow");
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
    strategy_count: 0,
    state_counts: {},
    items: [],
  },
  walk_forward: {
    status: "ready",
    candidate_strategy_count: 0,
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
  gates: [],
  next_actions: [],
};
