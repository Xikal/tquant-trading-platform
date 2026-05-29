import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { StrategyTrackingDetailResponse, StrategyTrackingItem, StrategyTrackingPerformance, StrategyTrackingSummary } from "../../types";
import { Topbar } from "../trading-workspace/Topbar";
import { StrategyTrackingDetailContent } from "./StrategyTrackingDetailDrawer";
import { StrategyTrackingPerformanceTable } from "./StrategyTrackingPerformanceTable";
import { StrategyTrackingReviewPanel } from "./StrategyTrackingReviewPanel";
import { StrategyTrackingSummaryBar } from "./StrategyTrackingSummaryBar";
import { StrategyTrackingTable } from "./StrategyTrackingTable";

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
        onOpenDetail={openDetail}
        onPageChange={onPageChange}
      />
    );

    expect(html).toContain("浦发银行");
    expect(html).toContain("首板回调");
    expect(html).toContain("买点触达");
    expect(html).toContain("止损");
  });

  it("renders detail drawer timeline without needing list payload_json", () => {
    const html = renderToStaticMarkup(
      <StrategyTrackingDetailContent detail={detailFixture()} />
    );

    expect(html).toContain("浦发银行");
    expect(html).toContain("首次推荐");
    expect(html).toContain("分钟K线");
    expect(html).toContain("2026-04-21");
    expect(html).toContain("止损");
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

    expect(html).toContain("推荐次数");
    expect(html).toContain("买点触达率");
    expect(html).toContain("首板回调");
  });
});

function summaryFixture(overrides: Partial<StrategyTrackingSummary> = {}): StrategyTrackingSummary {
  return {
    tracking_count: 3,
    active_count: 1,
    today_new_count: 1,
    in_entry_zone_count: 1,
    stopped_count: 1,
    avg_current_return_pct: 2.3,
    median_max_gain_pct: 5.6,
    data_quality: "ok",
    data_quality_text: "数据完整",
    generated_at: "2026-05-29T10:00:00+00:00",
    ...overrides,
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
    signal_text: "可买入",
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
    entry_touched: true,
    stop_triggered: true,
    stop_triggered_date: "2026-04-22",
    target_touched: true,
    target_touched_date: "2026-04-21",
    conclusion: "已跌破止损",
    failure_reason: "跌破止损",
    review_text: "缩量回踩到支撑位；推荐后跌破止损，需复盘失败原因。",
    data_quality: "ok",
    data_quality_text: "数据完整",
    source: "low_buy_result_snapshot",
    detail_available: true,
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
        hit_entry_zone: true,
        hit_stop_loss: false,
        hit_target: true,
        lifecycle_status: "stopped",
        data_quality: "ok",
      },
    ],
    markers: [{ kind: "first_signal", trade_date: "2026-04-20", price: 10, label: "首次推荐" }],
    signal_snapshot: { summary_reason: "缩量回踩到支撑位" },
    review_text: "缩量回踩到支撑位；推荐后跌破止损，需复盘失败原因。",
    partial_errors: [],
    production_writeable: false,
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
  };
}
