import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { PaperConclusionBar } from "./PaperConclusionBar";

describe("PaperConclusionBar", () => {
  it("renders compact two-column paper metrics with an unlabeled pixel panel", () => {
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
          max_drawdown_pct: 0,
          status: "active",
          today_return_pct: 0.88,
        }}
        performance={{
          total_return_pct: 1.23,
          max_drawdown_pct: 0,
          win_rate_pct: 0,
          net_win_rate_pct: 2.34,
          avg_trade_return_pct: 0,
          avg_win_pct: 0,
          avg_loss_pct: 0,
          profit_factor: null,
          stop_loss_rate_pct: 0,
          total_trades: 12,
          avg_hold_days: 0,
          win_loss_ratio: null,
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
    expect(html).toContain("真实收益（总收益率）");
    expect(html).toContain("仓位与风控");
    expect(html).toContain("自动状态");
    expect(html).toContain("信号收益");
    expect(html).not.toContain("tq-conclusion-bar__helper");
    expect(html).not.toContain("像素图");
    expect(html).not.toContain("总资产");
    expect(html).not.toContain("最近刷新");
    expect(html).not.toContain("总交易");
  });

  it("renders a first-screen review history action when available", () => {
    const html = renderToStaticMarkup(
      <PaperConclusionBar
        account={null}
        performance={null}
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
        performance={null}
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
