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
