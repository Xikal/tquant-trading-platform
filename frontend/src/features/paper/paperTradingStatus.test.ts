import { describe, expect, it } from "vitest";
import { buildPaperTradingPageStatus } from "./paperTradingStatus";

describe("buildPaperTradingPageStatus", () => {
  it("derives pause, loading, and automation flags for the paper page", () => {
    const status = buildPaperTradingPageStatus({
      account: { status: "paused" } as any,
      autoTradingStatus: { running: true },
      trades: [],
      loading: "paper-order",
      tradingExperienceFlags: {
        trading_experience_suite_enabled: true,
        holding_discipline_assistant_enabled: true,
        t_trade_discipline_enabled: false,
      },
    });

    expect(status.needsResumeOrder).toBe(true);
    expect(status.paused).toBe(true);
    expect(status.orderLoading).toBe(true);
    expect(status.paperLoading).toBe(false);
    expect(status.autoTradingRunning).toBe(true);
    expect(status.holdingEnabled).toBe(true);
    expect(status.tTradeEnabled).toBe(false);
  });

  it("builds a finite last order action from the latest trade", () => {
    const status = buildPaperTradingPageStatus({
      account: null,
      autoTradingStatus: null,
      trades: [{ side: "sell", symbol: "600000", trade_time: "2026-06-05T10:00:00+08:00" } as any],
      loading: "",
    });

    expect(status.lastOrderAction).toEqual({
      type: "sell",
      symbol: "600000",
      timestamp: Date.parse("2026-06-05T10:00:00+08:00"),
    });
  });

  it("drops invalid last order timestamps", () => {
    const status = buildPaperTradingPageStatus({
      account: null,
      autoTradingStatus: null,
      trades: [{ side: "buy", symbol: "600000", trade_time: "bad-date" } as any],
      loading: "",
    });

    expect(status.lastOrderAction).toBeNull();
  });
});
