import { describe, expect, it } from "vitest";
import type { LowBuyCandidate, LowBuyPriorityBoardResult, LowBuyScreenerResult } from "../../types";
import {
  beijingTodayString,
  countTodayConfirmedPriorityItems,
  filterTodayConfirmedCandidates,
  filterTodayConfirmedPriorityItems,
  isBeijingTodayTradeDate,
  normalizeTradeDate,
} from "./todayRecommendations";

const NOW = new Date("2026-06-05T03:30:00.000Z");

describe("today recommendation visibility", () => {
  it("normalizes trade dates against Beijing today", () => {
    expect(beijingTodayString(NOW)).toBe("2026-06-05");
    expect(normalizeTradeDate("20260605")).toBe("2026-06-05");
    expect(normalizeTradeDate("2026/6/5 15:00:00")).toBe("2026-06-05");
    expect(isBeijingTodayTradeDate("2026-06-05", NOW)).toBe(true);
    expect(isBeijingTodayTradeDate("2026-06-04", NOW)).toBe(false);
  });

  it("keeps only current-day confirmed priority board items", () => {
    const board = priorityBoardFixture("2026-06-05");

    expect(filterTodayConfirmedPriorityItems(board, NOW).map((item) => item.symbol)).toEqual(["600000", "600001"]);
    expect(countTodayConfirmedPriorityItems(board, NOW)).toBe(2);
    expect(filterTodayConfirmedPriorityItems(priorityBoardFixture("2026-06-04"), NOW)).toEqual([]);
  });

  it("keeps only current-day confirmed playbook candidates", () => {
    const playbook = playbookFixture("2026-06-05");

    expect(filterTodayConfirmedCandidates(playbook, NOW).map((item) => item.symbol)).toEqual(["600000", "600001"]);
    expect(filterTodayConfirmedCandidates(playbookFixture("2026-06-04"), NOW)).toEqual([]);
  });

  it("does not drop a confirmed candidate when an observe row for the same symbol appears first", () => {
    const playbook = playbookFixture("2026-06-05");
    playbook.confirmed_candidates = [
      candidate("600000", "observe_confirmed"),
      candidate("600000", "buy_now"),
    ];
    playbook.candidates = [];

    expect(filterTodayConfirmedCandidates(playbook, NOW).map((item) => item.buy_signal_state)).toEqual(["buy_now"]);
  });
});

function priorityBoardFixture(latestTradeDate: string): LowBuyPriorityBoardResult {
  return {
    as_of_date: latestTradeDate,
    latest_trade_date: latestTradeDate,
    updated_at: `${latestTradeDate} 15:10:00`,
    total_candidates: 3,
    immediate_count: 2,
    focus_count: 1,
    track_count: 0,
    market_state: "repair",
    market_state_text: "修复",
    market_bonus: 0,
    market_state_strength: 0,
    regime_confidence: 0,
    state_persistence_days: 1,
    transition_risk: 0,
    breadth_ready: true,
    emotion_ready: true,
    stock_up_ratio: 0.5,
    stock_median_change: 0,
    style_divergence: 0,
    hot_turnover: 0,
    hot_overlap_ratio: 0,
    limit_up_count: 0,
    board_height: 0,
    previous_board_height: 0,
    promotion_ratio: 0,
    broken_board_ratio: 0,
    promotion_break_gap: 0,
    promotion_break_pressure: 0,
    high_flyer_retreat_ratio: 0,
    high_flyer_gap_speed: 0,
    distribution_pressure: 0,
    hot_industries: [],
    hot_industry_source: "",
    hot_industry_source_text: "",
    items: [
      priorityItem("600000", "buy_now"),
      priorityItem("600001", "soft_buy_now"),
      priorityItem("600002", "observe_confirmed"),
    ],
  };
}

function priorityItem(symbol: string, buySignalState: "buy_now" | "soft_buy_now" | "observe_confirmed") {
  return {
    symbol,
    name: symbol,
    strategy_key: "baseline",
    strategy_title: "策略",
    strategy_titles: ["策略"],
    strategy_count: 1,
    latest_price: 10,
    change_pct: 1,
    quote_timestamp: "",
    buy_signal_state: buySignalState,
    buy_signal_text: buySignalState,
    priority_score: 80,
    strategy_weight_score: 80,
    industry_rotation_bonus: 0,
    industry_rotation_text: "",
    action_summary: "",
    blocked_reason: "",
    entry_zone_low: 9,
    entry_zone_high: 10,
    stop_loss: 8,
    suggested_position_pct: 10,
    suggested_position_text: "一成",
  };
}

function playbookFixture(latestTradeDate: string): LowBuyScreenerResult {
  return {
    strategy_key: "baseline",
    strategy_title: "策略",
    strategy_subtitle: "",
    strategy_logic: "",
    requested_mode: "quick",
    response_mode: "quick",
    as_of_date: latestTradeDate,
    latest_trade_date: latestTradeDate,
    pool_size: 3,
    scanned_count: 3,
    matched_count: 3,
    requested_scan_limit: 3,
    active_scan_limit: 3,
    full_scan_ready: true,
    full_scan_in_progress: false,
    market_state: "repair",
    market_state_text: "修复",
    market_bonus: 0,
    market_state_strength: 0,
    regime_confidence: 0,
    state_persistence_days: 1,
    transition_risk: 0,
    breadth_ready: true,
    emotion_ready: true,
    stock_up_ratio: 0.5,
    stock_median_change: 0,
    style_divergence: 0,
    hot_turnover: 0,
    hot_overlap_ratio: 0,
    limit_up_count: 0,
    board_height: 0,
    previous_board_height: 0,
    promotion_ratio: 0,
    broken_board_ratio: 0,
    promotion_break_gap: 0,
    promotion_break_pressure: 0,
    high_flyer_retreat_ratio: 0,
    high_flyer_gap_speed: 0,
    distribution_pressure: 0,
    hot_industries: [],
    hot_industry_source: "",
    hot_industry_source_text: "",
    retracement_distribution: {},
    filters: {},
    strategy_notes: [],
    close_review_items: [],
    confirmed_candidates: [
      candidate("600000", "buy_now"),
      candidate("600001", "soft_buy_now"),
      candidate("600002", "observe_confirmed"),
    ],
    history_sections: [],
    candidates: [],
  };
}

function candidate(symbol: string, buySignalState: "buy_now" | "soft_buy_now" | "observe_confirmed") {
  return {
    symbol,
    name: symbol,
    strategy_key: "baseline",
    strategy_title: "策略",
    latest_price: 10,
    change_pct: 1,
    score: 80,
    buy_signal_state: buySignalState,
    buy_signal_text: buySignalState,
    buy_signal_hint: "",
    entry_zone_low: 9,
    entry_zone_high: 10,
    stop_loss: 8,
    risk_tier: "note" as const,
    suggested_position_pct: 10,
    suggested_position_text: "一成",
  } as LowBuyCandidate;
}
