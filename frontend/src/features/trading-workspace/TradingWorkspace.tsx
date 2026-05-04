import { Suspense, lazy, useEffect, useState } from "react";
import { appApi } from "../../api/appClient";
import { clearAuthTokens, getAuthAccessToken } from "../../api/base";
import { api } from "../../api/client";
import type { AiDecisionSupportResponse, AuthUser } from "../../types";
import { LoginPage } from "./LoginPage";
import { Topbar } from "./Topbar";
import { AiInsightDialog, ErrorDialog, StatusStrip, StockDetailDialog } from "./WorkspaceComponents";
import { MONITOR_REFRESH_INTERVAL_MS, PAGE_PATHS } from "./workspaceConstants";
import { errorMessage, nullableNumber, parseNumber } from "./workspaceFormatters";
import { pageFromLocation } from "./workspaceRoutes";
import { activeLoadingKey, clearLoadingKeys, isLoading, setLoadingFlag, type LoadingState } from "./loadingState";
import { PageErrorBoundary } from "./PageErrorBoundary";
import type { AuthDraft, Page, StockCardView, WatchDraft } from "./workspaceTypes";
import { useAnalysisData } from "./useAnalysisData";
import { useMonitorData } from "./useMonitorData";
import { usePaperIntraday } from "./usePaperIntraday";
import { usePaperTrading } from "./usePaperTrading";
import { usePlaybookData } from "./usePlaybookData";
import { useResearchData } from "./useResearchData";
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
  const [aiResult, setAiResult] = useState<AiDecisionSupportResponse | null>(null);
  const [aiDialogOpen, setAiDialogOpen] = useState(false);
  const [loadingState, setLoadingState] = useState<LoadingState>({});
  const loading = activeLoadingKey(loadingState);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [selectedStock, setSelectedStock] = useState<StockCardView | null>(null);
  const monitor = useMonitorData({
    withLoading,
    setError,
    setNotice,
  });
  const playbookData = usePlaybookData({
    currentUser,
    page,
    withLoading,
  });
  const analysis = useAnalysisData({
    withLoading,
    setError,
    setNotice,
    navigatePage,
  });
  const research = useResearchData({
    withLoading,
    setError,
  });
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
    setRuntime: monitor.setRuntime,
  });
  const intradayConfirmations = usePaperIntraday({
    currentUser,
    page,
    positions: paper.positions,
    refreshAutoTradingStatus: paper.refreshAutoTradingStatus,
  });

  const [watchDraft, setWatchDraft] = useState<WatchDraft>({
    symbol: "",
    name: "",
    base_position: "0",
    available_position: "0",
    cost_basis: "",
    memo: "",
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
    if (page === "settings") {
      void settingsData.loadSettings();
    }
    if (page === "research") {
      void research.loadResearch();
    }
    if (page === "paper") {
      void paper.load();
    }
  }, [currentUser, page]);

  useEffect(() => {
    if (!currentUser || page !== "monitor") {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void monitor.fetchMonitorData(false);
    }, MONITOR_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [currentUser, page]);

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
      if (getAuthAccessToken()) {
        try {
          const result = await appApi.getMe();
          setCurrentUser(result.user);
          return;
        } catch {
          clearAuthTokens();
        }
      }
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
        ? await appApi.register({ username, password, display_name: username, device_name: "web-workspace", remember: authDraft.remember })
        : await appApi.login({ username, password, device_name: "web-workspace", remember: authDraft.remember });
      setCurrentUser(result.user);
      setAuthDraft((draft) => ({ ...draft, password: "" }));
      setNotice(register ? "账号已开通，已进入工作台" : "登录成功");
      await monitor.fetchMonitorData(true);
    });
  }

  function handleAuthRequired() {
    clearAuthTokens();
    setCurrentUser(null);
    monitor.resetMonitorData();
    playbookData.resetPlaybook();
  }

  async function logout() {
    await appApi.logout();
    handleAuthRequired();
    setNotice("已退出登录");
  }

  async function refreshMonitor() {
    await monitor.refreshMonitor();
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
      await monitor.fetchMonitorData(true);
    });
  }

  async function removeWatchlist(symbol: string) {
    await withLoading("watchlist", async () => {
      await api.deleteWatchlist(symbol);
      setNotice(`已移除 ${symbol}`);
      await monitor.fetchMonitorData(true);
    });
  }

  function editWatchlistFromCard(card: StockCardView) {
    const source = monitor.watchlistSignals.find((item) => item.symbol === card.symbol);
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

  async function runPriorityAi() {
    setAiDialogOpen(true);
    setAiResult(null);
    await withLoading("ai", async () => {
      const result = await api.buildAiDecisionSupport({
        task: "priority_board_summary",
        title: "全策略优先级榜盘中解读",
        include_ai: true,
        payload: {
          market_state: monitor.priorityBoard?.market_state_text,
          hot_industries: monitor.priorityBoard?.hot_industries,
          total_candidates: monitor.priorityBoard?.total_candidates,
          immediate_count: monitor.priorityBoard?.immediate_count,
          focus_count: monitor.priorityBoard?.focus_count,
          items: (monitor.priorityBoard?.items ?? []).slice(0, 12),
        },
      });
      setAiResult(result);
    });
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
        priorityBoard={monitor.priorityBoard}
        watchCards={monitor.watchCards}
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
          onAnalyze={analysis.analyzeFromCard}
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
              priorityBoard={monitor.priorityBoard}
              marketBreadth={monitor.marketBreadth}
              priorityCards={monitor.priorityCards}
              watchCards={monitor.watchCards}
              runtime={monitor.runtime}
              watchDraft={watchDraft}
              setWatchDraft={setWatchDraft}
              loading={loading}
              onRefresh={() => void refreshMonitor()}
              onSync={() => void monitor.syncInstruments()}
              onAi={() => void runPriorityAi()}
              onGoPlaybook={() => navigatePage("playbook")}
              onSelect={setSelectedStock}
              onAnalyze={analysis.analyzeFromCard}
              onEdit={editWatchlistFromCard}
              onRemove={removeWatchlist}
              onAddWatchlist={() => void addWatchlist()}
            />
          )}
          {page === "analysis" && (
            <AnalysisPage
              draft={analysis.draft}
              setDraft={analysis.setDraft}
              result={analysis.result}
              loading={loading}
              onRun={() => void analysis.runAnalysis()}
            />
          )}
          {page === "playbook" && (
            <PlaybookPage
              strategy={playbookData.strategy}
              setStrategy={playbookData.setStrategy}
              playbook={playbookData.playbook}
              loading={loading}
              onRefresh={() => void playbookData.loadPlaybook(playbookData.strategy, true)}
              onAnalyze={analysis.analyzeFromCard}
              onSelect={setSelectedStock}
            />
          )}
          {page === "research" && (
            <ResearchPage
              replays={research.replays}
              priorityBoard={research.researchBoard}
              lifecycleItems={research.tradeLifecycles}
              draft={research.draft}
              setDraft={research.setDraft}
              result={research.backtestResult}
              runs={research.backtestRuns}
              executionBacktest={research.executionBacktest}
              strategyValidation={research.strategyValidation}
              loading={loading}
              onRun={() => void research.runBacktest()}
              onValidate={() => void research.runStrategyValidation()}
              onRefresh={() => void research.loadResearch()}
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
              runtime={monitor.runtime}
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
