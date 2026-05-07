import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { PaperTradingPage } from "./PaperTradingPage";

describe("PaperTradingPage", () => {
  it("renders paper trading panels and mecha order cockpit", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={null}
        positions={[]}
        orders={[]}
        trades={[]}
        performance={null}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{ running: false }}
        autoTradingRuns={[]}
        intradayConfirmations={[]}
        draft={{
          symbol: "",
          name: "",
          side: "buy",
          order_type: "market",
          quantity: "100",
          price: "",
          current_price: "",
          strategy_key: "",
          reason: "",
          require_intraday_confirmation: false,
        }}
        setDraft={vi.fn()}
        loading=""
        onSubmitOrder={vi.fn()}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
      />
    );

    expect(html).not.toContain("模拟交易");
    expect(html).toContain("机甲指挥舱");
    expect(html).toContain("+委托");
    expect(html).toContain("市场状态绩效");
    expect(html).toContain("自动交易日志");
  });

  it("uses account-level total return for the top paper metric", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
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
        positions={[]}
        orders={[]}
        trades={[]}
        performance={{
          total_return_pct: -9.99,
          max_drawdown_pct: 0,
          win_rate_pct: 0,
          net_win_rate_pct: 0,
          avg_trade_return_pct: 0,
          avg_win_pct: 0,
          avg_loss_pct: 0,
          profit_factor: null,
          stop_loss_rate_pct: 0,
          total_trades: 0,
          avg_hold_days: 0,
          win_loss_ratio: null,
        }}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{ running: false }}
        autoTradingRuns={[]}
        intradayConfirmations={[]}
        draft={{
          symbol: "",
          name: "",
          side: "buy",
          order_type: "market",
          quantity: "100",
          price: "",
          current_price: "",
          strategy_key: "",
          reason: "",
          require_intraday_confirmation: false,
        }}
        setDraft={vi.fn()}
        loading=""
        onSubmitOrder={vi.fn()}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
      />
    );

    expect(html).toContain("总收益率");
    expect(html).toContain("+1.23%");
    expect(html).not.toContain("-9.99%");
  });

  it("locks manual order entry when auto trading is running", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={null}
        positions={[]}
        orders={[]}
        trades={[]}
        performance={null}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{ running: true }}
        autoTradingRuns={[]}
        intradayConfirmations={[]}
        draft={{
          symbol: "510300",
          name: "",
          side: "buy",
          order_type: "market",
          quantity: "100",
          price: "",
          current_price: "",
          strategy_key: "",
          reason: "",
          require_intraday_confirmation: false,
        }}
        setDraft={vi.fn()}
        loading=""
        onSubmitOrder={vi.fn()}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
      />
    );

    expect(html).toContain("超频");
    expect(html).toContain("disabled");
  });
});
