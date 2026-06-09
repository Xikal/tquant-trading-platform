import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { AnalysisResponse } from "../../types";
import { createAppQueryClient } from "../../state/queryClient";
import { AnalysisPage } from "../analysis/AnalysisPage";

function renderAnalysisPage(element: ReactElement) {
  return renderToStaticMarkup(
    <QueryClientProvider client={createAppQueryClient()}>
      {element}
    </QueryClientProvider>
  );
}

describe("AnalysisPage", () => {
  it("uses semantic layout classes for the analysis workspace", () => {
    const html = renderAnalysisPage(
      <AnalysisPage
        draft={{
          symbol: "510300",
          prefer_strategy: "auto",
          base_position: "3000",
          available_position: "3000",
          cost_basis: "",
        }}
        setDraft={vi.fn()}
        result={null}
        anomaly={null}
        batchSymbols=""
        setBatchSymbols={vi.fn()}
        batchResults={[]}
        loading=""
        onRun={vi.fn()}
        onBatchRun={vi.fn()}
      />,
    );

    expect(html).toContain("tq-analysis-page");
    expect(html).toContain("tq-analysis-page__hero");
    expect(html).toContain("tq-analysis-page__identity");
    expect(html).toContain("tq-analysis-page__control");
    expect(html).toContain("tq-analysis-page__batch");
    expect(html).toContain("tq-analysis-page__decision");
    expect(html).toContain("tq-analysis-page__key-levels");
    expect(html).toContain("tq-analysis-page__chart");
    expect(html).toContain("tq-analysis-page__plan");
  });

  it("does not repeat the same decision and execution copy across hero and plan details", () => {
    const html = renderAnalysisPage(
      <AnalysisPage
        draft={{
          symbol: "510300",
          prefer_strategy: "auto",
          base_position: "3000",
          available_position: "3000",
          cost_basis: "",
        }}
        setDraft={vi.fn()}
        result={analysisFixture()}
        anomaly={null}
        batchSymbols=""
        setBatchSymbols={vi.fn()}
        batchResults={[]}
        loading=""
        onRun={vi.fn()}
        onBatchRun={vi.fn()}
      />,
    );

    expect(countOccurrences(html, "当前先不下单")).toBe(1);
    expect(countOccurrences(html, "等待承接确认后再处理")).toBe(1);
    expect(countOccurrences(html, "跌破 3.20 失效")).toBe(1);
    expect(html).toContain("执行计划、AI 补充与合规假设");
    expect(html).not.toMatch(/建议买入|建议卖出|强烈推荐|直接低吸/);
  });
});

function countOccurrences(value: string, search: string) {
  return value.split(search).length - 1;
}

function analysisFixture(): AnalysisResponse {
  return {
    symbol: "510300",
    instrument: { symbol: "510300", name: "沪深300ETF", market: "SH", instrument_type: "etf" },
    quote: {
      symbol: "510300",
      name: "沪深300ETF",
      market: "SH",
      instrument_type: "etf",
      last_price: 3.45,
      change_pct: 0.3,
      change_amount: 0.01,
      open_price: 3.43,
      high_price: 3.48,
      low_price: 3.4,
      prev_close: 3.44,
      volume: 1000000,
      amount: 120000000,
      timestamp: "2026-06-01T10:30:00+08:00",
    },
    rules: {
      symbol: "510300",
      turnaround_mode: "t0",
      supports_positive_t: true,
      supports_negative_t: true,
      same_day_sell_allowed: true,
      requires_base_position: false,
      notes: "ETF T+0",
    },
    sector: {
      sector_name: "ETF",
      sector_strength: 55,
      market_strength: 52,
      alignment_score: 50,
      notes: "中性",
    },
    events: [],
    suggestion: {
      action: "hold",
      is_actionable: false,
      signal_layer: "watch_prepare",
      signal_layer_text: "观察提醒",
      plain_action_text: "观察提醒",
      plain_action_reason: "等待承接确认后再处理",
      plain_execution_text: "等待承接确认后再处理",
      plain_invalid_condition: "跌破 3.20 失效",
      trade_scene_text: "",
      entry_price: 3.4,
      exit_price: 3.55,
      stop_loss: 3.2,
      take_profit: 3.62,
      blocking_rules: [],
      risk_level: "medium",
      tradability_score: 55,
      signal_score: 62,
      confidence: 0.62,
      scenario: "watch",
      expected_profit_pct: 1.2,
      position_pct: 0,
      why_not_execute: "仍属观察提醒，不是买入动作",
      fee_warning: "",
      liquidity_warning: "",
      reasons: ["等待承接确认后再处理"],
      strategy_notes: "观察票只提醒，不下单。",
    },
    metrics: { amplitude_pct: 1.5, volume_ratio: 1.1 },
    bars: [],
    microstructure: {
      available: true,
      buy_pressure: 0.5,
      sell_pressure: 0.4,
      large_order_flow: 0.1,
      notes: "成交平稳",
    },
    ai: { enabled: true, summary: "AI 仅解释，不放宽规则。", confidence: 0.6, suggestions: [], warnings: [] },
    compliance_notes: ["观察提醒不是买入建议"],
    assumptions: [],
  };
}
