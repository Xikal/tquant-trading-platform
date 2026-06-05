import { afterEach, describe, expect, it, vi } from "vitest";
import { downsampleChartPoints, rankAnalysisBatch, resetFrontendComputeWorkerForTests } from "../workerClient";
import type { GeneratedAnalysisResponse } from "../protocol";

class EchoWorker {
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  postMessage(message: { id: string; kind: string; payload: Record<string, unknown> }) {
    const payload = message.kind === "analysisBatchRank"
      ? analysisBatchPayload(message.payload)
      : chartDownsamplePayload(message.payload);
    queueMicrotask(() => {
      this.onmessage?.({
        data: {
          elapsed_ms: 1,
          id: message.id,
          kind: message.kind,
          payload,
        },
      } as MessageEvent);
    });
  }

  terminate() {
    return undefined;
  }
}

class FailingWorker {
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  postMessage() {
    queueMicrotask(() => this.onerror?.());
  }

  terminate() {
    return undefined;
  }
}

describe("frontend worker client", () => {
  afterEach(() => {
    resetFrontendComputeWorkerForTests();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("uses the worker path for large chart downsample payloads", async () => {
    vi.stubGlobal("Worker", EchoWorker);
    const result = await downsampleChartPoints({ maxPoints: 80, points: chartPoints(160) });

    expect(result.input_count).toBe(160);
    expect(result.output_count).toBe(80);
    expect(result.points).toHaveLength(80);
  });

  it("uses the worker path for large analysis batch rank payloads", async () => {
    vi.stubGlobal("Worker", EchoWorker);
    const result = await rankAnalysisBatch({
      items: Array.from({ length: 100 }, (_, index) => analysisItem(String(index), index, index === 3)),
    });

    expect(result.total).toBe(100);
    expect(result.items[0]?.symbol).toBe("3");
  });

  it("falls back to the synchronous path when the worker flag is disabled", async () => {
    vi.stubEnv("VITE_FRONTEND_WORKER_COMPUTE_ENABLED", "false");
    vi.stubGlobal("Worker", FailingWorker);
    const result = await downsampleChartPoints({ maxPoints: 80, points: chartPoints(160) });

    expect(result.input_count).toBe(160);
    expect(result.output_count).toBe(80);
    expect(result.points[0]?.date).toBe("2026-01-01");
    expect(result.points[result.points.length - 1]?.date).toBe("2026-01-160");
  });

  it("falls back to the synchronous path when the worker fails", async () => {
    vi.stubGlobal("Worker", FailingWorker);
    const result = await downsampleChartPoints({ maxPoints: 80, points: chartPoints(160) });

    expect(result.input_count).toBe(160);
    expect(result.output_count).toBe(80);
    expect(result.points[0]?.date).toBe("2026-01-01");
    expect(result.points[result.points.length - 1]?.date).toBe("2026-01-160");
  });
});

function chartDownsamplePayload(payload: Record<string, unknown>) {
  const points = payload.points as Array<{ date: string; nav: number }>;
  const maxPoints = payload.maxPoints as number;
  return {
    input_count: points.length,
    output_count: Math.min(points.length, maxPoints),
    points: points.slice(0, maxPoints),
  };
}

function analysisBatchPayload(payload: Record<string, unknown>) {
  const items = payload.items as GeneratedAnalysisResponse[];
  return {
    items: [...items].sort((left, right) => {
      const leftAction = left.suggestion?.is_actionable ? 1000 : 0;
      const rightAction = right.suggestion?.is_actionable ? 1000 : 0;
      return (rightAction + Number(right.suggestion?.signal_score ?? 0)) - (leftAction + Number(left.suggestion?.signal_score ?? 0));
    }),
    total: items.length,
  };
}

function chartPoints(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    date: `2026-01-${String(index + 1).padStart(2, "0")}`,
    nav: 1 + Math.sin(index / 5) * 0.05 + index * 0.001,
  }));
}

function analysisItem(symbol: string, signalScore: number, actionable: boolean): GeneratedAnalysisResponse {
  return {
    symbol,
    instrument: { symbol, name: symbol, market: "SH", instrument_type: "stock" },
    quote: {
      symbol,
      name: symbol,
      market: "SH",
      instrument_type: "stock",
      last_price: 10,
      change_pct: 0,
      change_amount: 0,
      open_price: 10,
      high_price: 10,
      low_price: 10,
      prev_close: 10,
      volume: 0,
      amount: 0,
      timestamp: "2026-06-05T15:00:00+08:00",
    },
    rules: {
      symbol,
      turnaround_mode: "t1",
      supports_positive_t: false,
      supports_negative_t: false,
      same_day_sell_allowed: false,
      requires_base_position: false,
      notes: "",
    },
    sector: { sector_name: "", sector_strength: 0, market_strength: 0, alignment_score: 0, notes: "" },
    events: [],
    microstructure: { available: false, buy_pressure: 0, sell_pressure: 0, large_order_flow: 0, notes: "" },
    bars: [],
    metrics: {},
    suggestion: {
      action: "hold",
      position_pct: 0,
      risk_level: "medium",
      signal_score: signalScore,
      tradability_score: 0,
      confidence: 0,
      expected_profit_pct: 0,
      scenario: "fixture",
      reasons: [],
      blocking_rules: [],
      is_actionable: actionable,
    },
    ai: { enabled: false, summary: "", confidence: 0, suggestions: [], warnings: [] },
    compliance_notes: [],
    assumptions: [],
  } as unknown as GeneratedAnalysisResponse;
}
