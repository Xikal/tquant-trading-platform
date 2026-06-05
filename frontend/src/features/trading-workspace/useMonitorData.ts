import { useCallback, useEffect, useMemo, useRef } from "react";
import { API_BASE, bffPartialErrorsText, getAdminApiToken, invalidateCache, request } from "../../api/base";
import { api } from "../../api/client";
import { useWorkspaceMonitorStore } from "../../stores/workspaceMonitorStore";
import { seedLiveQuoteSignal, updateLiveQuoteSignal } from "../../state/realtime/liveQuoteSignals";
import { useQuoteStream } from "../../state/realtime/useQuoteStream";
import { useServerState } from "../../state/serverState";
import type {
  LowBuyPriorityBoardResult,
  LowBuyPriorityBoardItem,
  LowBuyQuoteRefreshItem,
  InstrumentSyncStatus,
  IntradayMarketPulse,
  MarketBreadth,
  MarketHourlySnapshotHistoryItem,
  MarketReviewReport,
  MarketReviewStatus,
  IntradayKeyLevelResponse,
  PairedHedgeResearchResponse,
  RuntimeStatus,
  SectorEtfT0Response,
  SectorRelativeStrengthResponse,
  StrategyVariant,
  WatchlistSignal,
} from "../../types";
import { DEFAULT_PLAYBOOK_STRATEGY } from "../workspace-shared/workspaceConstants";
import { errorMessage } from "../workspace-shared/workspaceFormatters";
import type { StockCardView } from "../workspace-shared/workspaceTypes";
import { priorityToCard, watchSignalToCard } from "../workspace-shared/workspaceViewModels";
import { filterTodayConfirmedPriorityItems } from "../workspace-shared/todayRecommendations";
import {
  applyPriorityBoardQuoteRefresh,
  applySectorEtfQuoteRefresh,
  applyWatchlistQuoteRefresh,
  collectPrioritySymbolsByStrategy,
  realtimePriceRefreshIntervalMs,
  refreshTradingSessionStatus,
  shouldRefreshRealtimePrices,
} from "./realtimePriceRefresh";
import { createStableCardListMapper } from "./stableMonitorCards";
import { isMonitorBffDisabled, useMonitorWorkspaceBff } from "./useMonitorWorkspaceBff";

const MONITOR_SERVER_KEYS = {
  priorityBoard: ["monitor", "priority-board"] as const,
  marketBreadth: ["monitor", "market-breadth"] as const,
  marketPulse: ["monitor", "market-pulse"] as const,
  hourlySnapshotHistory: ["monitor", "hourly-snapshot-history"] as const,
  reviewStatus: ["monitor", "review-status"] as const,
  reviewReports: ["monitor", "review-reports"] as const,
  sectorRelativeStrength: ["monitor", "sector-relative-strength"] as const,
  keyLevelAlerts: ["monitor", "key-level-alerts"] as const,
  watchlistSignals: ["monitor", "watchlist-signals"] as const,
  sectorEtfT0: ["monitor", "sector-etf-t0"] as const,
  pairedHedge: ["monitor", "paired-hedge"] as const,
  runtime: ["monitor", "runtime"] as const,
  instrumentSyncStatus: ["monitor", "instrument-sync-status"] as const,
};

const MONITOR_BFF_RETRYING_MESSAGE = "加载失败，正在重试… 已保留上次可用数据，接口恢复后会自动更新。";
const MONITOR_PENDING_REFRESH_DELAYS_MS = [3_000, 5_000, 8_000, 13_000, 20_000, 30_000];

type WithLoading = <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;

function isMonitorAuthError(reason: unknown): boolean {
  const status = (reason as { status?: number } | null)?.status;
  if (status !== undefined) {
    return status === 401;
  }
  const message = errorMessage(reason).toLowerCase();
  return message.includes("401") || message.includes("unauthorized") || message.includes("not authenticated");
}

interface UseMonitorDataOptions {
  active: boolean;
  withLoading: WithLoading;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
  onAuthRequired: () => void;
}

