import { describe, expect, it } from "vitest";
import {
  downsampleChartPointsSync,
  filterSortStrategyTrackingSync,
  normalizeMonitorPrioritySync,
  rankAnalysisBatchSync,
} from "../computeSync";
import type { GeneratedAnalysisResponse, GeneratedPriorityItem, GeneratedStrategyTrackingItem } from "../protocol";

describe("frontend worker sync compute fallback", () => {
  it("normalizes monitor priority items without changing backend order", () => {
    const items = [
      priorityItem("000002", 88, "near_entry"),
      priorityItem("000001", 98, "buy_now"),
      priorityItem("000003", 77, "watch"),
    ];

    const result = normalizeMonitorPrioritySync({ board: { items }, limit: 2 });

    expect(result.total).toBe(3);
    expect(result.items.map((item) => item.symbol)).toEqual(["000002", "000001"]);
    expect(result.items[0].buy_signal_state).toBe("near_entry");
  });

  it("filters and sorts strategy tracking items deterministically", () => {
    const items = [
      trackingItem("a", 1.1, -1, "active", "buy_now"),
      trackingItem("b", 5.2, -8, "active", "near_entry"),
      trackingItem("c", 3.4, -2, "stopped", "buy_now"),
    ];

    const result = filterSortStrategyTrackingSync({
      filters: { status: "active" },
      items,
      sort: "max_gain_desc",
    });

    expect(result.total).toBe(2);
    expect(result.items.map((item) => item.id)).toEqual(["b", "a"]);
  });

  it("ranks batch analysis results with the original actionable-score formula", () => {
    const result = rankAnalysisBatchSync({
      items: [
        analysisItem("watch-high", 99, false),
        analysisItem("action-low", 10, true),
        analysisItem("watch-mid", 70, false),
      ],
    });

    expect(result.total).toBe(3);
    expect(result.items.map((item) => item.symbol)).toEqual(["action-low", "watch-high", "watch-mid"]);
  });

  it("downsamples dense chart points and preserves first and last point", () => {
    const points = Array.from({ length: 240 }, (_, index) => ({
      date: `2026-01-${String((index % 30) + 1).padStart(2, "0")}`,
      nav: 1 + Math.sin(index / 9) * 0.1,
    }));

    const result = downsampleChartPointsSync({ maxPoints: 60, points });

    expect(result.input_count).toBe(240);
    expect(result.output_count).toBe(60);
    expect(result.points).toHaveLength(60);
    expect(result.points[0]).toBe(points[0]);
    expect(result.points[result.points.length - 1]).toBe(points[points.length - 1]);
  });
});

function priorityItem(symbol: string, score: number, signalState: string): GeneratedPriorityItem {
  return {
    symbol,
    name: symbol,
    strategy_key: "first_board",
    strategy_title: "首板低吸",
    priority_score: score,
    production_score: score,
    score,
    buy_signal_state: signalState,
    market: "SH",
    latest_price: 10,
    change_pct: 0,
    quote_timestamp: "2026-06-05T15:00:00+08:00",
    board_date: "2026-06-05",
    board_count: 1,
    retracement_days: 1,
    entry_zone_low: 9.8,
    entry_zone_high: 10.1,
    stop_loss: 9.5,
    take_profit: 10.6,
    ma5: 10,
    ma10: 9.9,
    ma20: 9.8,
    volume_burst_ratio: 1,
    volume_shrink_ratio: 1,
    support_distance_pct: 0,
    distribution_risk_score: 0,
    false_breakout_flag: false,
    stall_after_volume_flag: false,
    intraday_reversal_flag: false,
    execution_ready: true,
    execution_note: "",
    buy_signal_text: signalState,
    reasons: [],
    risks: [],
    tags: [],
  } as unknown as GeneratedPriorityItem;
}

function analysisItem(symbol: string, signalScore: number, actionable: boolean): GeneratedAnalysisResponse {
  return {
    symbol,
    instrument: { symbol, name: symbol, market: "SH", instrument_type: "stock" },
    quote: {
      symbol,
      name: symbol,
      market: "SH",
      instrument_type: "stock",
      last_price: 10,
      change_pct: 0,
      change_amount: 0,
      open_price: 10,
      high_price: 10,
      low_price: 10,
      prev_close: 10,
      volume: 0,
      amount: 0,
      timestamp: "2026-06-05T15:00:00+08:00",
    },
    rules: {
      symbol,
      turnaround_mode: "t1",
      supports_positive_t: false,
      supports_negative_t: false,
      same_day_sell_allowed: false,
      requires_base_position: false,
      notes: "",
    },
    sector: { sector_name: "", sector_strength: 0, market_strength: 0, alignment_score: 0, notes: "" },
    events: [],
    microstructure: { available: false, buy_pressure: 0, sell_pressure: 0, large_order_flow: 0, notes: "" },
    bars: [],
    metrics: {},
    suggestion: {
      action: "hold",
      position_pct: 0,
      risk_level: "medium",
      signal_score: signalScore,
      tradability_score: 0,
      confidence: 0,
      expected_profit_pct: 0,
      scenario: "fixture",
      reasons: [],
      blocking_rules: [],
      is_actionable: actionable,
    },
    ai: { enabled: false, summary: "", confidence: 0, suggestions: [], warnings: [] },
    compliance_notes: [],
    assumptions: [],
  } as unknown as GeneratedAnalysisResponse;
}

function trackingItem(
  id: string,
  gain: number,
  drawdown: number,
  status: string,
  signalState: string,
): GeneratedStrategyTrackingItem {
  return {
    id,
    symbol: id,
    name: id,
    strategy_key: "first_board",
    strategy_name: "首板低吸",
    strategy_family: "core",
    signal_state: signalState,
    signal_text: signalState,
    observe_only: false,
    lifecycle_status: status,
    lifecycle_status_text: status,
    first_signal_date: "2026-06-05",
    latest_signal_date: "2026-06-05",
    current_price: 10,
    latest_trade_date: "2026-06-05",
    recommendation_days: 1,
    max_gain_pct: gain,
    max_drawdown_pct: drawdown,
    entry_touched: true,
    stop_triggered: status === "stopped",
    target_touched: false,
    conclusion: "",
    failure_reason: "",
    failure_tags: [],
    market_state: "",
    market_state_text: "",
    sector_state: "",
    sector_state_text: "",
    signal_generated_at: "2026-06-05T15:00:00+08:00",
    data_cutoff_at: "2026-06-05T15:00:00+08:00",
    lookback_start_date: "2026-05-01",
    lookback_end_date: "2026-06-05",
    posterior_start_date: "2026-06-05",
    posterior_end_date: "2026-06-05",
    market_data_source: "fixture",
    market_data_updated_at: "2026-06-05T15:00:00+08:00",
    future_leak_check: "passed",
    audit_flags: [],
    abnormal_return: false,
    needs_review: false,
    review_priority: "",
    review_text: "",
    data_quality: "ok",
    data_quality_text: "ok",
    source: "fixture",
    detail_available: true,
    board_type: "main",
    board_type_text: "主板",
    display_sectors: [],
    industry_sectors: [],
    concept_sectors: [],
    user_friendly_status: "focus",
    user_friendly_status_text: "可以重点看",
    user_friendly_reason: "",
    plain_language_summary: "",
    sector_detail: {},
  } as unknown as GeneratedStrategyTrackingItem;
}
