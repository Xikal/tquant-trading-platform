import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../../shared/api/client";
import {
  ANALYSIS_DAILY_KLINE_LIMIT,
  ANALYSIS_INTRADAY_KLINE_LIMIT,
  ANALYSIS_BATCH_REQUEST_TIMEOUT_MS,
  ANALYSIS_REQUEST_TIMEOUT_MS,
  chartWindowLabel,
  chartPoints,
  defaultAnalysisForm,
  intradayChartPoints,
  runAnalysisWorkflow,
  runBatchAnalysis,
  type AnalysisSnapshot,
} from "./analysisModel";

vi.mock("../../shared/api/client", () => ({
  apiClient: {
    analyzeSymbol: vi.fn(),
    quote: vi.fn(),
    kline: vi.fn(),
    stockKeyLevels: vi.fn(),
    marketIntradayAnomaly: vi.fn(),
    analyzeBatch: vi.fn(),
  },
}));

vi.mock("../../shared/workers/workerClient", () => ({
  sortDisplayItems: vi.fn(async ({ items }) => ({ result: items })),
}));

const mockedApiClient = vi.mocked(apiClient);

describe("analysis model chart data", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("uses backend daily kline bars as the default chart window", () => {
    const snapshot = {
      response: {} as AnalysisSnapshot["response"],
      supplement: {
        dailyKline: {
          period: "daily",
          bars: [
            { timestamp: "2026-06-01", open: 8, high: 8.2, low: 7.9, close: 8.12 },
            { timestamp: "2026-06-02", open: 8.12, high: 8.36, low: 8.05, close: 8.3 },
          ],
        },
        intradayKline: {
          period: "5m",
          bars: [
            { timestamp: "2026-06-03 09:35", open: 8.3, high: 8.33, low: 8.29, close: 8.31 },
          ],
        },
        errors: [],
      },
    };

    expect(chartPoints(snapshot)).toEqual([
      { time: "2026-06-01", open: 8, high: 8.2, low: 7.9, close: 8.12 },
      { time: "2026-06-02", open: 8.12, high: 8.36, low: 8.05, close: 8.3 },
    ]);
    expect(intradayChartPoints(snapshot)).toEqual([
      { time: "2026-06-03 09:35", open: 8.3, high: 8.33, low: 8.29, close: 8.31 },
    ]);
    expect(chartWindowLabel(snapshot, "daily")).toBe("日线 2 个交易日");
    expect(chartWindowLabel(snapshot, "intraday")).toBe("5分钟 1 根");
  });

  it("does not mix intraday bars into the daily analysis window", () => {
    const snapshot = {
      response: {
        bars: [
          { timestamp: "2026-06-03 09:35", open: 8.3, high: 8.33, low: 8.29, close: 8.31 },
        ],
      } as unknown as AnalysisSnapshot["response"],
      supplement: {
        kline: {
          period: "5m",
          bars: [
            { timestamp: "2026-06-03 09:35", open: 8.3, high: 8.33, low: 8.29, close: 8.31 },
          ],
        },
        errors: [],
      },
    };

    expect(chartPoints(snapshot)).toEqual([]);
    expect(chartWindowLabel(snapshot, "daily")).toBe("日线 120D");
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

  it("loads daily analysis kline and a 5m intraday confirmation window", async () => {
    mockedApiClient.analyzeSymbol.mockResolvedValue({ symbol: "000001" } as never);
    mockedApiClient.quote.mockResolvedValue({} as never);
    mockedApiClient.kline.mockResolvedValue({ bars: [] } as never);
    mockedApiClient.stockKeyLevels.mockResolvedValue({} as never);
    mockedApiClient.marketIntradayAnomaly.mockResolvedValue({} as never);

    await runAnalysisWorkflow({ ...defaultAnalysisForm, symbol: "000001" });

    expect(mockedApiClient.analyzeSymbol).toHaveBeenCalledWith(
      expect.objectContaining({ symbol: "000001" }),
      expect.objectContaining({ timeoutMs: ANALYSIS_REQUEST_TIMEOUT_MS }),
    );
    expect(mockedApiClient.kline).toHaveBeenCalledWith("000001", "daily", ANALYSIS_DAILY_KLINE_LIMIT, {});
    expect(mockedApiClient.kline).toHaveBeenCalledWith("000001", "5m", ANALYSIS_INTRADAY_KLINE_LIMIT, {});
  });

  it("uses a longer timeout for batch analysis", async () => {
    mockedApiClient.analyzeBatch.mockResolvedValue([] as never);

    await runBatchAnalysis({ ...defaultAnalysisForm, batchSymbols: "000001,600000" });

    expect(mockedApiClient.analyzeBatch).toHaveBeenCalledWith(
      [expect.objectContaining({ symbol: "000001" }), expect.objectContaining({ symbol: "600000" })],
      false,
      expect.objectContaining({ timeoutMs: ANALYSIS_BATCH_REQUEST_TIMEOUT_MS }),
    );
  });
});
