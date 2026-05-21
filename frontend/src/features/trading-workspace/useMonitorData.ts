import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, getAuthAccessToken, getAdminApiToken, invalidateCache, request } from "../../api/base";
import { api } from "../../api/client";
import type {
  LowBuyPriorityBoardResult,
  LowBuyQuoteRefreshItem,
  InstrumentSyncStatus,
  MarketBreadth,
  IntradayKeyLevelResponse,
  PairedHedgeResearchResponse,
  RuntimeStatus,
  SectorEtfT0Response,
  SectorRelativeStrengthResponse,
  WatchlistSignal,
} from "../../types";
import { DEFAULT_PLAYBOOK_STRATEGY } from "../workspace-shared/workspaceConstants";
import { errorMessage } from "../workspace-shared/workspaceFormatters";
import type { StockCardView } from "../workspace-shared/workspaceTypes";
import { priorityToCard, watchSignalToCard } from "../workspace-shared/workspaceViewModels";
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
  const [sectorRelativeStrength, setSectorRelativeStrength] = useState<SectorRelativeStrengthResponse | null>(null);
  const [keyLevelAlerts, setKeyLevelAlerts] = useState<IntradayKeyLevelResponse[]>([]);
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
  const keyLevelSymbols = useMemo(() => [...new Set([
    ...(priorityBoard?.items ?? []).slice(0, 8).map((item) => item.symbol),
    ...watchlistSignals.slice(0, 8).map((item) => item.symbol),
  ].filter(Boolean))].slice(0, 16), [priorityBoard?.items, watchlistSignals]);
  const keyLevelSymbolsKey = keyLevelSymbols.join(",");
  const keyLevelEntryZonesKey = useMemo(() => (priorityBoard?.items ?? [])
    .slice(0, 8)
    .filter((item) => item.entry_zone_low > 0 && item.entry_zone_high > 0)
    .map((item) => `${item.symbol}:${item.entry_zone_low}:${item.entry_zone_high}`)
    .join(";"), [priorityBoard?.items]);

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
        api.getMonitorWorkspaceBff(12),
        shouldLoadRuntime ? api.getRuntimeStatus() : Promise.resolve(null),
      ] as const;
      const [workspaceResult, runtimeResult] = await Promise.allSettled(requests);
      if (workspaceResult.status === "fulfilled") {
        const monitorSnapshot = workspaceResult.value.monitor_snapshot;
        if (monitorSnapshot) {
          setPriorityBoard(monitorSnapshot.priority_board);
          setWatchlistSignals(monitorSnapshot.watchlist_signals);
          setSectorEtfT0(monitorSnapshot.sector_etf_t0 ?? null);
        }
        if (workspaceResult.value.market_breadth) {
          setMarketBreadth(workspaceResult.value.market_breadth);
        }
        if (workspaceResult.value.sector_relative_strength) {
          setSectorRelativeStrength(workspaceResult.value.sector_relative_strength);
        }
        if (workspaceResult.value.paired_hedge) {
          setPairedHedge(workspaceResult.value.paired_hedge);
        }
      }
      if (runtimeResult.status === "fulfilled" && runtimeResult.value) {
        setRuntime(runtimeResult.value);
      }
      const rejected = [workspaceResult, runtimeResult].find(
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
    setSectorRelativeStrength(null);
    setKeyLevelAlerts([]);
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
      invalidateCache(["/monitor/snapshot", "/bff/v1/workspace/monitor", "/market/breadth"]);
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

  useEffect(() => {
    if (!active || !getAuthAccessToken()) {
      setKeyLevelAlerts([]);
      return undefined;
    }
    const symbols = keyLevelSymbolsKey ? keyLevelSymbolsKey.split(",") : [];
    if (!symbols.length) {
      setKeyLevelAlerts([]);
      return undefined;
    }
    let source: EventSource | undefined;
    let cancelled = false;
    void request<{ stream_token: string; expires_in: number }>("/intraday/subscribe", { method: "POST" })
      .then((payload) => {
        if (cancelled || !payload.stream_token) return;
        const normalizedBase = API_BASE.replace(/\/$/, "");
        const apiBase = normalizedBase.endsWith("/api") ? normalizedBase : `${normalizedBase}/api`;
        const url = `${apiBase}/intraday/key-levels/stream?symbols=${encodeURIComponent(symbols.join(","))}&entry_zones=${encodeURIComponent(keyLevelEntryZonesKey)}&client_id=web-monitor-key-levels&stream_token=${encodeURIComponent(payload.stream_token)}&interval_seconds=20&feishu=true`;
        source = new EventSource(url);
        source.addEventListener("intraday_key_levels", (event) => {
          try {
            const payload = JSON.parse((event as MessageEvent).data) as { alerts?: IntradayKeyLevelResponse[] };
            setKeyLevelAlerts(payload.alerts ?? []);
          } catch {
            setKeyLevelAlerts([]);
          }
        });
        source.onerror = () => source?.close();
      })
      .catch(() => setKeyLevelAlerts([]));
    return () => {
      cancelled = true;
      source?.close();
    };
  }, [active, keyLevelSymbolsKey, keyLevelEntryZonesKey]);

  useEffect(() => () => stopInstrumentSyncPolling(), [stopInstrumentSyncPolling]);

  return {
    priorityBoard,
    setPriorityBoard,
    marketBreadth,
    sectorRelativeStrength,
    keyLevelAlerts,
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
