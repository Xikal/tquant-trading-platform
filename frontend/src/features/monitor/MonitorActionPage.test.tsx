import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { createAppQueryClient } from "../../state/queryClient";
import { MonitorActionPage } from "./MonitorActionPage";
import { baseMonitorPageProps } from "./monitorTestFixtures";

function renderPage(element: ReactElement) {
  return renderToStaticMarkup(
    <QueryClientProvider client={createAppQueryClient()}>
      {element}
    </QueryClientProvider>,
  );
}

describe("MonitorActionPage", () => {
  it("renders action desk sections without the full market review surface", () => {
    const html = renderPage(<MonitorActionPage {...baseMonitorPageProps()} />);

    expect(html).toContain("tq-conclusion-bar");
    expect(html).toContain("生产优先榜");
    expect(html).toContain("我的持仓");
    expect(html).toContain("+ 录入持仓");
    expect(html).not.toContain("今日全市场午盘 / 收盘复盘");
    expect(html).not.toContain("ETF 做T替代");
    expect(html).not.toContain("小时全市场快照");
  });

  it("renders a stable empty-state message when the selected lane has no stocks", () => {
    const html = renderPage(
      <MonitorActionPage
        {...baseMonitorPageProps({
          priorityBoard: {
            strategy_variant: "front_row_only",
            display_lane: "front_row_only",
            display_lane_title: "前排极精选",
            display_lane_subtitle: "前排极精选只做提醒，不作为生产硬过滤。",
            as_of_date: "2026-06-05",
            latest_trade_date: "2026-06-05",
            latest_available_trade_date: "2026-06-05",
            updated_at: "2026-06-05 15:10:00",
            stale: false,
            refresh_queued: false,
            read_path: "priority_board_read_model",
            total_candidates: 0,
            immediate_count: 0,
            focus_count: 0,
            track_count: 0,
            market_state: "balanced",
            market_state_text: "平衡",
            data_quality: "ok",
            data_quality_text: "数据完整",
            market_bonus: 0,
            market_state_strength: 0,
            regime_confidence: 0,
            state_persistence_days: 0,
            transition_risk: 0,
            breadth_ready: true,
            emotion_ready: true,
            stock_up_ratio: 0,
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
            hot_industry_source: "snapshot",
            hot_industry_source_text: "快照",
            items: [],
          },
        })}
      />,
    );

    expect(html).toContain("今日前排极精选无票");
    expect(html).not.toContain("正在后台刷新");
  });

  it("surfaces stale priority board snapshots as review-only", () => {
    const html = renderPage(
      <MonitorActionPage
        {...baseMonitorPageProps({
          priorityBoard: {
            strategy_variant: "baseline",
            display_lane: "baseline",
            display_lane_title: "生产优先榜",
            as_of_date: "2026-06-05",
            latest_trade_date: "2026-05-29",
            latest_available_trade_date: "2026-06-05",
            updated_at: "2026-05-29 15:10:00",
            stale: true,
            stale_reason: "当前榜单停留在 2026-05-29，距最新交易日 2026-06-05 已落后 5 个交易日，仅供复盘，不作为今日观察。",
            refresh_queued: false,
            read_path: "priority_board_read_model",
            total_candidates: 0,
            immediate_count: 0,
            focus_count: 0,
            track_count: 0,
            market_state: "balanced",
            market_state_text: "平衡",
            data_quality: "stale",
            data_quality_text: "行情可能延迟",
            market_bonus: 0,
            market_state_strength: 0,
            regime_confidence: 0,
            state_persistence_days: 0,
            transition_risk: 0,
            breadth_ready: true,
            emotion_ready: true,
            stock_up_ratio: 0,
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
            hot_industry_source: "snapshot",
            hot_industry_source_text: "快照",
            items: [],
          },
        })}
      />,
    );

    expect(html).toContain("优先榜快照已过期");
    expect(html).toContain("仅供复盘");
    expect(html).toContain("今日无票");
  });
});
