import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { appApi } from "../../api/appClient";
import { api } from "../../api/client";
import { API_BASE, getAdminApiToken, getAuthAccessToken, request } from "../../api/base";
import { applyQuoteRefreshToResponse } from "../playbook/formatters";
import type {
  AiDecisionSupportResponse,
  AnalysisResponse,
  AuthUser,
  BacktestResult,
  BacktestRun,
  LowBuyExecutionBacktestResult,
  IntradayConfirmationItem,
  LowBuyPriorityBoardResult,
  LowBuyScreenerResult,
  LowBuyTradeLifecycle,
  MarketBreadth,
  ReplayItem,
  RuntimeStatus,
  StrategyValidationReport,
  WatchlistSignal,
} from "../../types";
import { LoginPage } from "./LoginPage";
import { Topbar } from "./Topbar";
import { AiInsightDialog, ErrorDialog, StatusStrip, StockDetailDialog } from "./WorkspaceComponents";
import { DEFAULT_PLAYBOOK_STRATEGY, MONITOR_REFRESH_INTERVAL_MS, PAGE_PATHS, PLAYBOOK_QUOTE_REFRESH_INTERVAL_MS, PLAYBOOK_QUOTE_REFRESH_LIMIT } from "./workspaceConstants";
import { errorMessage, nullableNumber, parseNumber } from "./workspaceFormatters";
import { pageFromLocation } from "./workspaceRoutes";
import { activeLoadingKey, clearLoadingKeys, isLoading, setLoadingFlag, type LoadingState } from "./loadingState";
import { PageErrorBoundary } from "./PageErrorBoundary";
import type {
  AnalysisDraft,
  AuthDraft,
  BacktestDraft,
  Page,
  StockCardView,
  WatchDraft,
} from "./workspaceTypes";
import { priorityToCard, trackedPlaybookSymbols, watchSignalToCard } from "./workspaceViewModels";
import { usePaperTrading } from "./usePaperTrading";
import { useSettingsData } from "./useSettingsData";

const AnalysisPage = lazy(async () => ({ default: (await import("./AnalysisPage")).AnalysisPage }));
const MonitorPage = lazy(async () => ({ default: (await import("./MonitorPage")).MonitorPage }));
const PaperTradingPage = lazy(async () => ({ default: (await import("./PaperTradingPage")).PaperTradingPage }));
const PerformanceDashboard = lazy(async () => ({ default: (await import("./PerformanceDashboard")).PerformanceDashboard }));
const PlaybookPage = lazy(async () => ({ default: (await import("./PlaybookPage")).PlaybookPage }));
const ResearchPage = lazy(async () => ({ default: (await import("./ResearchPage")).ResearchPage }));
const SettingsPage = lazy(async () => ({ default: (await import("./SettingsPage")).SettingsPage }));

const PAPER_LOADING_KEYS = [
  "paper",
  "paper-refresh",
  "paper-quotes",
  "paper-status",
  "paper-order",
  "paper-tags",
];

