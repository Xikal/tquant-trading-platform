import { describe, expect, it } from "vitest";
import { chartPoints, defaultAnalysisForm, paperOrderDraftSearch, type AnalysisSnapshot } from "./analysisModel";

describe("analysis model chart data", () => {
  it("uses backend kline bars when available", () => {
    const snapshot = {
      response: {} as AnalysisSnapshot["response"],
      supplement: {
        kline: {
          bars: [
            { timestamp: "2026-06-01", open: 8, high: 8.2, low: 7.9, close: 8.12 },
            { timestamp: "2026-06-02", open: 8.12, high: 8.36, low: 8.05, close: 8.3 },
          ],
        },
        errors: [],
      },
    };

    expect(chartPoints(snapshot)).toEqual([
      { time: "2026-06-01", open: 8, high: 8.2, low: 7.9, close: 8.12 },
      { time: "2026-06-02", open: 8.12, high: 8.36, low: 8.05, close: 8.3 },
    ]);
  });

  it("falls back to close-derived candles only when the backend lacks OHLC fields", () => {
    const snapshot = {
      response: {} as AnalysisSnapshot["response"],
      supplement: {
        kline: { bars: [{ timestamp: "2026-06-03", close: 8.18 }] },
        errors: [],
      },
    };

    expect(chartPoints(snapshot)).toEqual([
      { time: "2026-06-03", open: 8.18, high: 8.18, low: 8.18, close: 8.18 },
    ]);
  });

  it("does not fabricate chart points when no backend bars are present", () => {
    const snapshot = {
      response: {} as AnalysisSnapshot["response"],
      supplement: { errors: [] },
    };

    expect(chartPoints(snapshot)).toEqual([]);
    expect(chartPoints(null)).toEqual([]);
  });

  it("builds a paper order draft from the analyzed result without inventing strategy fields", () => {
    const snapshot = {
      response: {
        symbol: "600000",
        instrument: { name: "浦发银行" },
        quote: { last_price: 8.72 },
        suggestion: {
          side: "buy",
          order_type: "limit",
          strategy_key: "n_pattern_long_wash",
          plain_action_reason: "接近支撑位",
        },
      } as unknown as AnalysisSnapshot["response"],
      supplement: { errors: [] },
    };

    expect(paperOrderDraftSearch(snapshot, { ...defaultAnalysisForm, symbol: "600000", availablePosition: 950 })).toEqual({
      source: "analysis",
      symbol: "600000",
      name: "浦发银行",
      side: "buy",
      order_type: "limit",
      quantity: "900",
      price: "8.72",
      strategy_key: "n_pattern_long_wash",
      reason: "接近支撑位",
    });
  });
});
