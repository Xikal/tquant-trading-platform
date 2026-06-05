import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useStrategyTrackingStore } from "../../stores/strategyTrackingStore";
import type { ReviewWorkspaceResponse } from "../../types";
import { ReviewWorkspaceDetail } from "./ReviewWorkspaceDetail";
import { StrategyReviewWorkspacePanel } from "./StrategyReviewWorkspacePanel";

describe("StrategyReviewWorkspacePanel", () => {
  afterEach(() => {
    useStrategyTrackingStore.getState().setReviewWorkspaceSelectedKey(null);
  });

  it("renders review queue, journal action, and relative strength facts as one workflow", () => {
    const html = renderToStaticMarkup(
      <StrategyReviewWorkspacePanel
        data={reviewWorkspaceFixture()}
        loading={false}
        boardFilter="include_all"
        onBoardFilterChange={vi.fn()}
        onCreateJournal={vi.fn()}
        creatingJournal={false}
      />,
    );

    expect(html).toContain("复盘中心");
    expect(html).toContain("今日复盘池已生成");
    expect(html).toContain("待复盘");
    expect(html).toContain("缺日志");
    expect(html).toContain("完成率");
    expect(html).toContain("7日纪律");
    expect(html).toContain("浦发银行");
    expect(html).toContain("写复盘");
    expect(html).toContain("抗跌事实");
    expect(html).toContain("相对市场");
    expect(html).toContain("相对板块");
    expect(html).toContain("仅用于观察和复盘");
    expect(html).toContain("不预测后续涨跌");
    expect(html).toContain("保存记录");
  });

  it("renders disabled state without review actions", () => {
    const html = renderToStaticMarkup(
      <StrategyReviewWorkspacePanel
        data={reviewWorkspaceFixture({
          enabled: false,
          review_enabled: false,
          relative_strength_enabled: false,
          data_quality: "blocked",
          source: "feature_flag",
          items: [],
          total: 0,
          reminder: {
            status: "blocked",
            message: "复盘中心未开启",
            refresh_queued: false,
            data_quality: "blocked",
          },
          summary: {
            pending_review_count: 0,
            retained_count: 0,
            dropped_count: 0,
            missing_journal_count: 0,
            journal_count: 0,
            relative_strength_count: 0,
            completion_rate_pct: 0,
            seven_day_discipline_pass_rate_pct: null,
            seven_day_journal_count: 0,
            market_context: "unknown",
          },
        })}
        loading={false}
        boardFilter="include_all"
        onBoardFilterChange={vi.fn()}
        onCreateJournal={vi.fn()}
        creatingJournal={false}
      />,
    );

    expect(html).toContain("复盘中心未开启");
    expect(html).not.toContain("写复盘");
  });

  it("shows source timings only in professional mode", () => {
    const html = renderToStaticMarkup(
      <StrategyReviewWorkspacePanel
        data={reviewWorkspaceFixture({ elapsed_ms: 123, cache_status: "fresh" })}
        loading={false}
        boardFilter="include_all"
        onBoardFilterChange={vi.fn()}
        onCreateJournal={vi.fn()}
        creatingJournal={false}
        professional
      />,
    );

    expect(html).toContain("总耗时 123ms");
    expect(html).toContain("缓存 命中");
    expect(html).toContain("复盘池");
    expect(html).toContain("纪律日志");
    expect(html).toContain("抗跌事实");
  });

  it("prefills the journal form from the selected queue item", () => {
    const fixture = reviewWorkspaceFixture();
    const baseItem = (fixture.items ?? [])[0];
    if (!baseItem) throw new Error("review workspace fixture item missing");
    const item = {
      ...baseItem,
      review_key: "2026-05-24:000001",
      pool_item: {
        ...baseItem.pool_item,
        symbol: "000001",
        name: "平安银行",
        evidence: ["第二条复盘证据"],
      },
    };

    const html = renderToStaticMarkup(
      <ReviewWorkspaceDetail
        item={item}
        creatingJournal={false}
        onCreateJournal={vi.fn()}
      />,
    );

    expect(html).toContain("value=\"000001\"");
    expect(html).toContain("第二条复盘证据");
    expect(html).not.toContain("value=\"600000\"");
  });
});

function reviewWorkspaceFixture(overrides: Partial<ReviewWorkspaceResponse> = {}): ReviewWorkspaceResponse {
  return {
    enabled: true,
    review_enabled: true,
    relative_strength_enabled: true,
    pool_date: "2026-05-24",
    board_filter: "include_all",
    summary: {
      pending_review_count: 1,
      retained_count: 1,
      dropped_count: 0,
      missing_journal_count: 1,
      journal_count: 0,
      relative_strength_count: 1,
      completion_rate_pct: 0,
      seven_day_discipline_pass_rate_pct: 75,
      seven_day_journal_count: 4,
      market_context: "market_down_day",
    },
    reminder: {
      status: "ready",
      message: "今日复盘池已生成，待补纪律日志 1 条",
      pool_date: "2026-05-24",
      refresh_queued: false,
      last_success_at: "2026-05-24T15:35:00+08:00",
      data_quality: "ok",
    },
    sources: [
      { source: "review_pool", status: "ok", elapsed_ms: 24, item_count: 1, reason: "" },
      { source: "trade_journal", status: "ok", elapsed_ms: 12, item_count: 0, reason: "" },
      { source: "relative_strength", status: "ok", elapsed_ms: 18, item_count: 1, reason: "" },
    ],
    cache_status: "fresh",
    elapsed_ms: 62,
    items: [
      {
        review_key: "2026-05-24:600000",
        review_status: "pending",
        next_action_label: "写复盘",
        pool_item: {
          pool_date: "2026-05-24",
          symbol: "600000",
          name: "浦发银行",
          board_type: "main",
          board_name: "主板",
          status: "retained",
          entry_pct: 8.2,
          volume_ratio: 1.4,
          mainline_state: "sector_known",
          sector_role: "银行",
          drop_reason: "",
          tracked_days: 3,
          evidence: ["信号日涨幅 8.20%", "后续跟踪 3 日，仅用于复盘"],
          data_quality: "ok",
          as_of: "2026-05-24T15:30:00+08:00",
          engine_version: "test",
        },
        journal_entries: [],
        relative_strength: {
          symbol: "600000",
          trade_date: "2026-05-24",
          index_code: "000300",
          sector_code: "银行",
          stock_pct: 1.2,
          index_pct: -1.4,
          sector_pct: -0.5,
          rs_vs_index: 2.6,
          rs_vs_sector: 1.7,
          sector_rank: 1,
          resilience_flag: "resilient",
          data_quality: "ok",
          as_of: "2026-05-24T15:30:00+08:00",
        },
      },
    ],
    total: 1,
    data_quality: "ok",
    as_of: "2026-05-24T15:30:00+08:00",
    engine_version: "test",
    source: "review_workspace",
    research_only: true,
    ...overrides,
  };
}
