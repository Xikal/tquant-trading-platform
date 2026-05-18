import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invalidateCache } from "../../api/base";
import { getAdminApiToken } from "../../api/base";
import { api } from "../../api/client";
import type {
  LowBuyPriorityBoardResult,
  LowBuyQuoteRefreshItem,
  InstrumentSyncStatus,
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
  refreshTradingSessionStatus,
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
  const [instrumentSyncStatus, setInstrumentSyncStatus] = useState<InstrumentSyncStatus | null>(null);
  const monitorRefreshRef = useRef(false);
  const quoteRefreshRef = useRef(false);
  const instrumentSyncPollRef = useRef<number | null>(null);
  const instrumentSyncRunIdRef = useRef<string>("");
  const pendingRetryTimerRef = useRef<number | null>(null);
  const pendingRetryCountRef = useRef(0);
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

  const clearPendingRetry = useCallback(() => {
    if (pendingRetryTimerRef.current != null) {
      window.clearTimeout(pendingRetryTimerRef.current);
      pendingRetryTimerRef.current = null;
    }
  }, []);

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

  const stopInstrumentSyncPolling = useCallback(() => {
    if (instrumentSyncPollRef.current != null) {
      window.clearInterval(instrumentSyncPollRef.current);
      instrumentSyncPollRef.current = null;
    }
  }, []);

  const pollInstrumentSyncStatus = useCallback(async (runId: string) => {
    try {
      const status = await api.getInstrumentSyncStatus(runId);
      if (instrumentSyncRunIdRef.current !== runId) {
        return;
      }
      setInstrumentSyncStatus(status);
      if (status.status === "queued" || status.status === "running") {
        return;
      }
      stopInstrumentSyncPolling();
      if (status.status === "succeeded") {
        setNotice(status.message || "股票库更新完成");
        await refreshMonitor();
      } else if (status.status === "failed") {
        setError(status.error || status.message || "股票库更新失败");
      }
    } catch {
      // Keep polling; transient auth/network failures should not hide the in-flight task.
    }
  }, [refreshMonitor, setError, setNotice, stopInstrumentSyncPolling]);

  const startInstrumentSyncPolling = useCallback((runId: string) => {
    stopInstrumentSyncPolling();
    instrumentSyncRunIdRef.current = runId;
    void pollInstrumentSyncStatus(runId);
    instrumentSyncPollRef.current = window.setInterval(() => void pollInstrumentSyncStatus(runId), 900);
  }, [pollInstrumentSyncStatus, stopInstrumentSyncPolling]);

  const syncInstruments = useCallback(async () => {
    await withLoading("sync", async () => {
      setInstrumentSyncStatus({
        run_id: "pending",
        kind: "all",
        status: "queued",
        progress_pct: 1,
        message: "正在提交更新请求",
        result: {},
        updated_at: new Date().toISOString(),
      });
      try {
        const result = await api.syncInstruments();
        instrumentSyncRunIdRef.current = result.run_id;
        setInstrumentSyncStatus(result.status);
        setNotice(result.message || "股票库更新任务已提交");
        startInstrumentSyncPolling(result.run_id);
      } catch (error) {
        try {
          setInstrumentSyncStatus(await api.getInstrumentSyncStatus(instrumentSyncRunIdRef.current || undefined));
        } catch {
          // Keep the local progress text if the status endpoint is unreachable.
        }
        throw error;
      }
    });
  }, [setNotice, startInstrumentSyncPolling, withLoading]);

  const resetMonitorData = useCallback(() => {
    clearPendingRetry();
    pendingRetryCountRef.current = 0;
    setPriorityBoard(null);
    setMarketBreadth(null);
    setSectorEtfT0(null);
    setPairedHedge(null);
    setWatchlistSignals([]);
  }, [clearPendingRetry]);

  useEffect(() => {
    if (!active) {
      clearPendingRetry();
      return undefined;
    }
    if (!isPendingMonitorSnapshot(priorityBoard)) {
      clearPendingRetry();
      pendingRetryCountRef.current = 0;
      return undefined;
    }
    if (pendingRetryCountRef.current >= 5) {
      return undefined;
    }
    clearPendingRetry();
    pendingRetryTimerRef.current = window.setTimeout(() => {
      pendingRetryCountRef.current += 1;
      invalidateCache(["/monitor/snapshot", "/market/breadth"]);
      void fetchMonitorData(false);
    }, 3500);
    return () => clearPendingRetry();
  }, [active, clearPendingRetry, fetchMonitorData, priorityBoard]);

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
      void refreshTradingSessionStatus(api.getMarketTradingSession).finally(() => {
        if (cancelled) {
          return;
        }
        timer = window.setTimeout(() => {
          void refreshQuotes().finally(() => {
            if (!cancelled) {
              scheduleNext();
            }
          });
        }, realtimePriceRefreshIntervalMs());
      });
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void refreshQuotes();
      }
    };
    void refreshTradingSessionStatus(api.getMarketTradingSession).finally(() => {
      if (!cancelled) {
        void refreshQuotes();
        scheduleNext();
      }
    });
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      cancelled = true;
      if (timer) {
        window.clearTimeout(timer);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [active]);

  useEffect(() => () => stopInstrumentSyncPolling(), [stopInstrumentSyncPolling]);

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
    instrumentSyncStatus,
    priorityCards,
    watchCards,
    fetchMonitorData,
    refreshMonitor,
    syncInstruments,
    resetMonitorData,
  };
}

function isPendingMonitorSnapshot(priorityBoard: LowBuyPriorityBoardResult | null): boolean {
  if (!priorityBoard) {
    return false;
  }
  const warning = `${priorityBoard.snapshot_warning ?? ""} ${priorityBoard.data_quality_text ?? ""}`;
  return warning.includes("已排队") || warning.includes("后台刷新中");
}
