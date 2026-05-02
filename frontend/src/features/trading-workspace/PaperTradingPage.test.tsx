import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { PaperTradingPage } from "./PaperTradingPage";

describe("PaperTradingPage", () => {
  it("renders paper trading panels and intraday confirmation switch", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={null}
        positions={[]}
        orders={[]}
        trades={[]}
        performance={null}
        strategyPerformance={[]}
        marketPerformance={[]}
        riskEvents={[]}
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
        onRefresh={vi.fn()}
        onRefreshQuotes={vi.fn()}
        onSubmitOrder={vi.fn()}
        onTogglePause={vi.fn()}
      />
    );

    expect(html).toContain("模拟交易");
    expect(html).toContain("录入模拟委托");
    expect(html).toContain("买入前必须承接确认");
    expect(html).toContain("市场状态绩效");
  });
});
