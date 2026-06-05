import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { PaperConclusionBar } from "./PaperConclusionBar";

describe("PaperConclusionBar", () => {
  it("renders compact account asset metrics with an unlabeled pixel panel", () => {
    const html = renderToStaticMarkup(
      <PaperConclusionBar
        account={{
          id: 1,
          name: "测试账户",
          initial_cash: 100000,
          cash_available: 50000,
          frozen_cash: 0,
          market_value: 51230,
          total_assets: 101230,
          realized_pnl: 0,
          unrealized_pnl: 1230,
          total_return_pct: 1.23,
          today_pnl: 880,
          max_drawdown_pct: 0,
          status: "active",
          today_return_pct: 0.88,
        }}
        autoTradingStatus={{ running: true, last_cycle_at: "2026-06-01T10:00:00+08:00" }}
        loading={false}
        pixel={<div className="pixel-fixture">角色</div>}
        onTogglePause={vi.fn()}
      />
    );

    expect(html).toContain("paper-conclusion--with-pixel");
    expect(html).toContain("paper-conclusion__metrics");
    expect(html).toContain("paper-conclusion__pixel-panel");
    expect(html).toContain("总资产");
    expect(html).toContain("101,230.00");
    expect(html).toContain("浮动盈亏");
    expect(html).toContain("+1,230.00");
    expect(html).toContain("当日盈亏");
    expect(html).toContain("+880.00");
    expect(html).toContain("总市值");
    expect(html).toContain("51,230.00");
    expect(html).not.toContain("真实收益（总收益率）");
    expect(html).not.toContain("仓位与风控");
    expect(html).not.toContain("自动状态");
    expect(html).not.toContain("信号收益");
    expect(html).not.toContain("真实收益、影子收益和信号收益分区展示");
    expect(html).not.toContain("自动交易只在模拟盘口径内执行");
    expect(html).not.toContain("tq-conclusion-bar__helper");
    expect(html).not.toContain("像素图");
    expect(html).not.toContain("最近刷新");
    expect(html).not.toContain("总交易");
  });

  it("renders a first-screen review history action when available", () => {
    const html = renderToStaticMarkup(
      <PaperConclusionBar
        account={null}
        autoTradingStatus={{ running: false }}
        loading={false}
        reviewReportCount={2}
        onOpenReviewHistory={vi.fn()}
      />
    );

    expect(html).toContain("复盘历史 · 2 条");
  });

  it("keeps the review history action visible when there are no reports", () => {
    const html = renderToStaticMarkup(
      <PaperConclusionBar
        account={null}
        autoTradingStatus={{ running: false }}
        loading={false}
        reviewReportCount={0}
        onOpenReviewHistory={vi.fn()}
      />
    );

    expect(html).toContain("复盘历史");
    expect(html).not.toContain("复盘历史 · 0 条");
  });
});
