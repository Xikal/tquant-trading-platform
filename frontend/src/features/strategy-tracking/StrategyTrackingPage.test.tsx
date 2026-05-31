import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import { configureApiClient, resetApiClient } from "../../api/httpClient";
import type { StrategyTrackingDetailResponse, StrategyTrackingHoldingAnalysis, StrategyTrackingItem, StrategyTrackingPerformance, StrategyTrackingSummary } from "../../types";
import { Topbar } from "../trading-workspace/Topbar";
import { StrategyTrackingDetailContent } from "./StrategyTrackingDetailDrawer";
import { StrategyTrackingDiagnosticsPanel } from "./StrategyTrackingDiagnosticsPanel";
import { DriftMonitorPanel } from "./DriftMonitorPanel";
import { StrategyTrackingHoldingAnalysisPanel } from "./StrategyTrackingHoldingAnalysisPanel";
import { StrategyTrackingPerformanceTable } from "./StrategyTrackingPerformanceTable";
import { StrategyTrackingReviewPanel } from "./StrategyTrackingReviewPanel";
import { StrategyTrackingSummaryBar } from "./StrategyTrackingSummaryBar";
import { buildParams } from "./StrategyTrackingPage";
import { StrategyTrackingTable } from "./StrategyTrackingTable";

afterEach(() => {
  resetApiClient();
});

