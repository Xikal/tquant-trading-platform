import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getAdminApiToken } from "../../api/base";
import { api } from "../../api/client";
import type {
  LowBuyPriorityBoardResult,
  LowBuyQuoteRefreshItem,
  MarketBreadth,
  PairedHedgeResearchResponse,
  RuntimeStatus,
  SectorEtfT0Response,
  WatchlistSignal,
} from "../../types";
import { DEFAULT_PLAYBOOK_STRATEGY } from "./workspaceConstants";
import { errorMessage } from "./workspaceFormatters";
import type { StockCardView } from "./workspaceTypes";
import { priorityToCard, watchSignalToCard } from "./workspaceViewModels";
import {
  applyPriorityBoardQuoteRefresh,
  applySectorEtfQuoteRefresh,
  applyWatchlistQuoteRefresh,
  collectPrioritySymbolsByStrategy,
  realtimePriceRefreshIntervalMs,
  shouldRefreshRealtimePrices,
} from "./realtimePriceRefresh";

type WithLoading = <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;

interface UseMonitorDataOptions {
  active: boolean;
  withLoading: WithLoading;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
}

export function useMonitorData({ active, withLoading, setError, setNotice }: UseMonitorDataOptions) {
  const [priorityBoard, setPriorityBoard] = useState<LowBuyPriorityBoardResult | null>(null);
  const [marketBreadth, setMarketBreadth] = useState<MarketBreadth | null>(null);
  const [watchlistSignals, setWatchlistSignals] = useState<WatchlistSignal[]>([]);
  const [sectorEtfT0, setSectorEtfT0] = useState<SectorEtfT0Response | null>(null);
  const [pairedHedge, setPairedHedge] = useState<PairedHedgeResearchResponse | null>(null);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const monitorRefreshRef = useRef(false);
  const quoteRefreshRef = useRef(false);
  const priorityBoardRef = useRef<LowBuyPriorityBoardResult | null>(null);
  const watchlistSignalsRef = useRef<WatchlistSignal[]>([]);
  const sectorEtfT0Ref = useRef<SectorEtfT0Response | null>(null);

  const priorityCards: StockCardView[] = useMemo(
    () => (priorityBoard?.items ?? []).map(priorityToCard),
    [priorityBoard]
  );
  const watchCards: StockCardView[] = useMemo(
    () => watchlistSignals.map(watchSignalToCard),
    [watchlistSignals]
  );

  useEffect(() => {
    priorityBoardRef.current = priorityBoard;
  }, [priorityBoard]);

  useEffect(() => {
    watchlistSignalsRef.current = watchlistSignals;
  }, [watchlistSignals]);

  useEffect(() => {
    sectorEtfT0Ref.current = sectorEtfT0;
  }, [sectorEtfT0]);

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

  useEffect(() => {
    if (!active) {
      return undefined;
    }
    let cancelled = false;
    let timer: number | undefined;
    const refreshQuotes = async () => {
      if (!shouldRefreshRealtimePrices() || quoteRefreshRef.current || cancelled) {
        return;
      }
      const currentBoard = priorityBoardRef.current;
      const currentWatchlist = watchlistSignalsRef.current;
      const currentEtfT0 = sectorEtfT0Ref.current;
      const priorityGroups = collectPrioritySymbolsByStrategy(currentBoard?.items ?? []);
      const etfSymbols = [...new Set((currentEtfT0?.opportunities ?? []).map((item) => item.etf_symbol).filter(Boolean))];
      if (!priorityGroups.length && !currentWatchlist.length && !etfSymbols.length) {
        return;
      }
      quoteRefreshRef.current = true;
      try {
        const priorityResults = await Promise.allSettled(
          priorityGroups.map(({ strategy, symbols }) => api.getLowBuyQuoteRefresh(strategy, symbols)),
        );
        if (cancelled) {
          return;
        }
        const priorityQuoteMap = priorityResults.reduce<Record<string, LowBuyQuoteRefreshItem>>((acc, result) => {
          if (result.status === "fulfilled") {
            Object.assign(acc, result.value.items);
          }
          return acc;
        }, {});
        if (currentBoard && Object.keys(priorityQuoteMap).length) {
          setPriorityBoard((board) => (board ? applyPriorityBoardQuoteRefresh(board, priorityQuoteMap) : board));
        }

        if (currentWatchlist.length) {
          const watchlistQuotes = await api.getWatchlistQuotes();
          if (!cancelled && watchlistQuotes.length) {
            setWatchlistSignals((signals) => applyWatchlistQuoteRefresh(signals, watchlistQuotes));
          }
        }

        if (etfSymbols.length) {
          const etfQuotes = await api.getLowBuyQuoteRefresh(DEFAULT_PLAYBOOK_STRATEGY, etfSymbols);
          if (!cancelled) {
            setSectorEtfT0((payload) =>
              payload ? applySectorEtfQuoteRefresh(payload, etfQuotes.items) : payload,
            );
          }
        }
      } catch (err) {
        if (import.meta.env.DEV) {
          console.warn("监控实时价格刷新失败，已保留上次快照。", err);
        }
      } finally {
        quoteRefreshRef.current = false;
      }
    };
    const scheduleNext = () => {
      timer = window.setTimeout(() => {
        void refreshQuotes().finally(() => {
          if (!cancelled) {
            scheduleNext();
          }
        });
      }, realtimePriceRefreshIntervalMs());
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void refreshQuotes();
      }
    };
    void refreshQuotes();
    scheduleNext();
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      cancelled = true;
      if (timer) {
        window.clearTimeout(timer);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [active]);

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
