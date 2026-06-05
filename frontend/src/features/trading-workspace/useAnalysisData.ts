import { useCallback } from "react";
import { api } from "../../api/client";
import type { AnalysisResponse, IntradayAnomalyResponse } from "../../types";
import { useWorkspaceAnalysisStore } from "../../stores/workspaceAnalysisStore";
import { useServerState } from "../../state/serverState";
import { rankAnalysisBatch } from "../../workers/workerClient";
import { nullableNumber, parseNumber } from "../workspace-shared/workspaceFormatters";
import type { Page, StockCardView } from "../workspace-shared/workspaceTypes";

type WorkspaceLoader = <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;

const ANALYSIS_SERVER_KEYS = {
  result: ["workspace-analysis", "result"] as const,
  anomaly: ["workspace-analysis", "anomaly"] as const,
  batchResults: ["workspace-analysis", "batch-results"] as const,
};

export function useAnalysisData({
  withLoading,
  setError,
  setNotice,
  navigatePage,
}: {
  withLoading: WorkspaceLoader;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
  navigatePage: (page: Page) => void;
}) {
  const draft = useWorkspaceAnalysisStore((state) => state.draft);
  const batchSymbols = useWorkspaceAnalysisStore((state) => state.batchSymbols);
  const setDraft = useWorkspaceAnalysisStore((state) => state.setDraft);
  const setBatchSymbols = useWorkspaceAnalysisStore((state) => state.setBatchSymbols);
  const [result, setResult] = useServerState<AnalysisResponse | null>(ANALYSIS_SERVER_KEYS.result, null);
  const [anomaly, setAnomaly] = useServerState<IntradayAnomalyResponse | null>(ANALYSIS_SERVER_KEYS.anomaly, null);
  const [batchResults, setBatchResults] = useServerState<AnalysisResponse[]>(ANALYSIS_SERVER_KEYS.batchResults, []);

  const runAnalysis = useCallback(
    async (symbolOverride?: string) => {
      const symbol = (symbolOverride ?? draft.symbol).trim();
      if (!symbol) {
        setError("请填写证券代码");
        return;
      }
      setDraft((current) => ({ ...current, symbol }));
      navigatePage("analysis");
      await withLoading("analysis", async () => {
        const [analysisResult, anomalyResult] = await Promise.allSettled([
          api.analyze({
            symbol,
            prefer_strategy: draft.prefer_strategy,
            base_position: parseNumber(draft.base_position),
            available_position: parseNumber(draft.available_position),
            cost_basis: nullableNumber(draft.cost_basis),
            include_ai: false,
            include_events: true,
            include_microstructure: true,
          }),
          api.getIntradayAnomaly(symbol),
        ]);
        if (analysisResult.status === "rejected") {
          throw analysisResult.reason;
        }
        const response = analysisResult.value;
        setResult(response);
        setAnomaly(anomalyResult.status === "fulfilled" ? anomalyResult.value : null);
        setNotice(`${response.instrument.name} 分析完成`);
      });
    },
    [draft, navigatePage, setError, setNotice, withLoading],
  );

  const analyzeFromCard = useCallback(
    (card: StockCardView) => {
      void runAnalysis(card.symbol);
    },
    [runAnalysis],
  );

  const runBatchAnalysis = useCallback(async () => {
    const symbols = batchSymbols
      .split(/[\s,，;；]+/)
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, 8);
    if (!symbols.length) {
      setError("请填写要批量分析的证券代码，多个代码用逗号或空格分隔");
      return;
    }
    navigatePage("analysis");
    await withLoading("analysis-batch", async () => {
      const payload = symbols.map((symbol) => ({
        symbol,
        prefer_strategy: draft.prefer_strategy,
        base_position: parseNumber(draft.base_position),
        available_position: parseNumber(draft.available_position),
        cost_basis: nullableNumber(draft.cost_basis),
        include_ai: false,
        include_events: true,
        include_microstructure: true,
      }));
      const responses = await api.analyzeBatch(payload);
      const ranked = await rankAnalysisBatch({ items: responses.map(toAnalysisRankItem) });
      setBatchResults(applyAnalysisRankOrder(responses, ranked.items.map((item) => item.symbol)));
      setNotice(`批量分析完成：${responses.length} 只`);
    });
  }, [batchSymbols, draft, navigatePage, setError, setNotice, withLoading]);

  return {
    draft,
    setDraft,
    result,
    anomaly,
    batchSymbols,
    setBatchSymbols,
    batchResults,
    runAnalysis,
    runBatchAnalysis,
    analyzeFromCard,
  };
}

function toAnalysisRankItem(item: AnalysisResponse) {
  return {
    symbol: item.symbol,
    suggestion: {
      is_actionable: Boolean(item.suggestion.is_actionable),
      signal_score: item.suggestion.signal_score,
    },
  };
}

function applyAnalysisRankOrder(items: AnalysisResponse[], symbols: string[]): AnalysisResponse[] {
  const bySymbol = new Map(items.map((item) => [item.symbol, item]));
  const ranked = symbols
    .map((symbol) => bySymbol.get(symbol))
    .filter((item): item is AnalysisResponse => Boolean(item));
  return ranked.length === items.length ? ranked : items;
}