describe("StrategyTracking UI", () => {
  it("changes top navigation from old pages to strategy tracking", () => {
    const html = renderToStaticMarkup(
      <Topbar
        page="strategy-tracking"
        setPage={vi.fn()}
        priorityBoard={null}
        watchCards={[]}
        currentUser={{ id: 1, username: "tester", display_name: "tester", roles: [], can_paper_trade: true, created_at: "2026-05-29T10:00:00+08:00" }}
        onLogout={vi.fn()}
      />
    );

    expect(html).toContain("策略跟踪");
    expect(html).not.toContain("策略工作台");
    expect(html).not.toContain("市场情绪");
  });

  it("renders compact summary and data quality fallback", () => {
    const html = renderToStaticMarkup(
      <StrategyTrackingSummaryBar
        summary={summaryFixture({
          data_quality: "partial",
          data_quality_text: "部分行情或 payload 缺失，已降级展示",
        })}
      />
    );

    expect(html).toContain("当前跟踪");
    expect(html).toContain("部分行情或 payload 缺失");
    expect(html).toContain("跌破止损");
  });

  it("renders list rows with stable detail actions and pagination wiring", () => {
    const openDetail = vi.fn();
    const onPageChange = vi.fn();

    const html = renderToStaticMarkup(
      <StrategyTrackingTable
        items={[itemFixture()]}
        total={1}
        page={1}
        pageSize={30}
        loading={false}
        viewMode="professional"
        onOpenDetail={openDetail}
        onPageChange={onPageChange}
      />
    );

    expect(html).toContain("浦发银行");
    expect(html).toContain("首板回调");
    expect(html).toContain("策略线");
    expect(html).toContain("旧策略排序");
    expect(html).toContain("过火勿追");
    expect(html).toContain("已到计划买入区");
    expect(html).toContain("已跌破风险线");
    expect(html).toContain("信号性质");
    expect(html).toContain("买入类：确定买入");
    expect(html).toContain("信号后最高涨过");
    expect(html).toContain("短线1-3天");
    expect(html).toContain("需复核");
  });

  it("renders detail drawer timeline without needing list payload_json", () => {
    const html = renderToStaticMarkup(
      <StrategyTrackingDetailContent detail={detailFixture()} viewMode="professional" />
    );

    expect(html).toContain("浦发银行");
    expect(html).toContain("过火勿追");
    expect(html).toContain("首次信号");
    expect(html).toContain("分钟K线");
    expect(html).toContain("2026-04-21");
    expect(html).toContain("跌破风险线");
    expect(html).toContain("最优持有");
    expect(html).toContain("延长持有评分");
    expect(html).toContain("失败归因");
    expect(html).toContain("最优退出");
    expect(html).toContain("决策上下文");
    expect(html).toContain("信号归因");
    expect(html).toContain("事件风险");
    expect(html).toContain("事件源缺失");
    expect(html).toContain("分钟入场");
    expect(html).toContain("数据缺失");
    expect(html).not.toContain("payload_json");
  });

  it("renders one-click review summary from strategy samples", () => {
    const html = renderToStaticMarkup(
      <StrategyTrackingReviewPanel summary={summaryFixture()} performance={[performanceFixture()]} />
    );

    expect(html).toContain("一键复盘");
    expect(html).toContain("首板回调");
    expect(html).toContain("下一阶段");
  });

  it("renders performance aggregation table", () => {
    const html = renderToStaticMarkup(<StrategyTrackingPerformanceTable items={[performanceFixture()]} />);

    expect(html).toContain("信号次数");
    expect(html).toContain("买点触达率");
    expect(html).toContain("首板回调");
  });



  it("renders holding analysis tab conclusions", () => {
    const html = renderToStaticMarkup(<StrategyTrackingHoldingAnalysisPanel items={[holdingFixture()]} loading={false} />);

    expect(html).toContain("信号次数");
    expect(html).toContain("首板回调更适合短线");
    expect(html).toContain("短线 1-3 天");
  });

  it("builds board filter params from store state", () => {
    const params = buildParams({
      ...baseStoreState(),
      excludeChinext: true,
      excludeStar: true,
      boardFilter: "main_only",
      userStatus: "focus",
    });

    expect(params.exclude_chinext).toBe(true);
    expect(params.exclude_star).toBe(true);
    expect(params.board_filter).toBe("main_only");
    expect(params.user_status).toBe("focus");
  });

  it("builds strategy lane params from store state", () => {
    const params = buildParams({
      ...baseStoreState(),
      strategyVariant: "front_row_weighted",
    });

    expect(params.strategy_variant).toBe("front_row_weighted");
  });

  it("loads the strategy tracking homepage through one snapshot endpoint", async () => {
    const requestedPaths: string[] = [];
    configureApiClient({
      request: async <T,>() => ({} as T),
      requestCached: async <T,>(path: string) => {
        requestedPaths.push(path);
        return snapshotFixture() as T;
      },
    });

    await api.getStrategyTrackingSnapshot({
      range: 20,
      strategy_key: "first_board",
      strategy_variant: "front_row_weighted",
      hit_entry: true,
      exclude_chinext: true,
      exclude_star: true,
    });

    expect(requestedPaths).toHaveLength(1);
    expect(requestedPaths[0]).toContain("/strategy-tracking/snapshot?");
    expect(requestedPaths[0]).toContain("range=20");
    expect(requestedPaths[0]).toContain("strategy_key=first_board");
    expect(requestedPaths[0]).toContain("strategy_variant=front_row_weighted");
    expect(requestedPaths[0]).toContain("exclude_chinext=true");
    expect(requestedPaths[0]).not.toContain("/strategy-tracking/items?");
    expect(requestedPaths[0]).not.toContain("/strategy-tracking/holding-analysis?");
  });

  it("renders diagnostics for market segments and shadow zero reasons", () => {
    const html = renderToStaticMarkup(<StrategyTrackingDiagnosticsPanel result={listFixture()} viewMode="professional" />);

    expect(html).toContain("Shadow 观测样本为 0");
    expect(html).toContain("观测表里目前没有该模型观测记录");
    expect(html).toContain("强势行情");
    expect(html).toContain("冲高回落");
  });

  it("renders drift monitor with realized vs expected evidence", () => {
    const html = renderToStaticMarkup(
      <DriftMonitorPanel
        loading={false}
        defaultOpen
        total={1}
        items={[{
          strategy_key: "first_board",
          as_of_date: "2026-06-30",
          window_days: 60,
          realized_pf: 1.2,
          expected_pf: 1.8,
          realized_avg: 0.4,
          expected_avg: 0.8,
          realized_winrate: 52,
          expected_winrate: 60,
          realized_max5: 2.1,
          backtest_max5: 4.0,
          realized_max10: 3.0,
          backtest_max10: 5.0,
          tracking_error: -0.4,
          decay_pct: -50,
          drift_flag: "decay_advisory",
          sample_settled: 30,
        }]}
      />
    );

    expect(html).toContain("真实战绩漂移");
    expect(html).toContain("decay_advisory");
    expect(html).toContain("first_board");
    expect(html).toContain("PF");
  });
});