export function useMonitorData({ active, withLoading, setError, setNotice, onAuthRequired }: UseMonitorDataOptions) {
  const onAuthRequiredRef = useRef(onAuthRequired);
  useEffect(() => {
    onAuthRequiredRef.current = onAuthRequired;
  }, [onAuthRequired]);
  const [priorityBoard, setPriorityBoard, resetPriorityBoard] = useServerState<LowBuyPriorityBoardResult | null>(MONITOR_SERVER_KEYS.priorityBoard, null);
  const [marketBreadth, setMarketBreadth, resetMarketBreadth] = useServerState<MarketBreadth | null>(MONITOR_SERVER_KEYS.marketBreadth, null);
  const [marketPulse, setMarketPulse, resetMarketPulse] = useServerState<IntradayMarketPulse | null>(MONITOR_SERVER_KEYS.marketPulse, null);
  const [hourlySnapshotHistory, setHourlySnapshotHistory, resetHourlySnapshotHistory] = useServerState<MarketHourlySnapshotHistoryItem[]>(MONITOR_SERVER_KEYS.hourlySnapshotHistory, []);
  const [reviewStatus, setReviewStatus, resetReviewStatus] = useServerState<MarketReviewStatus | null>(MONITOR_SERVER_KEYS.reviewStatus, null);
  const [reviewReports, setReviewReports, resetReviewReports] = useServerState<MarketReviewReport[]>(MONITOR_SERVER_KEYS.reviewReports, []);
  const [sectorRelativeStrength, setSectorRelativeStrength, resetSectorRelativeStrength] = useServerState<SectorRelativeStrengthResponse | null>(MONITOR_SERVER_KEYS.sectorRelativeStrength, null);
  const [keyLevelAlerts, setKeyLevelAlerts, resetKeyLevelAlerts] = useServerState<IntradayKeyLevelResponse[]>(MONITOR_SERVER_KEYS.keyLevelAlerts, []);
  const [watchlistSignals, setWatchlistSignals, resetWatchlistSignals] = useServerState<WatchlistSignal[]>(MONITOR_SERVER_KEYS.watchlistSignals, []);
  const [sectorEtfT0, setSectorEtfT0, resetSectorEtfT0] = useServerState<SectorEtfT0Response | null>(MONITOR_SERVER_KEYS.sectorEtfT0, null);
  const [pairedHedge, setPairedHedge, resetPairedHedge] = useServerState<PairedHedgeResearchResponse | null>(MONITOR_SERVER_KEYS.pairedHedge, null);
  const [runtime, setRuntime, resetRuntime] = useServerState<RuntimeStatus | null>(MONITOR_SERVER_KEYS.runtime, null);
  const [instrumentSyncStatus, setInstrumentSyncStatus, resetInstrumentSyncStatus] = useServerState<InstrumentSyncStatus | null>(MONITOR_SERVER_KEYS.instrumentSyncStatus, null);
  const resetMonitorState = useWorkspaceMonitorStore((state) => state.resetMonitorData);
  const monitorRefreshRef = useRef(false);
  const quoteRefreshRef = useRef(false);
  const instrumentSyncPollRef = useRef<number | null>(null);
  const instrumentSyncRunIdRef = useRef<string>("");
  const pendingRetryTimerRef = useRef<number | null>(null);
  const pendingRetryCountRef = useRef(0);
  const keyLevelStreamOpenedRef = useRef(false);
  const priorityBoardRef = useRef<LowBuyPriorityBoardResult | null>(null);
  const laneBoardsRef = useRef<Partial<Record<StrategyVariant, LowBuyPriorityBoardResult>>>({});
  const watchlistSignalsRef = useRef<WatchlistSignal[]>([]);
  const sectorEtfT0Ref = useRef<SectorEtfT0Response | null>(null);
  const priorityCardMapperRef = useRef(createStableCardListMapper<LowBuyPriorityBoardItem>({
    keyOf: priorityCardKey,
    signatureOf: monitorCardSignature,
    mapItem: priorityToCard,
  }));
  const watchCardMapperRef = useRef(createStableCardListMapper<WatchlistSignal>({
    keyOf: (item) => item.symbol,
    signatureOf: monitorCardSignature,
    mapItem: watchSignalToCard,
  }));
  const monitorWorkspaceBff = useMonitorWorkspaceBff();

  const priorityCards: StockCardView[] = useMemo(
    () => priorityCardMapperRef.current(filterTodayConfirmedPriorityItems(priorityBoard)),
    [priorityBoard]
  );
  const visiblePriorityItems = useMemo(
    () => filterTodayConfirmedPriorityItems(priorityBoard),
    [priorityBoard]
  );
  const watchCards: StockCardView[] = useMemo(
    () => watchCardMapperRef.current(watchlistSignals),
    [watchlistSignals]
  );
  const keyLevelSymbols = useMemo(() => [...new Set([
    ...visiblePriorityItems.slice(0, 8).map((item) => item.symbol),
    ...watchlistSignals.slice(0, 8).map((item) => item.symbol),
  ].filter(Boolean))].slice(0, 16), [visiblePriorityItems, watchlistSignals]);
  const keyLevelSymbolsKey = keyLevelSymbols.join(",");
  const liveQuoteSymbols = useMemo(() => [...new Set([
    ...visiblePriorityItems.map((item) => item.symbol),
    ...watchlistSignals.map((item) => item.symbol),
    ...(sectorEtfT0?.opportunities ?? []).map((item) => item.etf_symbol),
  ].filter(Boolean))], [visiblePriorityItems, sectorEtfT0?.opportunities, watchlistSignals]);
  const keyLevelEntryZonesKey = useMemo(() => visiblePriorityItems
    .slice(0, 8)
    .filter((item) => item.entry_zone_low > 0 && item.entry_zone_high > 0)
    .map((item) => `${item.symbol}:${item.entry_zone_low}:${item.entry_zone_high}`)
    .join(";"), [visiblePriorityItems]);

  useEffect(() => {
    priorityBoardRef.current = priorityBoard;
  }, [priorityBoard]);

  useEffect(() => {
    watchlistSignalsRef.current = watchlistSignals;
  }, [watchlistSignals]);

  useEffect(() => {
    sectorEtfT0Ref.current = sectorEtfT0;
  }, [sectorEtfT0]);

  useEffect(() => {
    for (const item of visiblePriorityItems) {
      seedLiveQuoteSignal(item.symbol, {
        price: item.latest_price,
        changePct: item.change_pct,
        signalState: item.buy_signal_state,
      });
    }
  }, [visiblePriorityItems]);

  useEffect(() => {
    for (const item of watchlistSignals) {
      seedLiveQuoteSignal(item.symbol, {
        price: item.quote.last_price,
        changePct: item.quote.change_pct,
        signalState: item.signal.action,
      });
    }
  }, [watchlistSignals]);

  useEffect(() => {
    for (const item of sectorEtfT0?.opportunities ?? []) {
      seedLiveQuoteSignal(item.etf_symbol, {
        price: item.last_price,
        changePct: item.change_pct,
        signalState: item.bias,
      });
    }
  }, [sectorEtfT0?.opportunities]);

  const clearPendingRetry = useCallback(() => {
    if (pendingRetryTimerRef.current != null) {
      window.clearTimeout(pendingRetryTimerRef.current);
      pendingRetryTimerRef.current = null;
    }
  }, []);

  const fetchLegacyMonitorData = useCallback(async (includeRuntime: boolean) => {
    const shouldLoadRuntime = includeRuntime && Boolean(getAdminApiToken());
    const requests = [
      api.getMonitorSnapshot(12),
      api.getMarketBreadth(),
      api.getMarketHourlySnapshotsHistory(8),
      api.getSectorRelativeStrength(8, 8),
      api.getSectorEtfT0(8),
      api.getPairedHedgeResearch(4),
      api.getMarketReviewSummary(),
      shouldLoadRuntime ? api.getRuntimeStatus() : Promise.resolve(null),
    ] as const;
    const [
      snapshotResult,
      breadthResult,
      hourlyHistoryResult,
      sectorStrengthResult,
      sectorEtfResult,
      pairedHedgeResult,
      reviewResult,
      runtimeResult,
    ] = await Promise.allSettled(requests);
    if (snapshotResult.status === "fulfilled") {
      setPriorityBoard(snapshotResult.value.priority_board);
      laneBoardsRef.current.baseline = snapshotResult.value.priority_board;
      setWatchlistSignals(snapshotResult.value.watchlist_signals);
      setSectorEtfT0(snapshotResult.value.sector_etf_t0 ?? null);
    }
    if (breadthResult.status === "fulfilled") setMarketBreadth(breadthResult.value);
    if (hourlyHistoryResult.status === "fulfilled") setHourlySnapshotHistory(hourlyHistoryResult.value.items ?? []);
    if (sectorStrengthResult.status === "fulfilled") setSectorRelativeStrength(sectorStrengthResult.value);
    if (sectorEtfResult.status === "fulfilled") setSectorEtfT0(sectorEtfResult.value);
    if (pairedHedgeResult.status === "fulfilled") setPairedHedge(pairedHedgeResult.value);
    if (reviewResult.status === "fulfilled") {
      setReviewStatus(reviewResult.value.review_status);
      setReviewReports(reviewResult.value.review_reports ?? []);
    }
    if (runtimeResult.status === "fulfilled" && runtimeResult.value) setRuntime(runtimeResult.value);
    const rejections = [
      snapshotResult,
      breadthResult,
      hourlyHistoryResult,
      sectorStrengthResult,
      sectorEtfResult,
      pairedHedgeResult,
      reviewResult,
      runtimeResult,
    ].filter((item): item is PromiseRejectedResult => item.status === "rejected");
    if (rejections.some((item) => isMonitorAuthError(item.reason))) {
      onAuthRequiredRef.current();
      return;
    }
    if (rejections.length > 0) {
      setError(errorMessage(rejections[0].reason));
    }
  }, [
    setError,
    setHourlySnapshotHistory,
    setMarketBreadth,
    setPairedHedge,
    setPriorityBoard,
    setReviewReports,
    setReviewStatus,
    setRuntime,
    setSectorEtfT0,
    setSectorRelativeStrength,
    setWatchlistSignals,
  ]);

  const fetchMonitorData = useCallback(async (includeRuntime: boolean) => {
    if (monitorRefreshRef.current) {
      return;
    }
    monitorRefreshRef.current = true;
    try {
      if (!monitorWorkspaceBff.aggregateEnabled) {
        await fetchLegacyMonitorData(includeRuntime);
        return;
      }
      const workspaceResult = await Promise.resolve(monitorWorkspaceBff.fetchMonitorWorkspace(12))
        .then((value) => ({ status: "fulfilled" as const, value }))
        .catch((reason) => ({ status: "rejected" as const, reason }));
      if (workspaceResult.status === "rejected" && isMonitorBffDisabled(workspaceResult.reason)) {
        await fetchLegacyMonitorData(includeRuntime);
        return;
      }
      if (workspaceResult.status === "rejected") {
        if (isMonitorAuthError(workspaceResult.reason)) {
          onAuthRequiredRef.current();
          return;
        }
        setError(MONITOR_BFF_RETRYING_MESSAGE);
        return;
      }
      let hourlyHistoryLoadedFromBff = false;
      let runtimeLoadedFromBff = !includeRuntime || !Boolean(getAdminApiToken());
      const partialWarnings = bffPartialErrorsText(workspaceResult.value);
      if (partialWarnings) {
        setNotice(`监控合包部分降级：${partialWarnings}`);
      }
      const monitorSnapshot = workspaceResult.value.monitor_snapshot;
      if (monitorSnapshot) {
        setPriorityBoard(monitorSnapshot.priority_board);
        laneBoardsRef.current.baseline = monitorSnapshot.priority_board;
        setWatchlistSignals(monitorSnapshot.watchlist_signals);
        setSectorEtfT0(monitorSnapshot.sector_etf_t0 ?? null);
      }
      if (workspaceResult.value.market_breadth) {
        setMarketBreadth(workspaceResult.value.market_breadth);
      }
      setMarketPulse(workspaceResult.value.market_pulse ?? null);
      setReviewStatus(workspaceResult.value.review_status ?? null);
      setReviewReports(workspaceResult.value.review_reports ?? []);
      if (workspaceResult.value.sector_relative_strength) {
        setSectorRelativeStrength(workspaceResult.value.sector_relative_strength);
      }
      if (workspaceResult.value.paired_hedge) {
        setPairedHedge(workspaceResult.value.paired_hedge);
      }
      if (Array.isArray(workspaceResult.value.hourly_snapshot_history)) {
        setHourlySnapshotHistory(workspaceResult.value.hourly_snapshot_history);
        hourlyHistoryLoadedFromBff = true;
      }
      if ("runtime" in workspaceResult.value) {
        runtimeLoadedFromBff = true;
      }
      if (workspaceResult.value.runtime) {
        setRuntime(workspaceResult.value.runtime);
      }
      const fallbackRequests: Promise<unknown>[] = [];
      if (!hourlyHistoryLoadedFromBff) {
        fallbackRequests.push(api.getMarketHourlySnapshotsHistory(8));
      }
      if (!runtimeLoadedFromBff && includeRuntime && Boolean(getAdminApiToken())) {
        fallbackRequests.push(api.getRuntimeStatus());
      }
      const fallbackResults = await Promise.allSettled(fallbackRequests);
      for (const result of fallbackResults) {
        if (result.status !== "fulfilled") {
          continue;
        }
        if (isHourlyHistoryResponse(result.value)) {
          setHourlySnapshotHistory(result.value.items ?? []);
        } else if (isRuntimeStatus(result.value)) {
          setRuntime(result.value);
        }
      }
      const rejections = [workspaceResult, ...fallbackResults].filter(
        (item): item is PromiseRejectedResult => item.status === "rejected"
      );
      // 会话过期：401 必须触发登出，否则轮询会无限刷 401（清登录态后轮询随 currentUser 置空而停止）。
      if (rejections.some((item) => isMonitorAuthError(item.reason))) {
        onAuthRequiredRef.current();
        return;
      }
      if (rejections.length > 0) {
        setError(errorMessage(rejections[0].reason));
      }
    } finally {
      monitorRefreshRef.current = false;
    }
  }, [
    fetchLegacyMonitorData,
    monitorWorkspaceBff,
    setError,
    setHourlySnapshotHistory,
    setMarketBreadth,
    setMarketPulse,
    setPairedHedge,
    setPriorityBoard,
    setReviewReports,
    setReviewStatus,
    setRuntime,
    setSectorEtfT0,
    setSectorRelativeStrength,
    setWatchlistSignals,
  ]);

  const refreshMonitor = useCallback(async () => {
    await withLoading("monitor", () => fetchMonitorData(true));
  }, [fetchMonitorData, withLoading]);

  const loadPriorityLane = useCallback(async (strategyVariant: StrategyVariant) => {
    if (strategyVariant === "baseline") {
      const cached = laneBoardsRef.current.baseline;
      if (cached) {
        setPriorityBoard(cached);
        return;
      }
      await refreshMonitor();
      return;
    }
    await withLoading("priority-lane", async () => {
      const payload = await api.getLowBuyPriorityBoard(12, strategyVariant);
      laneBoardsRef.current[strategyVariant] = payload;
      setPriorityBoard(payload);
    });
  }, [refreshMonitor, setPriorityBoard, withLoading]);

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
    resetPriorityBoard();
    resetMarketBreadth();
    resetMarketPulse();
    resetHourlySnapshotHistory();
    resetReviewStatus();
    resetReviewReports();
    resetSectorRelativeStrength();
    resetKeyLevelAlerts();
    resetWatchlistSignals();
    resetSectorEtfT0();
    resetPairedHedge();
    resetRuntime();
    resetInstrumentSyncStatus();
    resetMonitorState();
  }, [
    clearPendingRetry,
    resetHourlySnapshotHistory,
    resetInstrumentSyncStatus,
    resetKeyLevelAlerts,
    resetMarketBreadth,
    resetMarketPulse,
    resetMonitorState,
    resetPairedHedge,
    resetPriorityBoard,
    resetReviewReports,
    resetReviewStatus,
    resetRuntime,
    resetSectorEtfT0,
    resetSectorRelativeStrength,
    resetWatchlistSignals,
  ]);

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
    if (pendingRetryCountRef.current >= MONITOR_PENDING_REFRESH_DELAYS_MS.length) {
      return undefined;
    }
    clearPendingRetry();
    const retryDelay = MONITOR_PENDING_REFRESH_DELAYS_MS[pendingRetryCountRef.current] ?? 30_000;
    pendingRetryTimerRef.current = window.setTimeout(() => {
      pendingRetryCountRef.current += 1;
      invalidateCache(["/bff/v1/workspace/monitor"]);
      void fetchMonitorData(false);
    }, retryDelay);
    return () => clearPendingRetry();
  }, [active, clearPendingRetry, fetchMonitorData, priorityBoard]);

  const refreshRealtimeQuotes = useCallback(async () => {
    if (!shouldRefreshRealtimePrices() || quoteRefreshRef.current) {
      return;
    }
    const currentBoard = priorityBoardRef.current;
    const currentWatchlist = watchlistSignalsRef.current;
    const currentEtfT0 = sectorEtfT0Ref.current;
    const priorityGroups = collectPrioritySymbolsByStrategy(filterTodayConfirmedPriorityItems(currentBoard));
    const etfSymbols = [...new Set((currentEtfT0?.opportunities ?? []).map((item) => item.etf_symbol).filter(Boolean))];
    if (!priorityGroups.length && !currentWatchlist.length && !etfSymbols.length) {
      return;
    }
    quoteRefreshRef.current = true;
    try {
      const priorityResults = await Promise.allSettled(
        priorityGroups.map(({ strategy, symbols }) => api.getLowBuyQuoteRefresh(strategy, symbols)),
      );
      const priorityQuoteMap = priorityResults.reduce<Record<string, LowBuyQuoteRefreshItem>>((acc, result) => {
        if (result.status === "fulfilled") {
          Object.assign(acc, result.value.items);
        }
        return acc;
      }, {});
      if (useLiveQuoteSignals()) {
        for (const [symbol, quote] of Object.entries(priorityQuoteMap)) {
          updateLiveQuoteSignal(symbol, {
            price: quote.latest_price,
            changePct: quote.change_pct,
            signalState: quote.buy_signal_state,
          });
        }
      } else if (currentBoard && Object.keys(priorityQuoteMap).length) {
        setPriorityBoard((board) => (board ? applyPriorityBoardQuoteRefresh(board, priorityQuoteMap) : board));
      }

      if (currentWatchlist.length) {
        const watchlistQuotes = await api.getWatchlistQuotes();
        if (watchlistQuotes.length) {
          if (useLiveQuoteSignals()) {
            for (const item of watchlistQuotes) {
              updateLiveQuoteSignal(item.symbol, {
                price: item.quote.last_price,
                changePct: item.quote.change_pct,
              });
            }
          } else {
            setWatchlistSignals((signals) => applyWatchlistQuoteRefresh(signals, watchlistQuotes));
          }
        }
      }

      if (etfSymbols.length) {
        const etfQuotes = await api.getLowBuyQuoteRefresh(DEFAULT_PLAYBOOK_STRATEGY, etfSymbols);
        if (useLiveQuoteSignals()) {
          for (const [symbol, quote] of Object.entries(etfQuotes.items)) {
            updateLiveQuoteSignal(symbol, {
              price: quote.latest_price,
              changePct: quote.change_pct,
              signalState: quote.buy_signal_state,
            });
          }
        } else {
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
  }, [setPriorityBoard, setSectorEtfT0, setWatchlistSignals]);

  useQuoteStream({
    active,
    symbols: liveQuoteSymbols,
    fallbackPoll: refreshRealtimeQuotes,
  });

  useEffect(() => {
    if (!active) {
      return undefined;
    }
    if (useLiveQuoteSignals()) {
      return undefined;
    }
    let cancelled = false;
    let timer: number | undefined;
    const scheduleNext = () => {
      void refreshTradingSessionStatus(api.getMarketTradingSession).finally(() => {
        if (cancelled) {
          return;
        }
        timer = window.setTimeout(() => {
          void refreshRealtimeQuotes().finally(() => {
            if (!cancelled) {
              scheduleNext();
            }
          });
        }, realtimePriceRefreshIntervalMs());
      });
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void refreshRealtimeQuotes();
      }
    };
    void refreshTradingSessionStatus(api.getMarketTradingSession).finally(() => {
      if (!cancelled) {
        void refreshRealtimeQuotes();
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
  }, [active, refreshRealtimeQuotes]);

  useEffect(() => {
    if (!active) {
      keyLevelStreamOpenedRef.current = false;
      setKeyLevelAlerts([]);
      return undefined;
    }
    const symbols = keyLevelSymbolsKey ? keyLevelSymbolsKey.split(",") : [];
    if (!symbols.length) {
      keyLevelStreamOpenedRef.current = false;
      setKeyLevelAlerts([]);
      return undefined;
    }
    if (keyLevelStreamOpenedRef.current) {
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
        keyLevelStreamOpenedRef.current = true;
        source.addEventListener("intraday_key_levels", (event) => {
          try {
            const payload = JSON.parse((event as MessageEvent).data) as { alerts?: IntradayKeyLevelResponse[] };
            setKeyLevelAlerts(payload.alerts ?? []);
          } catch {
            setKeyLevelAlerts([]);
          }
        });
        source.onerror = () => {
          keyLevelStreamOpenedRef.current = false;
          source?.close();
        };
      })
      .catch(() => {
        keyLevelStreamOpenedRef.current = false;
        setKeyLevelAlerts([]);
      });
    return () => {
      cancelled = true;
      keyLevelStreamOpenedRef.current = false;
      source?.close();
    };
  }, [active, keyLevelSymbolsKey, keyLevelEntryZonesKey]);

  useEffect(() => () => stopInstrumentSyncPolling(), [stopInstrumentSyncPolling]);

  return {
    priorityBoard,
    setPriorityBoard,
    marketBreadth,
    marketPulse,
    hourlySnapshotHistory,
    reviewStatus,
    reviewReports,
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
    loadPriorityLane,
    syncInstruments,
    resetMonitorData,
  };
}

function isHourlyHistoryResponse(value: unknown): value is { items?: MarketHourlySnapshotHistoryItem[] } {
  return Boolean(value && typeof value === "object" && "items" in value);
}

function isRuntimeStatus(value: unknown): value is RuntimeStatus {
  return Boolean(value && typeof value === "object" && "ready_checks" in value);
}

function isPendingMonitorSnapshot(priorityBoard: LowBuyPriorityBoardResult | null): boolean {
  if (!priorityBoard) {
    return false;
  }
  if (priorityBoard.refresh_queued || priorityBoard.stale) {
    return true;
  }
  const warning = `${priorityBoard.snapshot_warning ?? ""} ${priorityBoard.data_quality_text ?? ""}`;
  return warning.includes("已排队") || warning.includes("后台刷新中");
}

function priorityCardKey(item: LowBuyPriorityBoardItem): string {
  return [
    item.symbol,
    item.strategy_key,
    item.display_lane ?? "",
  ].join(":");
}

function monitorCardSignature(item: unknown): string {
  return JSON.stringify(item);
}

function useLiveQuoteSignals(): boolean {
  return import.meta.env.VITE_LIVE_QUOTE_SIGNALS !== "false";
}
