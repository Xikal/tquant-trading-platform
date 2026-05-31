import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { LowBuyPriorityBoardResult } from "../../types";
import { MonitorPage } from "../monitor/MonitorPage";

describe("MonitorPage", () => {
  it("puts the direct action card before numeric metrics", () => {
    const html = renderToStaticMarkup(
      <MonitorPage
        priorityBoard={null}
        marketBreadth={null}
        marketPulse={null}
        hourlySnapshotHistory={[]}
        reviewStatus={null}
        reviewReports={[]}
        keyLevelAlerts={[]}
        sectorEtfT0={null}
        pairedHedge={null}
        priorityCards={[]}
        watchCards={[{
          name: "农业银行",
          symbol: "601288",
          priceText: "4.320",
          changeText: "+1.20%",
          riskText: "低风险",
          actionText: "正T",
          details: "接近支撑，等待承接确认。",
          executionHint: "冲高变弱先卖一部分。",
          tone: "up",
        }]}
        runtime={null}
        instrumentSyncStatus={null}
        watchDraft={{ symbol: "", name: "", base_position: "", available_position: "", cost_basis: "", memo: "" }}
        setWatchDraft={vi.fn()}
        editingWatchSymbol=""
        loading=""
        onRefresh={vi.fn()}
        onSync={vi.fn()}
        onAi={vi.fn()}
        onGoPlaybook={vi.fn()}
        onSelect={vi.fn()}
        onAnalyze={vi.fn()}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
        onAddWatchlist={vi.fn()}
        onCancelEdit={vi.fn()}
      />
    );

    expect(html).toContain("今天最重要的 1 件事");
    expect(html).toContain("今日红运");
    expect(html).toContain("农业银行");
    expect(html).toContain("盘面细节、小时快照与维护状态");
  });

  it("renders independent low-buy strategy lanes with plain status copy", () => {
    const html = renderToStaticMarkup(
      <MonitorPage
        priorityBoard={priorityBoardFixture()}
        marketBreadth={null}
        marketPulse={null}
        hourlySnapshotHistory={[]}
        reviewStatus={null}
        reviewReports={[]}
        keyLevelAlerts={[]}
        sectorEtfT0={null}
        pairedHedge={null}
        priorityCards={[]}
        watchCards={[]}
        runtime={null}
        instrumentSyncStatus={null}
        watchDraft={{ symbol: "", name: "", base_position: "", available_position: "", cost_basis: "", memo: "" }}
        setWatchDraft={vi.fn()}
        editingWatchSymbol=""
        loading=""
        onRefresh={vi.fn()}
        onSync={vi.fn()}
        onAi={vi.fn()}
        onGoPlaybook={vi.fn()}
        onLaneChange={vi.fn()}
        onSelect={vi.fn()}
        onAnalyze={vi.fn()}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
        onAddWatchlist={vi.fn()}
        onCancelEdit={vi.fn()}
      />
    );

    expect(html).toContain("原低吸策略");
    expect(html).toContain("前排加权");
    expect(html).toContain("前排极精选");
    expect(html).toContain("只做验证，暂不影响真实排序");
    expect(html).toContain("今日无生产可推荐票");
    expect(html).toContain("研究观察池只做提醒");
  });

  it("renders hourly all-market snapshot feedback", () => {
    const html = renderToStaticMarkup(
      <MonitorPage
        priorityBoard={null}
        marketBreadth={{
          updated_at: "2026-05-25 10:30:00",
          state: "neutral",
          state_text: "震荡",
          breadth_ready: true,
          emotion_ready: true,
          stock_up_ratio: 0.56,
          stock_median_change: 0.3,
          largecap_change: 0,
          smallcap_change: 0,
          style_divergence: 0,
          limit_up_count: 42,
          limit_down_count: 3,
          broken_board_ratio: 0.12,
          promotion_ratio: 0.2,
          board_height: 4,
          hot_industries: ["AI"],
          hot_turnover: 0.1,
          hot_overlap_ratio: 0.4,
          data_quality: "fresh",
          data_quality_text: "可用",
          hourly_all_market_snapshot: {
            updated_at: "2026-05-25 10:30:00",
            snapshot_count: 5200,
            stock_up_ratio: 0.56,
            stock_down_ratio: 0.32,
            stock_median_change: 0.3,
            strong_count: 210,
            weak_count: 80,
            market_strength_score: 18,
            market_strength_text: "全市场温和修复",
          },
        }}
        marketPulse={null}
        hourlySnapshotHistory={[]}
        reviewStatus={null}
        reviewReports={[]}
        keyLevelAlerts={[]}
        sectorEtfT0={null}
        pairedHedge={null}
        priorityCards={[]}
        watchCards={[]}
        runtime={null}
        instrumentSyncStatus={null}
        watchDraft={{ symbol: "", name: "", base_position: "", available_position: "", cost_basis: "", memo: "" }}
        setWatchDraft={vi.fn()}
        editingWatchSymbol=""
        loading=""
        onRefresh={vi.fn()}
        onSync={vi.fn()}
        onAi={vi.fn()}
        onGoPlaybook={vi.fn()}
        onSelect={vi.fn()}
        onAnalyze={vi.fn()}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
        onAddWatchlist={vi.fn()}
        onCancelEdit={vi.fn()}
      />
    );

    expect(html).toContain("盘面细节、小时快照与维护状态");
    expect(html).toContain("今日复盘、Pulse 和风险动作");
  });

  it("renders hourly trend and weakening warning", () => {
    const html = renderToStaticMarkup(
      <MonitorPage
        priorityBoard={null}
        marketBreadth={null}
        hourlySnapshotHistory={[
          {
            id: 1,
            trade_date: "2026-05-25",
            snapshot_bucket: "202605251030",
            data_quality: "fresh",
            snapshot_count: 5200,
            market_strength_score: 18,
            payload: { market_strength_text: "强" },
            created_at: "",
            updated_at: "2026-05-25 10:30:00",
          },
          {
            id: 2,
            trade_date: "2026-05-25",
            snapshot_bucket: "202605251130",
            data_quality: "fresh",
            snapshot_count: 5200,
            market_strength_score: 8,
            payload: { market_strength_text: "降温" },
            created_at: "",
            updated_at: "2026-05-25 11:30:00",
          },
          {
            id: 3,
            trade_date: "2026-05-25",
            snapshot_bucket: "202605251400",
            data_quality: "partial",
            snapshot_count: 5200,
            market_strength_score: -3,
            payload: { market_strength_text: "走弱" },
            created_at: "",
            updated_at: "2026-05-25 14:00:00",
          },
        ]}
        marketPulse={null}
        reviewStatus={null}
        reviewReports={[]}
        keyLevelAlerts={[]}
        sectorEtfT0={null}
        pairedHedge={null}
        priorityCards={[]}
        watchCards={[]}
        runtime={null}
        instrumentSyncStatus={null}
        watchDraft={{ symbol: "", name: "", base_position: "", available_position: "", cost_basis: "", memo: "" }}
        setWatchDraft={vi.fn()}
        editingWatchSymbol=""
        loading=""
        onRefresh={vi.fn()}
        onSync={vi.fn()}
        onAi={vi.fn()}
        onGoPlaybook={vi.fn()}
        onSelect={vi.fn()}
        onAnalyze={vi.fn()}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
        onAddWatchlist={vi.fn()}
        onCancelEdit={vi.fn()}
      />
    );

    expect(html).toContain("盘面细节、小时快照与维护状态");
    expect(html).toContain("等待触发");
  });

  it("renders intraday pulse and review status on monitor first screen", () => {
    const html = renderToStaticMarkup(
      <MonitorPage
        priorityBoard={null}
        marketBreadth={null}
        hourlySnapshotHistory={[]}
        marketPulse={{
          updated_at: "2026-05-25 10:30:00",
          data_quality: "partial",
          data_quality_text: "部分可用",
          market_strength_text: "市场宽度修复",
          emotion_text: "情绪温度升温",
          hourly_snapshot_text: "小时快照温和修复",
          pulse_level: "balanced",
          pulse_text: "盘中结构转为可观察。",
          suggested_action: "只做已入池候选，控制追高。",
          partial_errors: [{ source: "paired_hedge", detail: "暂不可用" }],
          market_breadth_summary: {},
          emotion_summary: {},
          hourly_snapshot_summary: {},
          autofill_details: [{ source: "emotion_temperature", detail: "情绪温度由市场涨跌面派生" }],
        }}
        reviewStatus={{
          trade_date: "2026-05-25",
          status: "midday_ready",
          status_text: "今日市场午盘复盘已生成，等待收盘复盘",
          review_subject: "全市场",
          source_scope: "market",
          has_midday: true,
          has_close: false,
          next_trigger_at: "2026-05-25 15:05",
          risk_alert_count: 1,
          suggested_action: "午后控制追高",
        }}
        reviewReports={[{
          id: 1,
          report_date: "2026-05-25",
          report_slot: "midday",
          review_subject: "全市场",
          source_scope: "market",
          overall_summary: "午盘市场宽度稳定",
          strategy_highlights: [],
          risk_alerts: [{ level: "warning", content: "单票仓位偏高" }],
          suggestion: "午后控制追高",
          generated_at: "2026-05-25 11:35:00",
          llm_model: "",
          missing_data: [{ source: "sector_relative_strength", name: "板块/龙头强度" }],
          autofill_details: [{ source: "emotion_temperature", detail: "情绪温度由市场涨跌面派生" }],
        }]}
        keyLevelAlerts={[]}
        sectorEtfT0={null}
        pairedHedge={null}
        priorityCards={[]}
        watchCards={[]}
        runtime={null}
        instrumentSyncStatus={null}
        watchDraft={{ symbol: "", name: "", base_position: "", available_position: "", cost_basis: "", memo: "" }}
        setWatchDraft={vi.fn()}
        editingWatchSymbol=""
        loading=""
        onRefresh={vi.fn()}
        onSync={vi.fn()}
        onAi={vi.fn()}
        onGoPlaybook={vi.fn()}
        onSelect={vi.fn()}
        onAnalyze={vi.fn()}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
        onAddWatchlist={vi.fn()}
        onCancelEdit={vi.fn()}
      />
    );

    expect(html).toContain("盘中 Pulse");
    expect(html).toContain("盘中结构转为可观察");
    expect(html).toContain("今日全市场午盘 / 收盘复盘");
    expect(html).toContain("今日市场午盘复盘已生成");
    expect(html).toContain("午后控制追高");
    expect(html).toContain("明细");
    expect(html).toContain("自动补全明细");
    expect(html).toContain("今日红运");
  });

  it("renders ETF T0 intraday signal details on monitor page", () => {
    const html = renderToStaticMarkup(
      <MonitorPage
        priorityBoard={null}
        marketBreadth={null}
        marketPulse={null}
        hourlySnapshotHistory={[]}
        reviewStatus={null}
        reviewReports={[]}
        keyLevelAlerts={[]}
        sectorEtfT0={{
          updated_at: "2026-05-27 10:30:00",
          market_state: "repair",
          market_state_text: "震荡修复",
          total: 1,
          notes: ["只在价差覆盖成本时执行。"],
          opportunities: [{
            sector_name: "半导体",
            etf_symbol: "512480",
            etf_name: "半导体ETF",
            etf_category: "sector",
            t0_eligible: true,
            settlement_rule: "t0",
            min_amount: 50000000,
            source_signal_symbol: "000001",
            source_signal_name: "测试股票",
            source_strategy: "低吸",
            source_signal_text: "回踩确认",
            last_price: 1.234,
            change_pct: 0.56,
            bias: "positive_t",
            bias_text: "ETF 正T候选",
            confidence: 72,
            entry_zone: "1.230-1.240",
            sell_zone: "1.250-1.260",
            expected_edge_pct: 0.9,
            intraday_signal_action: "positive_t_buy",
            intraday_signal_text: "ETF 正T买入候选",
            intraday_signal_confidence: 78,
            intraday_signal_snapshot: {
              current_price: 1.234,
              vwap: 1.245,
              rsi: 32.4,
              expected_edge_pct: 0.44,
            },
            intraday_risk_flags: [],
            reason: "测试股票 属于该方向强信号。",
            risk: "执行前检查价差和数据 freshness。",
          }],
        }}
        pairedHedge={null}
        priorityCards={[]}
        watchCards={[]}
        runtime={null}
        instrumentSyncStatus={null}
        watchDraft={{ symbol: "", name: "", base_position: "", available_position: "", cost_basis: "", memo: "" }}
        setWatchDraft={vi.fn()}
        editingWatchSymbol=""
        loading=""
        onRefresh={vi.fn()}
        onSync={vi.fn()}
        onAi={vi.fn()}
        onGoPlaybook={vi.fn()}
        onSelect={vi.fn()}
        onAnalyze={vi.fn()}
        onEdit={vi.fn()}
        onRemove={vi.fn()}
        onAddWatchlist={vi.fn()}
        onCancelEdit={vi.fn()}
      />
    );

    expect(html).toContain("ETF 正T买入候选");
    expect(html).toContain("分钟信心");
    expect(html).toContain("VWAP");
    expect(html).toContain("净边际");
  });
});

function priorityBoardFixture(): LowBuyPriorityBoardResult {
  return {
    strategy_variant: "front_row_weighted",
    display_lane: "front_row_weighted",
    display_lane_title: "前排加权",
    display_lane_subtitle: "只做验证，暂不影响真实排序",
    production_sort_replaced: false,
    readiness_summary: {
      plain_status: {
        conclusion: "只做验证，暂不影响真实排序",
        reason: "样本外验证不足、滚动验证不稳定、成交数据不足",
        next_step: "继续影子验证和模拟盘观察",
      },
      blockers: ["oos_window_below_60_trade_days"],
    },
    as_of_date: "2026-05-30",
    latest_trade_date: "2026-05-29",
    updated_at: "2026-05-30 10:00:00",
    total_candidates: 0,
    immediate_count: 0,
    focus_count: 0,
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
    items: [],
  };
}
