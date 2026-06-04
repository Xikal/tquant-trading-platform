import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { PaperTradingSummaryBar } from "./PaperTradingSummaryBar";

describe("PaperTradingSummaryBar", () => {
  it("uses flat metric tiles instead of nested AntD cards", () => {
    const html = renderToStaticMarkup(
      <PaperTradingSummaryBar
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
          today_return_pct: 1.23,
        }}
        performance={{
          total_return_pct: 1.23,
          max_drawdown_pct: 0,
          win_rate_pct: 0,
          net_win_rate_pct: 50,
          avg_trade_return_pct: 0,
          avg_win_pct: 0,
          avg_loss_pct: 0,
          profit_factor: null,
          stop_loss_rate_pct: 0,
          total_trades: 0,
          avg_hold_days: 0,
          win_loss_ratio: null,
        }}
        autoTradingStatus={{ running: false, trading_time: true }}
        loading={false}
        canOpenOrder
        onOpenOrderEntry={vi.fn()}
      />
    );

    expect(html).toContain("paper-summary-metric");
    expect(html.match(/paper-summary-metric/g)?.length).toBe(6);
    expect(html.match(/ant-card-body/g)?.length).toBe(1);
    expect(html).not.toContain("ant-card-small");
  });
});
