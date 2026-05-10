import { useCallback, useMemo, useRef, useState } from "react";
import { getAdminApiToken } from "../../api/base";
import { api } from "../../api/client";
import type { LowBuyPriorityBoardResult, MarketBreadth, PairedHedgeResearchResponse, RuntimeStatus, SectorEtfT0Response, WatchlistSignal } from "../../types";
import { errorMessage } from "./workspaceFormatters";
import type { StockCardView } from "./workspaceTypes";
import { priorityToCard, watchSignalToCard } from "./workspaceViewModels";

type WithLoading = <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;

interface UseMonitorDataOptions {
  withLoading: WithLoading;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
}

export function useMonitorData({ withLoading, setError, setNotice }: UseMonitorDataOptions) {
  const [priorityBoard, setPriorityBoard] = useState<LowBuyPriorityBoardResult | null>(null);
  const [marketBreadth, setMarketBreadth] = useState<MarketBreadth | null>(null);
  const [watchlistSignals, setWatchlistSignals] = useState<WatchlistSignal[]>([]);
  const [sectorEtfT0, setSectorEtfT0] = useState<SectorEtfT0Response | null>(null);
  const [pairedHedge, setPairedHedge] = useState<PairedHedgeResearchResponse | null>(null);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const monitorRefreshRef = useRef(false);

  const priorityCards: StockCardView[] = useMemo(
    () => (priorityBoard?.items ?? []).map(priorityToCard),
    [priorityBoard]
  );
  const watchCards: StockCardView[] = useMemo(
    () => watchlistSignals.map(watchSignalToCard),
    [watchlistSignals]
  );

  const fetchMonitorData = useCallback(async (includeRuntime: boolean) => {
    if (monitorRefreshRef.current) {
      return;
    }
    monitorRefreshRef.current = true;
    try {
      const shouldLoadRuntime = includeRuntime && Boolean(getAdminApiToken());
      const requests = [
        api.getMonitorSnapshot(12),
        api.getMarketBreadth(),
        api.getPairedHedgeResearch(4),
        shouldLoadRuntime ? api.getRuntimeStatus() : Promise.resolve(null),
      ] as const;
      const [monitorResult, breadthResult, hedgeResult, runtimeResult] = await Promise.allSettled(requests);
      if (monitorResult.status === "fulfilled") {
        setPriorityBoard(monitorResult.value.priority_board);
        setWatchlistSignals(monitorResult.value.watchlist_signals);
        setSectorEtfT0(monitorResult.value.sector_etf_t0 ?? null);
      }
      if (breadthResult.status === "fulfilled") {
        setMarketBreadth(breadthResult.value);
      }
      if (hedgeResult.status === "fulfilled") {
        setPairedHedge(hedgeResult.value);
      }
      if (runtimeResult.status === "fulfilled" && runtimeResult.value) {
        setRuntime(runtimeResult.value);
      }
      const rejected = [monitorResult, runtimeResult].find(
        (item): item is PromiseRejectedResult => item.status === "rejected"
      );
      if (rejected) {
        setError(errorMessage(rejected.reason));
      }
    } finally {
      monitorRefreshRef.current = false;
    }
  }, [setError]);

  const refreshMonitor = useCallback(async () => {
    await withLoading("monitor", () => fetchMonitorData(true));
  }, [fetchMonitorData, withLoading]);

  const syncInstruments = useCallback(async () => {
    await withLoading("sync", async () => {
      const result = await api.syncInstruments();
      setNotice(result.message || "标的同步完成");
      await refreshMonitor();
    });
  }, [refreshMonitor, setNotice, withLoading]);

  const resetMonitorData = useCallback(() => {
    setPriorityBoard(null);
    setMarketBreadth(null);
    setSectorEtfT0(null);
    setPairedHedge(null);
    setWatchlistSignals([]);
  }, []);

  return {
    priorityBoard,
    setPriorityBoard,
    marketBreadth,
    sectorEtfT0,
    pairedHedge,
    watchlistSignals,
    setWatchlistSignals,
    runtime,
    setRuntime,
    priorityCards,
    watchCards,
    fetchMonitorData,
    refreshMonitor,
    syncInstruments,
    resetMonitorData,
  };
}
