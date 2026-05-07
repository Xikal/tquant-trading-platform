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

  return {
    draft,
    setDraft,
    result,
    anomaly,
    runAnalysis,
    analyzeFromCard,
  };
}
