import { useCallback, useState } from "react";
import { api } from "../../api/client";
import type { AnalysisResponse, IntradayAnomalyResponse } from "../../types";
import { nullableNumber, parseNumber } from "./workspaceFormatters";
import type { AnalysisDraft, Page, StockCardView } from "./workspaceTypes";

type WorkspaceLoader = <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;

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
  const [draft, setDraft] = useState<AnalysisDraft>({
    symbol: "510300",
    prefer_strategy: "auto",
    base_position: "3000",
    available_position: "3000",
    cost_basis: "",
  });
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [anomaly, setAnomaly] = useState<IntradayAnomalyResponse | null>(null);
  const [batchSymbols, setBatchSymbols] = useState("");
  const [batchResults, setBatchResults] = useState<AnalysisResponse[]>([]);

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
      setBatchResults(sortBatchAnalysis(responses));
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

function sortBatchAnalysis(items: AnalysisResponse[]): AnalysisResponse[] {
  return [...items].sort((left, right) => {
    const leftAction = left.suggestion.is_actionable ? 1000 : 0;
    const rightAction = right.suggestion.is_actionable ? 1000 : 0;
    return (rightAction + right.suggestion.signal_score) - (leftAction + left.suggestion.signal_score);
  });
}