function summaryFixture(overrides: Partial<StrategyTrackingSummary> = {}): StrategyTrackingSummary {
  return {
    tracking_count: 3,
    active_count: 1,
    today_new_count: 1,
    in_entry_zone_count: 1,
    stopped_count: 1,
    needs_review_count: 1,
    abnormal_return_count: 0,
    shadow_observation_count: 0,
    avg_current_return_pct: 2.3,
    median_max_gain_pct: 5.6,
    data_quality: "ok",
    data_quality_text: "数据完整",
    generated_at: "2026-05-29T10:00:00+00:00",
    ...overrides,
  };
}

function listFixture() {
  return {
    items: [itemFixture()],
    total: 1,
    limit: 30,
    offset: 0,
    sort: "max_gain_desc",
    summary: summaryFixture(),
    performance: [performanceFixture()],
    market_segments: [
      {
        strategy_key: "first_board",
        strategy_name: "首板回调",
        market_state: "strong_market",
        market_state_text: "强势行情",
        sector_state: "sector_main_rise",
        sector_state_text: "板块主升",
        recommendation_count: 1,
        entry_touch_rate: 100,
        win_rate_5d: 0,
        avg_max_gain_pct: 10,
        avg_max_drawdown_pct: -16.19,
        stop_loss_rate: 100,
        return_drawdown_ratio: 0.62,
      },
    ],
    shadow_observations: [
      {
        model_key: "main_force_model_observation",
        model_version: "",
        observation_count: 0,
        latest_observed_at: null,
        linked_tracking_count: 0,
        no_sample_reason: "no_model_observation",
        no_sample_reason_text: "观测表里目前没有该模型观测记录",
        actionable_count: 0,
        settled_count: 0,
        success_rate_pct: 0,
      },
    ],
    partial_errors: [],
    production_writeable: false,
    read_path: "python_read_through_go_boundary_reserved",
    rust_math_used: true,
    notes: [],
  };
}

function snapshotFixture() {
  return {
    status: "fresh",
    stale: false,
    generated_at: "2026-05-29T10:00:00+08:00",
    source_data_cutoff: "2026-05-29T09:30:00+08:00",
    data_version: "2026-05-29:2026-05-29T09:30:00:1",
    snapshot_key: "strategy-tracking:test",
    as_of_date: "2026-05-29",
    payload: {
      summary: summaryFixture(),
      items: [itemFixture()],
      performance: [performanceFixture()],
      market_segments: listFixture().market_segments,
      holding_summary: {
        items: [holdingFixture()],
        generated_at: "2026-05-29T10:00:00+08:00",
        data_quality: "ok",
        production_writeable: false,
      },
      shadow_observations: listFixture().shadow_observations,
      audit: {
        future_leak_check: "passed",
        checked_count: 1,
        violation_count: 0,
        abnormal_return_count: 0,
        needs_review_count: 1,
        audit_flags: [],
      },
    },
    total: 1,
    limit: 30,
    offset: 0,
    sort: "max_gain_desc",
    partial_errors: [],
    production_writeable: false,
    read_path: "strategy_tracking_snapshot",
    notes: [],
  };
}