export function TradingWorkspace() {
  const [authReady, setAuthReady] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [page, setPage] = useState<Page>(() => pageFromLocation());
  const [priorityBoard, setPriorityBoard] = useState<LowBuyPriorityBoardResult | null>(null);
  const [marketBreadth, setMarketBreadth] = useState<MarketBreadth | null>(null);
  const [watchlistSignals, setWatchlistSignals] = useState<WatchlistSignal[]>([]);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [playbookStrategy, setPlaybookStrategy] = useState(DEFAULT_PLAYBOOK_STRATEGY);
  const [playbook, setPlaybook] = useState<LowBuyScreenerResult | null>(null);
  const [playbookCache, setPlaybookCache] = useState<Record<string, LowBuyScreenerResult>>({});
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const [aiResult, setAiResult] = useState<AiDecisionSupportResponse | null>(null);
  const [aiDialogOpen, setAiDialogOpen] = useState(false);
  const [replays, setReplays] = useState<ReplayItem[]>([]);
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [backtestRuns, setBacktestRuns] = useState<BacktestRun[]>([]);
  const [executionBacktest, setExecutionBacktest] = useState<LowBuyExecutionBacktestResult | null>(null);
  const [strategyValidation, setStrategyValidation] = useState<StrategyValidationReport | null>(null);
  const [intradayConfirmations, setIntradayConfirmations] = useState<IntradayConfirmationItem[]>([]);
  const [tradeLifecycles, setTradeLifecycles] = useState<LowBuyTradeLifecycle[]>([]);
  const [researchBoard, setResearchBoard] = useState<LowBuyPriorityBoardResult | null>(null);
  const [loadingState, setLoadingState] = useState<LoadingState>({});
  const loading = activeLoadingKey(loadingState);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [selectedStock, setSelectedStock] = useState<StockCardView | null>(null);
  const playbookRequestRef = useRef(0);
  const monitorRefreshRef = useRef(false);
  const [authDraft, setAuthDraft] = useState<AuthDraft>({
    username: "",
    password: "",
    remember: true,
  });
  const paper = usePaperTrading({
    setError,
    setLoading: setPaperLoading,
    setNotice,
    onAuthRequired: handleAuthRequired,
  });
  const settingsData = useSettingsData({
    withLoading,
    setError,
    setNotice,
    setRuntime,
  });

  const [watchDraft, setWatchDraft] = useState<WatchDraft>({
    symbol: "",
    name: "",
    base_position: "0",
    available_position: "0",
    cost_basis: "",
    memo: "",
  });
  const [analysisDraft, setAnalysisDraft] = useState<AnalysisDraft>({
    symbol: "510300",
    prefer_strategy: "auto",
    base_position: "3000",
    available_position: "3000",
    cost_basis: "",
  });
  const [backtestDraft, setBacktestDraft] = useState<BacktestDraft>({
    symbol: "300059",
    bar_period: "5m",
    lookback_bars: "480",
    initial_position: "1000",
    walk_forward_windows: "4",
    low_buy_strategy: DEFAULT_PLAYBOOK_STRATEGY,
    low_buy_lookback_days: "60",
    low_buy_limit: "160",
  });
  useEffect(() => {
    void restoreSession();
  }, []);

  useEffect(() => {
    if (authReady && currentUser) {
      void refreshMonitor();
    }
  }, [authReady, currentUser?.id]);

  useEffect(() => {
    if (!notice) {
      return undefined;
    }
    const timer = window.setTimeout(() => setNotice(""), 3500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    function handlePopState() {
      setPage(pageFromLocation());
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    if (!currentUser) {
      return;
    }
    if (page === "playbook") {
      void loadPlaybook(playbookStrategy);
    }
    if (page === "research") {
      void loadResearch();
    }
    if (page === "settings") {
      void settingsData.loadSettings();
    }
    if (page === "paper") {
      void paper.load();
    }
  }, [currentUser, page, playbookStrategy]);

  useEffect(() => {
    if (!currentUser || page !== "monitor") {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void fetchMonitorData(false);
    }, MONITOR_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [currentUser, page]);

  useEffect(() => {
    if (!currentUser || page !== "playbook" || !playbook) {
      return undefined;
    }
    const currentPlaybook = playbook;
    let active = true;
    let refreshing = false;
    async function refreshPlaybookQuotes() {
      if (refreshing) {
        return;
      }
      const symbols = trackedPlaybookSymbols(currentPlaybook).slice(0, PLAYBOOK_QUOTE_REFRESH_LIMIT);
      if (!symbols.length) {
        return;
      }
      refreshing = true;
      try {
        const result = await api.getLowBuyQuoteRefresh(playbookStrategy, symbols);
        if (active) {
          setPlaybook((current) =>
            current ? applyQuoteRefreshToResponse(current, result.items) : current
          );
        }
      } catch (err) {
        if (import.meta.env.DEV) {
          console.warn("低吸实时价格刷新失败，已保留上次结果。", err);
        }
      } finally {
        refreshing = false;
      }
    }
    const timer = window.setInterval(() => {
      void refreshPlaybookQuotes();
    }, PLAYBOOK_QUOTE_REFRESH_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [
    page,
    currentUser,
    playbookStrategy,
    playbook?.latest_trade_date,
    playbook?.strategy_key,
    playbook?.confirmed_candidates.length,
    playbook?.candidates.length,
  ]);

  const priorityCards = useMemo(
    () => (priorityBoard?.items ?? []).map(priorityToCard),
    [priorityBoard]
  );
  const watchCards = useMemo(
    () => watchlistSignals.map(watchSignalToCard),
    [watchlistSignals]
  );
  const paperPositionSymbols = useMemo(
    () => paper.positions.map((item) => item.symbol).filter(Boolean).slice(0, 12).join(","),
    [paper.positions]
  );

  useEffect(() => {
    let source: EventSource | undefined;
    let cancelled = false;
    if (!currentUser || page !== "paper" || !paperPositionSymbols) {
      setIntradayConfirmations([]);
      return undefined;
    }
    if (!getAuthAccessToken()) {
      setIntradayConfirmations([]);
      return undefined;
    }
    void request<{ stream_token: string; expires_in: number }>("/intraday/subscribe", { method: "POST" }).then((payload) => {
      if (cancelled || !payload.stream_token) {
        return;
      }
      const normalizedBase = API_BASE.replace(/\/$/, "");
      const agentBase = normalizedBase.endsWith("/api") ? normalizedBase : `${normalizedBase}/api`;
      const url = `${agentBase}/intraday/stream?symbols=${encodeURIComponent(paperPositionSymbols)}&client_id=web-paper&stream_token=${encodeURIComponent(payload.stream_token)}&interval_seconds=20`;
      source = new EventSource(url);
      source.addEventListener("intraday_confirmations", (event) => {
        try {
          const payload = JSON.parse((event as MessageEvent).data) as { items?: IntradayConfirmationItem[] };
          setIntradayConfirmations(payload.items ?? []);
        } catch {
          setIntradayConfirmations([]);
        }
      });
      source.onerror = () => {
        source?.close();
      };
    }).catch(() => setIntradayConfirmations([]));
    return () => {
      cancelled = true;
      source?.close();
    };
  }, [currentUser, page, paperPositionSymbols]);

  useEffect(() => {
    if (!currentUser || page !== "paper" || !currentUser.can_paper_trade) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void paper.refreshAutoTradingStatus();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [currentUser, page, currentUser?.can_paper_trade]);

  async function withLoading<T>(key: string, action: () => Promise<T>): Promise<T | undefined> {
    try {
      setLoadingKey(key, true);
      setError("");
      return await action();
    } catch (err) {
      const message = errorMessage(err);
      setError(message);
      if (isAuthErrorMessage(message)) {
        handleAuthRequired();
      }
      return undefined;
    } finally {
      setLoadingKey(key, false);
    }
  }

  async function restoreSession() {
    try {
      setLoadingKey("auth-restore", true);
      const result = await appApi.refreshAuth();
      setCurrentUser(result.user);
    } catch {
      setCurrentUser(null);
    } finally {
      setLoadingKey("auth-restore", false);
      setAuthReady(true);
    }
  }

  function setLoadingKey(key: string, active: boolean) {
    setLoadingState((current) => setLoadingFlag(current, key, active));
  }

  function setPaperLoading(key: string) {
    setLoadingState((current) => {
      if (!key) {
        return clearLoadingKeys(current, PAPER_LOADING_KEYS);
      }
      return setLoadingFlag(current, key, true);
    });
  }

  async function submitAuth(register: boolean) {
    await withLoading("auth", async () => {
      const username = authDraft.username.trim();
      const password = authDraft.password;
      if (!username || !password) {
        throw new Error("请填写账号和密码");
      }
      const result = register
        ? await appApi.register({ username, password, display_name: username, device_name: "web-workspace" })
        : await appApi.login({ username, password, device_name: "web-workspace" });
      setCurrentUser(result.user);
      setAuthDraft((draft) => ({ ...draft, password: "" }));
      setNotice(register ? "账号已开通，已进入工作台" : "登录成功");
      await fetchMonitorData(true);
    });
  }

  function handleAuthRequired() {
    setCurrentUser(null);
    setPriorityBoard(null);
    setMarketBreadth(null);
    setWatchlistSignals([]);
    setPlaybook(null);
    setPlaybookCache({});
  }

  async function logout() {
    await appApi.logout();
    handleAuthRequired();
    setNotice("已退出登录");
  }

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

  async function loadPlaybook(strategy: string, force = false) {
    const cached = playbookCache[strategy];
    if (cached && !force) {
      setPlaybook(cached);
    }
    await withLoading("playbook", async () => {
      const requestId = ++playbookRequestRef.current;
      const result = await api.getLowBuyCandidates(strategy, 18, 480, false, "full");
      if (requestId === playbookRequestRef.current) {
        setPlaybook(result);
        setPlaybookCache((current) => ({ ...current, [strategy]: result }));
      }
    });
  }

  async function loadResearch() {
    await withLoading("research", async () => {
      const [replayResult, boardResult, lifecycleResult, runResult] = await Promise.allSettled([
        api.listReplays(),
        api.getLowBuyPriorityBoard(18),
        api.getLowBuyLifecycle(undefined, false, 40),
        api.listBacktestRuns(20),
      ]);
      if (replayResult.status === "fulfilled") {
        setReplays(replayResult.value);
      }
      if (boardResult.status === "fulfilled") {
        setResearchBoard(boardResult.value);
      }
      if (lifecycleResult.status === "fulfilled") {
        setTradeLifecycles(lifecycleResult.value.items);
      }
      if (runResult.status === "fulfilled") {
        setBacktestRuns(runResult.value.runs);
      }
      const rejected = [replayResult, boardResult, lifecycleResult, runResult].find(
        (item): item is PromiseRejectedResult => item.status === "rejected"
      );
      if (rejected) {
        setError(errorMessage(rejected.reason));
      }
    });
  }

  async function syncInstruments() {
    await withLoading("sync", async () => {
      const result = await api.syncInstruments();
      setNotice(result.message || "标的同步完成");
      await refreshMonitor();
    });
  }

  async function addWatchlist() {
    await withLoading("watchlist", async () => {
      const symbol = watchDraft.symbol.trim();
      if (!symbol) {
        throw new Error("请填写证券代码");
      }
      await api.upsertWatchlist({
        symbol,
        name: watchDraft.name.trim(),
        base_position: parseNumber(watchDraft.base_position),
        available_position: parseNumber(watchDraft.available_position),
        cost_basis: nullableNumber(watchDraft.cost_basis),
        memo: watchDraft.memo.trim(),
      });
      setNotice("持仓信息已保存");
      setWatchDraft({
        symbol: "",
        name: "",
        base_position: "0",
        available_position: "0",
        cost_basis: "",
        memo: "",
      });
      await fetchMonitorData(true);
    });
  }

  async function removeWatchlist(symbol: string) {
    await withLoading("watchlist", async () => {
      await api.deleteWatchlist(symbol);
      setNotice(`已移除 ${symbol}`);
      await fetchMonitorData(true);
    });
  }

  function editWatchlistFromCard(card: StockCardView) {
    const source = watchlistSignals.find((item) => item.symbol === card.symbol);
    if (!source) {
      setError(`未找到 ${card.symbol} 的持仓记录`);
      return;
    }
    setWatchDraft({
      symbol: source.symbol,
      name: source.name || source.quote.name || card.name,
      base_position: String(source.base_position ?? 0),
      available_position: String(source.available_position ?? 0),
      cost_basis: source.cost_basis == null ? "" : String(source.cost_basis),
      memo: source.memo || "",
    });
    setNotice(`${card.name} 已载入编辑区，修改后点击保存持仓`);
  }

  async function runAnalysis(symbolOverride?: string) {
    const symbol = (symbolOverride ?? analysisDraft.symbol).trim();
    if (!symbol) {
      setError("请填写证券代码");
      return;
    }
    setAnalysisDraft((draft) => ({ ...draft, symbol }));
    navigatePage("analysis");
    await withLoading("analysis", async () => {
      const result = await api.analyze({
        symbol,
        prefer_strategy: analysisDraft.prefer_strategy,
        base_position: parseNumber(analysisDraft.base_position),
        available_position: parseNumber(analysisDraft.available_position),
        cost_basis: nullableNumber(analysisDraft.cost_basis),
        include_ai: false,
        include_events: true,
        include_microstructure: true,
      });
      setAnalysisResult(result);
      setNotice(`${result.instrument.name} 分析完成`);
    });
  }

  async function runPriorityAi() {
    setAiDialogOpen(true);
    setAiResult(null);
    await withLoading("ai", async () => {
      const result = await api.buildAiDecisionSupport({
        task: "priority_board_summary",
        title: "全策略优先级榜盘中解读",
        include_ai: true,
        payload: {
          market_state: priorityBoard?.market_state_text,
          hot_industries: priorityBoard?.hot_industries,
          total_candidates: priorityBoard?.total_candidates,
          immediate_count: priorityBoard?.immediate_count,
          focus_count: priorityBoard?.focus_count,
          items: (priorityBoard?.items ?? []).slice(0, 12),
        },
      });
      setAiResult(result);
    });
  }

  async function runBacktest() {
    await withLoading("backtest", async () => {
      const [symbolResult, executionResult] = await Promise.allSettled([
        api.runBacktest({
          symbol: backtestDraft.symbol.trim(),
          lookback_bars: parseNumber(backtestDraft.lookback_bars),
          bar_period: backtestDraft.bar_period,
          initial_position: parseNumber(backtestDraft.initial_position),
          walk_forward_windows: parseNumber(backtestDraft.walk_forward_windows),
        }),
        api.getLowBuyExecutionBacktest(
          backtestDraft.low_buy_strategy,
          parseNumber(backtestDraft.low_buy_lookback_days),
          parseNumber(backtestDraft.low_buy_limit)
        ),
      ]);
      if (symbolResult.status === "fulfilled") {
        setBacktestResult(symbolResult.value);
      }
      if (executionResult.status === "fulfilled") {
        setExecutionBacktest(executionResult.value);
      }
      const rejected = [symbolResult, executionResult].find(
        (item): item is PromiseRejectedResult => item.status === "rejected"
      );
      if (rejected) {
        throw rejected.reason;
      }
    });
  }

  async function runStrategyValidation() {
    await withLoading("strategy-validation", async () => {
      const result = await api.runStrategyValidation({
        strategies: ["first_board", "volume_shrink", "late_session_strong_support", "core_midcap_vwap_ma5_retrace", "sector_mainline_first_divergence_low_buy"],
        lookback_days: parseNumber(backtestDraft.low_buy_lookback_days),
        max_signals_per_day: 8,
      });
      setStrategyValidation(result);
    });
  }

  function goAnalyzeFromCard(card: StockCardView) {
    void runAnalysis(card.symbol);
  }

  function navigatePage(nextPage: Page) {
    setPage(nextPage);
    if (typeof window === "undefined") {
      return;
    }
    const nextPath = PAGE_PATHS[nextPage];
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
  }

  if (!authReady) {
    return (
      <div className="app auth-loading">
        <div className="panel">正在恢复登录状态...</div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <LoginPage
        draft={authDraft}
        error={error}
        loading={isLoading(loadingState, "auth")}
        setDraft={setAuthDraft}
        onLogin={() => void submitAuth(false)}
        onRegister={() => void submitAuth(true)}
      />
    );
  }

  return (
    <div className={`app page-${page}`}>
      <Topbar
        page={page}
        setPage={navigatePage}
        priorityBoard={priorityBoard}
        watchCards={watchCards}
        currentUser={currentUser}
        onLogout={() => void logout()}
        onPaperRefresh={page === "paper" ? () => void paper.refreshAll() : undefined}
        paperRefreshLoading={isLoading(loadingState, "paper") || isLoading(loadingState, "paper-refresh") || isLoading(loadingState, "paper-quotes")}
      />
      <main className="workspace">
        <StatusStrip loading={loading} notice={notice} />
        <ErrorDialog message={error} onClose={() => setError("")} />
        <StockDetailDialog
          stock={selectedStock}
          onClose={() => setSelectedStock(null)}
          onAnalyze={goAnalyzeFromCard}
        />
        {aiDialogOpen ? (
          <AiInsightDialog
            response={aiResult}
            loading={isLoading(loadingState, "ai")}
            onClose={() => setAiDialogOpen(false)}
          />
        ) : null}
        <PageErrorBoundary resetKey={page}>
        <Suspense fallback={<div className="panel">页面模块加载中...</div>}>
          {page === "monitor" && (
            <MonitorPage
              priorityBoard={priorityBoard}
              marketBreadth={marketBreadth}
              priorityCards={priorityCards}
              watchCards={watchCards}
              runtime={runtime}
              watchDraft={watchDraft}
              setWatchDraft={setWatchDraft}
              loading={loading}
              onRefresh={() => void refreshMonitor()}
              onSync={() => void syncInstruments()}
              onAi={() => void runPriorityAi()}
              onGoPlaybook={() => navigatePage("playbook")}
              onSelect={setSelectedStock}
              onAnalyze={goAnalyzeFromCard}
              onEdit={editWatchlistFromCard}
              onRemove={removeWatchlist}
              onAddWatchlist={() => void addWatchlist()}
            />
          )}
          {page === "analysis" && (
            <AnalysisPage
              draft={analysisDraft}
              setDraft={setAnalysisDraft}
              result={analysisResult}
              loading={loading}
              onRun={() => void runAnalysis()}
            />
          )}
          {page === "playbook" && (
            <PlaybookPage
              strategy={playbookStrategy}
              setStrategy={(nextStrategy) => {
                setPlaybookStrategy(nextStrategy);
                setPlaybook(playbookCache[nextStrategy] ?? null);
              }}
              playbook={playbook}
              loading={loading}
              onRefresh={() => void loadPlaybook(playbookStrategy, true)}
              onAnalyze={goAnalyzeFromCard}
              onSelect={setSelectedStock}
            />
          )}
          {page === "research" && (
            <ResearchPage
              replays={replays}
              priorityBoard={researchBoard}
              lifecycleItems={tradeLifecycles}
              draft={backtestDraft}
              setDraft={setBacktestDraft}
              result={backtestResult}
              runs={backtestRuns}
              executionBacktest={executionBacktest}
              strategyValidation={strategyValidation}
              loading={loading}
              onRun={() => void runBacktest()}
              onValidate={() => void runStrategyValidation()}
              onRefresh={() => void loadResearch()}
            />
          )}
          {page === "paper" && (
            currentUser.can_paper_trade ? (
              <PaperTradingPage
                account={paper.account}
                positions={paper.positions}
                orders={paper.orders}
                trades={paper.trades}
                performance={paper.performance}
                strategyPerformance={paper.strategyPerformance}
                marketPerformance={paper.marketPerformance}
                tagPerformance={paper.tagPerformance}
                tradeTags={paper.tradeTags}
                riskEvents={paper.riskEvents}
                autoTradingStatus={paper.autoTradingStatus}
                autoTradingRuns={paper.autoTradingRuns}
                intradayConfirmations={intradayConfirmations}
                draft={paper.draft}
                setDraft={paper.setDraft}
                loading={loading}
                onSubmitOrder={paper.submitOrder}
                onAddTradeTag={(tradeId, tag) => void paper.addTradeTag(tradeId, tag)}
                onDeleteTradeTag={(tradeId, tagId) => void paper.deleteTradeTag(tradeId, tagId)}
              />
            ) : (
              <section className="panel auth-guard-panel">
                <h2>模拟盘需申请白名单权限</h2>
                <p>当前账号可以查看行情和策略，但暂未开通模拟交易。请联系管理员加入模拟盘白名单。</p>
              </section>
            )
          )}
          {page === "performance" && (
            currentUser.can_paper_trade ? (
              <PerformanceDashboard />
            ) : (
              <section className="panel auth-guard-panel">
                <h2>绩效看板需模拟盘权限</h2>
                <p>当前账号暂未开通模拟盘白名单，无法查看模拟交易绩效。</p>
              </section>
            )
          )}
          {page === "settings" && (
              <SettingsPage
              settings={settingsData.settings}
              runtime={runtime}
              factorWeights={settingsData.factorWeights}
              adminTasks={settingsData.adminTasks}
              strategyGovernance={settingsData.strategyGovernance}
              factorDraft={settingsData.factorDraft}
              draft={settingsData.settingsDraft}
              setDraft={settingsData.setSettingsDraft}
              setFactorDraft={settingsData.setFactorDraft}
              loading={loading}
              onSave={settingsData.saveSettings}
              onSaveFactors={() => void settingsData.saveFactorWeights()}
              onRefresh={() => void settingsData.loadSettings()}
            />
          )}
        </Suspense>
        </PageErrorBoundary>
      </main>
    </div>
  );
}

function isAuthErrorMessage(message: string): boolean {
  const normalized = message.toLowerCase();
  return (
    normalized.includes("401") ||
    normalized.includes("unauthorized") ||
    normalized.includes("not authenticated") ||
    message.includes("登录") ||
    message.includes("账号未开通")
  );
}
