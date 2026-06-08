import { apiClient, type RequestJsonOptions } from "../../shared/api/client";
import { errorMessage } from "../../shared/api/errors";
import type { AnalyzeSymbolResponse } from "../../shared/api/types";
import type { KlineCandlePoint } from "../../shared/charts/KlineChart";
import { sortDisplayItems } from "../../shared/workers/workerClient";
import { nested, numberText, pctText, pickFirst, readArray, readRecord, text } from "../shared/dataAccess";

export interface AnalysisFormState {
  symbol: string;
  batchSymbols: string;
  basePosition: number;
  availablePosition: number;
  preferStrategy: "auto" | "positive_t" | "negative_t";
  includeAi: boolean;
}

export interface AnalysisRequestPayload {
  symbol: string;
  base_position: number;
  available_position: number;
  cost_basis: number | null;
  include_ai: boolean;
  include_events: boolean;
  include_microstructure: boolean;
  prefer_strategy: "auto" | "positive_t" | "negative_t";
}

export interface AnalysisSupplement {
  quote?: unknown;
  kline?: unknown;
  keyLevels?: unknown;
  anomaly?: unknown;
  errors: string[];
}

export interface AnalysisSnapshot {
  response: AnalyzeSymbolResponse;
  supplement: AnalysisSupplement;
}

export interface BatchAnalysisRow {
  symbol: string;
  name: string;
  action: string;
  score: number;
  positionPct: number;
  risk: string;
  price: string;
  reason: string;
}

export const defaultAnalysisForm: AnalysisFormState = {
  symbol: "",
  batchSymbols: "",
  basePosition: 1000,
  availablePosition: 1000,
  preferStrategy: "auto",
  includeAi: true,
};

export function buildAnalysisPayload(form: AnalysisFormState, symbol = form.symbol): AnalysisRequestPayload {
  return {
    symbol: normalizeSymbol(symbol),
    base_position: positiveNumber(form.basePosition, 1000),
    available_position: positiveNumber(form.availablePosition, 1000),
    cost_basis: null,
    include_ai: form.includeAi,
    include_events: true,
    include_microstructure: true,
    prefer_strategy: form.preferStrategy,
  };
}

export async function runAnalysisWorkflow(form: AnalysisFormState, init: RequestJsonOptions = {}): Promise<AnalysisSnapshot> {
  const payload = buildAnalysisPayload(form);
  const [response, quote, kline, keyLevels, anomaly] = await Promise.allSettled([
    apiClient.analyzeSymbol(payload, init),
    apiClient.quote(payload.symbol, init),
    apiClient.kline(payload.symbol, "daily", 120, init),
    apiClient.stockKeyLevels(payload.symbol, init),
    apiClient.marketIntradayAnomaly(payload.symbol, init),
  ]);
  if (response.status === "rejected") throw response.reason;
  return {
    response: response.value,
    supplement: {
      quote: settledValue(quote),
      kline: settledValue(kline),
      keyLevels: settledValue(keyLevels),
      anomaly: settledValue(anomaly),
      errors: [quote, kline, keyLevels, anomaly].filter((item) => item.status === "rejected").map((item) => errorMessage(item.reason)),
    },
  };
}

export async function runBatchAnalysis(form: AnalysisFormState, init: RequestJsonOptions = {}): Promise<BatchAnalysisRow[]> {
  const payloads = parseSymbols(form.batchSymbols).map((symbol) => buildAnalysisPayload(form, symbol));
  const response = await apiClient.analyzeBatch(payloads, false, init);
  const rows = readArray<Record<string, unknown>>(response).map(batchRow);
  const sorted = await sortDisplayItems({ items: rows, key: "score", direction: "desc", numeric: true });
  return sorted.result ?? rows;
}

export function chartPoints(snapshot: AnalysisSnapshot | null): KlineCandlePoint[] {
  const bars = readArray<Record<string, unknown>>(readRecord(snapshot?.supplement.kline).bars).length
    ? readArray<Record<string, unknown>>(readRecord(snapshot?.supplement.kline).bars)
    : readArray<Record<string, unknown>>(readRecord(snapshot?.response).bars);
  const points = bars
    .map((bar) => candlePoint(bar))
    .filter((point): point is KlineCandlePoint => Boolean(point));
  return points.length ? points.slice(-120) : [];
}

export function summaryMetrics(snapshot: AnalysisSnapshot | null) {
  const root = readRecord(snapshot?.response);
  const suggestion = readRecord(root.suggestion);
  const quote = readRecord(root.quote ?? snapshot?.supplement.quote);
  const micro = readRecord(root.microstructure);
  return [
    { label: "建议动作", value: text(suggestion.plain_action_text ?? suggestion.effective_action ?? suggestion.action, "待分析") },
    { label: "信号分", value: numberText(suggestion.signal_score ?? nested(root, "metrics.signal_score"), "--") },
    { label: "建议仓位", value: pctText(suggestion.position_pct, "--") },
    { label: "最新价", value: numberText(quote.last_price ?? quote.latest_price, "--") },
    { label: "买压", value: numberText(micro.buy_pressure, "--") },
    { label: "卖压", value: numberText(micro.sell_pressure, "--") },
  ];
}