function itemFixture(): StrategyTrackingItem {
  return {
    id: "first_board:600000:2026-04-20",
    symbol: "600000",
    name: "浦发银行",
    strategy_key: "first_board",
    strategy_name: "首板回调",
    strategy_family: "core",
    signal_state: "buy_now",
    signal_text: "确定可买",
    observe_only: false,
    lifecycle_status: "stopped",
    lifecycle_status_text: "跌破止损",
    first_signal_date: "2026-04-20",
    latest_signal_date: "2026-04-21",
    first_signal_price: 10,
    entry_zone_low: 9.5,
    entry_zone_high: 10.5,
    stop_loss: 9,
    target_price: 11,
    current_price: 8.8,
    latest_trade_date: "2026-04-22",
    recommendation_days: 2,
    distance_to_entry_pct: -7.37,
    current_return_pct: -12,
    max_price_after_signal: 11,
    max_gain_pct: 10,
    max_drawdown_pct: -16.19,
    actual_low_price: 8.8,
    actual_low_date: "2026-04-22",
    actual_high_date: "2026-04-21",
    spike_retrace_pct: 22,
    best_holding_days: 2,
    best_exit_date: "2026-04-21",
    best_exit_return_pct: 5,
    best_exit_drawdown_pct: 0,
    return_drawdown_ratio: 5,
    giveback_from_peak_pct: 22,
    holding_bucket: "short_1_3d",
    exit_quality: "late_exit",
    exit_reason: "最佳收益后回吐明显",
    hold_extension_state: "risk_off",
    hold_extension_text: "跌破止损，不适合延长持有",
    hold_extension_score: 20,
    hold_extension_reasons: ["买点触达"],
    hold_extension_risks: ["已触及止损"],
    suggested_holding_plan: "exit_review",
    entry_touched: true,
    stop_triggered: true,
    stop_triggered_date: "2026-04-22",
    target_touched: true,
    target_touched_date: "2026-04-21",
    invalidated_date: null,
    conclusion: "已跌破止损",
    failure_reason: "跌破止损",
    failure_tags: ["stop_loss_triggered", "spike_without_take_profit"],
    failure_reason_text: "跌破止损；冲高未止盈",
    market_state: "strong_market",
    market_state_text: "强势行情",
    sector_state: "sector_main_rise",
    sector_state_text: "板块主升",
    signal_generated_at: "2026-04-20T14:50:00+08:00",
    data_cutoff_at: "2026-04-20T14:45:00+08:00",
    lookback_start_date: "2026-03-20",
    lookback_end_date: "2026-04-20",
    posterior_start_date: "2026-04-21",
    posterior_end_date: "2026-04-22",
    market_data_source: "unit-test",
    market_data_updated_at: "2026-04-20T15:30:00",
    future_leak_check: "needs_review",
    audit_flags: ["excessive_drawdown"],
    abnormal_return: false,
    needs_review: true,
    review_priority: "normal",
    review_text: "缩量回踩到支撑位；信号后跌破止损，需复盘失败原因。",
    data_quality: "ok",
    data_quality_text: "数据完整",
    source: "low_buy_result_snapshot",
    detail_available: true,
    board_type: "main",
    board_type_text: "主板",
    industry_sectors: ["银行"],
    concept_sectors: ["金融科技", "中特估"],
    display_sectors: ["金融科技", "银行", "主板"],
    user_friendly_status: "weakening",
    user_friendly_status_text: "已经走弱",
    user_friendly_reason: "已经跌破风险线，优先复盘失败原因。",
    plain_language_summary: "信号后最高涨过 +10.00%，最多跌过 -16.19%，现在涨跌 -12.00%，已经跌破风险线。",
    sector_detail: { board_type_text: "主板" },
  };
}

