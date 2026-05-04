import { useMemo, useRef, useState } from "react";
import { getAdminApiToken } from "../../api/base";
import { api } from "../../api/client";
import type { LowBuyPriorityBoardResult, MarketBreadth, RuntimeStatus, WatchlistSignal } from "../../types";
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

  async function fetchMonitorData(includeRuntime: boolean) {
    if (monitorRefreshRef.current) {
      return;
    }
    monitorRefreshRef.current = true;
    try {
      const shouldLoadRuntime = includeRuntime && Boolean(getAdminApiToken());
      const requests = [
        api.getMonitorSnapshot(24),
        api.getMarketBreadth(),
        shouldLoadRuntime ? api.getRuntimeStatus() : Promise.resolve(null),
      ] as const;
      const [monitorResult, breadthResult, runtimeResult] = await Promise.allSettled(requests);
      if (monitorResult.status === "fulfilled") {
        setPriorityBoard(monitorResult.value.priority_board);
        setWatchlistSignals(monitorResult.value.watchlist_signals);
      }
      if (breadthResult.status === "fulfilled") {
        setMarketBreadth(breadthResult.value);
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
  }

  async function refreshMonitor() {
    await withLoading("monitor", () => fetchMonitorData(true));
  }

  async function syncInstruments() {
    await withLoading("sync", async () => {
      const result = await api.syncInstruments();
      setNotice(result.message || "标的同步完成");
      await refreshMonitor();
    });
  }

  function resetMonitorData() {
    setPriorityBoard(null);
    setMarketBreadth(null);
    setWatchlistSignals([]);
  }

  return {
    priorityBoard,
    setPriorityBoard,
    marketBreadth,
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