export function keyLevelRows(snapshot: AnalysisSnapshot | null) {
  const keyLevelRoot = readRecord(snapshot?.supplement.keyLevels);
  return readArray<Record<string, unknown>>(keyLevelRoot.key_level_candidates).slice(0, 8);
}

export function anomalyRecord(snapshot: AnalysisSnapshot | null) {
  return readRecord(snapshot?.supplement.anomaly);
}

export function quoteRecord(snapshot: AnalysisSnapshot | null) {
  return readRecord(readRecord(snapshot?.response).quote ?? snapshot?.supplement.quote);
}

export function analysisReason(snapshot: AnalysisSnapshot | null): string {
  const root = readRecord(snapshot?.response);
  const suggestion = readRecord(root.suggestion);
  return text(suggestion.plain_action_reason ?? suggestion.plain_execution_text ?? readArray(root.assumptions).join(" / "), "等待分析结果");
}

export function aiLines(snapshot: AnalysisSnapshot | null): string[] {
  const ai = readRecord(readRecord(snapshot?.response).ai);
  return [text(ai.summary, "")].concat(readArray<string>(ai.suggestions)).filter(Boolean).slice(0, 4);
}

export function paperOrderDraftSearch(snapshot: AnalysisSnapshot | null, form: AnalysisFormState): Record<string, string> {
  const payload = buildAnalysisPayload(form);
  const root = readRecord(snapshot?.response);
  const suggestion = readRecord(root.suggestion);
  const quote = quoteRecord(snapshot);
  const instrument = readRecord(root.instrument);
  return {
    source: "analysis",
    symbol: text(root.symbol ?? payload.symbol, payload.symbol),
    name: text(instrument.name ?? quote.name, ""),
    side: text(suggestion.side ?? suggestion.order_side ?? suggestion.trade_side, "buy") === "sell" ? "sell" : "buy",
    order_type: text(suggestion.order_type, "limit") === "market" ? "market" : "limit",
    quantity: String(lotQuantity(payload.available_position || payload.base_position)),
    price: numberSearchValue(pickFirst(suggestion, ["limit_price", "suggested_price", "price"]) ?? pickFirst(quote, ["last_price", "latest_price"])),
    strategy_key: text(suggestion.strategy_key ?? root.strategy_key ?? payload.prefer_strategy, ""),
    reason: analysisReason(snapshot).slice(0, 80),
  };
}

export function parseSymbols(value: string): string[] {
  return Array.from(new Set(value.split(/[\s,，;；]+/).map(normalizeSymbol).filter(Boolean))).slice(0, 20);
}

function batchRow(item: Record<string, unknown>): BatchAnalysisRow {
  const suggestion = readRecord(item.suggestion);
  const quote = readRecord(item.quote);
  const score = Number(pickFirst(suggestion, ["signal_score", "confidence"]) ?? pickFirst(item, ["score", "signal_score"]) ?? 0);
  return {
    symbol: text(item.symbol),
    name: text(nested(item, "instrument.name") ?? quote.name, ""),
    action: text(suggestion.plain_action_text ?? suggestion.effective_action ?? suggestion.action, "观察"),
    score: Number.isFinite(score) ? score : 0,
    positionPct: Number(suggestion.position_pct ?? 0),
    risk: text(suggestion.risk_level ?? item.risk_level, "--"),
    price: numberText(quote.last_price ?? quote.latest_price, "--"),
    reason: text(suggestion.plain_action_reason ?? suggestion.strategy_notes, ""),
  };
}

function candlePoint(bar: Record<string, unknown>): KlineCandlePoint | null {
  const time = text(pickFirst(bar, ["timestamp", "date", "trade_date"]), "");
  const close = Number(pickFirst(bar, ["close", "value", "last_price"]));
  const open = Number(pickFirst(bar, ["open", "open_price"]) ?? close);
  const high = Number(pickFirst(bar, ["high", "high_price"]) ?? Math.max(open, close));
  const low = Number(pickFirst(bar, ["low", "low_price"]) ?? Math.min(open, close));
  if (!time || ![open, high, low, close].every(Number.isFinite)) return null;
  return {
    time,
    open,
    high: Math.max(high, open, close),
    low: Math.min(low, open, close),
    close,
  };
}

function normalizeSymbol(symbol: string): string {
  return symbol.trim().toUpperCase();
}

function positiveNumber(value: number, fallback: number): number {
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function lotQuantity(value: number): number {
  const quantity = Math.floor(positiveNumber(value, 100) / 100) * 100;
  return quantity > 0 ? quantity : 100;
}

function numberSearchValue(value: unknown): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? String(parsed) : "";
}

function settledValue<T>(result: PromiseSettledResult<T>): T | undefined {
  return result.status === "fulfilled" ? result.value : undefined;
}
