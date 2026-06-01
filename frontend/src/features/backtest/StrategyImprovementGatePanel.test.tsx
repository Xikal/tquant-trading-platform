import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { StrategyImprovementGateContent } from "./StrategyImprovementGatePanel";
import type { StrategyImprovementReportResponse } from "../../api/backtests";

describe("StrategyImprovementGateContent", () => {
  it("renders blocked data gates and missing samples", () => {
    const html = renderToStaticMarkup(<StrategyImprovementGateContent report={report} />);

    expect(html).toContain("正式回测已阻断");
    expect(html).toContain("全市场覆盖");
    expect(html).toContain("ETF 验收分钟线");
    expect(html).toContain("blocked_by_data");
    expect(html).toContain("insufficient_window_trade_day_coverage");
    expect(html).toContain("交易元数据");
    expect(html).toContain("premium_discount_coverage_lt_95pct");
    expect(html).toContain("2024-05-28");
    expect(html).toContain("510300");
    expect(html).toContain("ETF补数诊断");
    expect(html).toContain("tushare token not configured");
    expect(html).toContain("fake_minute_bars_forbidden");
    expect(html).toContain("daily_24m_coverage");
    expect(html).toContain("滚动验证");
    expect(html).toContain("随机切分禁止");
    expect(html).toContain("2025-08-01");
    expect(html).toContain("约束审计");
    expect(html).toContain("防未来函数");
    expect(html).toContain("仅影子验证");
    expect(html).toContain("动作差异");
    expect(html).toContain("shadow_record_count_lt_30");
  });
});

const report: StrategyImprovementReportResponse = {
  summary: {
    overall_status: "blocked_or_research_only",
    formal_backtest_allowed: false,
    walk_forward_allowed: false,
    production_parameter_change_allowed: false,
    reason: "两年数据覆盖、ETF 分钟线或质量门禁未达标，只允许研究/观察，不允许参数晋级。",
  },
  data_coverage: {
    status: "partial",
    coverage_pct: 0,
    full_market_trade_day_coverage_pct: 0,
    complete_trade_day_count: 0,
    trade_day_count: 158,
    symbol_count: 629,
    missing_detail_sample: [{ trade_date: "2024-05-28", symbol_count: 2, threshold: 4500 }],
  },
  data_quality: {
    status: "fail",
    metadata_coverage: {
      status: "fail",
      blocking_gap_count: 2,
      blocking_gaps: [
        "minute_bar_snapshots.premium_discount_coverage_lt_95pct",
        "minute_bar_snapshots.data_quality_fresh_coverage_lt_95pct",
      ],
    },
  },
  minute_coverage: {
    status: "blocked_by_data",
    raw_data_status: "partial",
    blocked_reason: "insufficient_window_trade_day_coverage",
    eligible_etf_count: 22,
    eligible_etf_with_minutes: 0,
    eligible_etf_with_sufficient_window_minutes: 0,
    eligible_etf_any_minute_coverage_pct: 0,
    eligible_etf_minute_coverage_pct: 0,
    expected_trade_day_count: 466,
    missing_etf_symbols: [{ symbol: "510300", name: "沪深300ETF", trade_day_coverage_pct: 0 }],
    provider_diagnostics: {
      status: "partial_data",
      report_path: "docs/reports/etf-minute-backfill-tushare-probe-2026-05-28.json",
      totals: { ok: 0, empty: 1, error: 0 },
      write_effect: "no_bars_written",
      fake_data_policy: "fake_minute_bars_forbidden",
      provider_errors_sample: [
        { symbol: "510300", source: "tushare.stk_mins", message: "tushare token not configured" },
      ],
    },
  },
  strategy_governance: {
    state_counts: { weak_strategy: 1 },
    ranking: [],
  },
  walk_forward: {
    status: "ready",
    blocked_reasons: [],
    candidate_strategy_count: 8,
    window_count: 7,
    random_split_allowed: false,
    windows: [
      {
        window_id: 1,
        train_start: "2024-05-28",
        train_end: "2025-04-30",
        validation_start: "2025-05-06",
        validation_end: "2025-07-31",
        oos_start: "2025-08-01",
        oos_end: "2025-10-31",
      },
    ],
    controlled_parameter_grid: [
      { name: "min_score", values: ["current", "+3", "+5"] },
      { name: "stop_loss", values: ["current", "-2.5pct"] },
    ],
    stability_checks: [
      { key: "pbo_or_equivalent", description: "估算过拟合概率。" },
      { key: "deflated_sharpe_or_equivalent", description: "保守修正 Sharpe。" },
    ],
  },
  constraint_policy: {
    status: "pass",
    issue_count: 0,
    production_effect: "constraints_required_before_promotion",
    required_base_constraints: ["data_quality_non_fresh_no_strong_buy"],
    required_risk_constraints: ["weak_market_block_or_reduce"],
  },
  temporal_guard: {
    status: "pass",
    issue_count: 0,
    checks: ["walk_forward_order", "shadow_features_no_future_keywords"],
  },
  auxiliary_model_shadow: {
    status: "insufficient_shadow_samples",
    record_count: 0,
    settled_count: 0,
    production_effect: "shadow_only_no_trade_permission",
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
      settled_or_labeled_count: 0,
      avg_return_5d_pct: 0,
      avg_max_adverse_5d_pct: 0,
      sell_flying_rate_pct: 0,
    },
  },
  gates: [
    {
      key: "daily_24m_coverage",
      status: "fail",
      severity: "blocking",
      message: "全 A 日线覆盖率必须达到阈值后才能正式回测和参数晋级。",
    },
  ],
  next_actions: [],
};
