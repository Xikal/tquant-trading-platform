import { apiClient } from "./httpClient";
import type { KlineBar, MarketEvent, QuoteSnapshot, SectorSnapshot, TradingRule } from "../types";

export interface InstrumentInspectorResponse {
  symbol: string;
  quote: QuoteSnapshot | null;
  kline: { symbol: string; period: string; bars: KlineBar[] } | null;
  rules: TradingRule | null;
  sector: SectorSnapshot | null;
  events: MarketEvent[];
  partial_errors: string[];
}

export const dataConsoleInspectorApi = {
  inspect: async (symbol: string): Promise<InstrumentInspectorResponse> => {
    const code = encodeURIComponent(symbol.trim());
    const partial_errors: string[] = [];
    const quote = await readOrNull<QuoteSnapshot>(`/quote/${code}`, "行情", partial_errors);
    const kline = await readOrNull<{ symbol: string; period: string; bars: KlineBar[] }>(`/kline/${code}?period=5m&limit=80`, "K 线", partial_errors);
    const rules = await readOrNull<TradingRule>(`/instruments/${code}/rules`, "交易规则", partial_errors);
    const sector = await readOrNull<SectorSnapshot>(`/instruments/${code}/sector`, "板块", partial_errors);
    const eventPayload = await readOrNull<{ symbol: string; events: MarketEvent[] }>(`/instruments/${code}/events`, "事件", partial_errors);
    return {
      symbol,
      quote,
      kline,
      rules,
      sector,
      events: eventPayload?.events ?? [],
      partial_errors,
    };
  },
};

async function readOrNull<T>(path: string, label: string, partialErrors: string[]): Promise<T | null> {
  try {
    return await apiClient.request<T>(path);
  } catch (error) {
    partialErrors.push(`${label}：${error instanceof Error ? error.message : "加载失败"}`);
    return null;
  }
}