function detailFixture(): StrategyTrackingDetailResponse {
  return {
    item: itemFixture(),
    timeline: [
      {
        trade_date: "2026-04-21",
        open: 10,
        high: 11,
        low: 9.6,
        close: 10.5,
        pct_chg: 5,
        current_return_pct: 5,
        max_return_pct: 10,
        max_drawdown_pct: 0,
        holding_day: 1,
        is_best_exit: true,
        hold_extension_state: "unavailable",
        hit_entry_zone: true,
        hit_stop_loss: false,
        hit_target: true,
        lifecycle_status: "stopped",
        data_quality: "ok",
      },
    ],
    markers: [{ kind: "first_signal", trade_date: "2026-04-20", price: 10, label: "首次信号" }],
    signal_snapshot: { summary_reason: "缩量回踩到支撑位" },
    decision_context: {
      status: "ok",
      context_snapshot_id: 1,
      symbol: "600000",
      strategy_key: "first_board",
      trade_date: "2026-04-20",
      strategy_tier: "core",
      production_eligible: true,
      production_score: 82.5,
      final_decision: "front_row",
      final_score: 82.5,
      data_quality: "ok",
      gates: {
        market_gate: { decision: "allow", score: 90, reasons: ["市场修复"] },
        sector_leader_gate: { decision: "reduce", score: 62, reasons: ["板块扩散不足"] },
        hard_risk_gate: { decision: "allow", score: 100, reasons: [] },
        event_risk_gate: { decision: "no_data", score: 0, reasons: ["事件源缺失"] },
        intraday_entry_gate: { decision: "no_data", score: 0, reasons: ["分钟数据缺失"] },
      },
      gate_contributions: [
        { gate: "market_gate", decision: "allow", score: 90, effect: "positive", reasons: ["市场修复"] },
        { gate: "event_risk_gate", decision: "no_data", score: 0, effect: "blocked", reasons: ["事件源缺失"] },
      ],
      outcomes: [
        { horizon_days: 1, return_pct: 5, max_gain_pct: 10, max_drawdown_pct: -4, hit: true, exit_reason: "horizon_1d_close" },
      ],
      similar_history_sample_count: 12,
      reasons: [],
    },
    review_text: "缩量回踩到支撑位；信号后跌破止损，需复盘失败原因。",
    partial_errors: [],
    production_writeable: false,
  };
}


function holdingFixture(): StrategyTrackingHoldingAnalysis {
  return {
    strategy_key: "first_board",
    strategy_name: "首板回调",
    strategy_family: "core",
    sample_count: 24,
    avg_best_holding_days: 2.4,
    median_best_holding_days: 2,
    dominant_holding_bucket: "short_1_3d",
    dominant_holding_bucket_text: "短线 1-3 天",
    short_hold_ratio: 66.7,
    swing_hold_ratio: 20.8,
    trend_hold_ratio: 8.3,
    midlong_hold_ratio: 4.2,
    avg_best_exit_return_pct: 6.8,
    avg_best_exit_drawdown_pct: -2.1,
    avg_giveback_from_peak_pct: 18.5,
    extension_qualified_ratio: 16.7,
    conclusion: "首板回调更适合短线 1-3 天，多数样本在 3 天内冲高。",
  };
}

function baseStoreState() {
  return {
    tab: "active" as const,
    viewMode: "beginner" as const,
    range: 30,
    strategyKey: "",
    strategyVariant: "" as const,
    strategyFamily: "",
    signalState: "",
    lifecycleStatus: "",
    dataQuality: "",
    hitEntry: "",
    stopped: "",
    userStatus: "",
    excludeChinext: true,
    excludeStar: true,
    boardFilter: "include_all" as const,
    sort: "max_gain_desc",
    page: 1,
    pageSize: 30,
    selectedItemId: null,
    setTab: vi.fn(),
    setViewMode: vi.fn(),
    setRange: vi.fn(),
    setStrategyKey: vi.fn(),
    setStrategyVariant: vi.fn(),
    setStrategyFamily: vi.fn(),
    setSignalState: vi.fn(),
    setLifecycleStatus: vi.fn(),
    setDataQuality: vi.fn(),
    setHitEntry: vi.fn(),
    setStopped: vi.fn(),
    setUserStatus: vi.fn(),
    setExcludeChinext: vi.fn(),
    setExcludeStar: vi.fn(),
    setBoardFilter: vi.fn(),
    setSort: vi.fn(),
    setPagination: vi.fn(),
    setSelectedItemId: vi.fn(),
  };
}

function performanceFixture(): StrategyTrackingPerformance {
  return {
    strategy_key: "first_board",
    strategy_name: "首板回调",
    strategy_family: "core",
    recommendation_count: 3,
    entry_touched_count: 2,
    entry_touch_rate: 66.67,
    win_rate_3d: 50,
    win_rate_5d: 50,
    win_rate_10d: 0,
    avg_current_return_pct: 2,
    avg_max_gain_pct: 5,
    avg_max_drawdown_pct: -3,
    profit_loss_ratio: 1.4,
    stop_loss_rate: 33.33,
    active_count: 1,
    health_score: 70,
    health_grade: "B",
    sample_quality: "thin",
    health_reasons: ["买点触达率稳定"],
    health_risks: ["止损率偏高"],
  };
}
