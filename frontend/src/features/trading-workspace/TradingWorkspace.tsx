import { lazy, useEffect, useState } from "react";
import { appApi } from "../../api/appClient";
import { clearAuthTokens, getAuthAccessToken } from "../../api/base";
import { api } from "../../api/client";
import { strategiesApi, type StrategyMeta } from "../../api/strategies";
import type { AiDecisionSupportResponse, AuthUser } from "../../types";
import { CommandPalette } from "./CommandPalette";
import { LoginPage } from "./LoginPage";
import { Topbar } from "./Topbar";
import { AiInsightDialog, ErrorDialog, StatusStrip, StockDetailDialog } from "./WorkspaceComponents";
import { MONITOR_REFRESH_INTERVAL_MS } from "./workspaceConstants";
import { nullableNumber, parseNumber } from "./workspaceFormatters";
import { isLoading } from "./loadingState";
import type { AuthDraft, Page, StockCardView, WatchDraft } from "./workspaceTypes";
import { useAnalysisData } from "./useAnalysisData";
import { useMonitorData } from "./useMonitorData";
import { usePaperIntraday } from "./usePaperIntraday";
import { usePaperTrading } from "./usePaperTrading";
import { usePlaybookData } from "./usePlaybookData";
import { useResearchData } from "./useResearchData";
import { useSettingsData } from "./useSettingsData";
import { useWorkspaceLoading } from "./useWorkspaceLoading";
import { useWorkspaceNavigation } from "./useWorkspaceNavigation";
import { useWorkspacePageProps } from "./useWorkspacePageProps";
import { WorkspacePageContent } from "./WorkspacePageContent";

const AnalysisPage = lazy(async () => ({ default: (await import("./AnalysisPage")).AnalysisPage }));
const BacktestPage = lazy(async () => ({ default: (await import("../backtest/BacktestPage")).BacktestPage }));
const MonitorPage = lazy(async () => ({ default: (await import("./MonitorPage")).MonitorPage }));
const PaperTradingPage = lazy(async () => ({ default: (await import("./PaperTradingPage")).PaperTradingPage }));
const PerformanceDashboard = lazy(async () => ({ default: (await import("./PerformanceDashboard")).PerformanceDashboard }));
const PlaybookPage = lazy(async () => ({ default: (await import("./PlaybookPage")).PlaybookPage }));
const ResearchPage = lazy(async () => ({ default: (await import("./ResearchPage")).ResearchPage }));
const SettingsPage = lazy(async () => ({ default: (await import("./SettingsPage")).SettingsPage }));
const StrategyHubPage = lazy(async () => ({ default: (await import("../strategy/StrategyHubPage")).StrategyHubPage }));

export function TradingWorkspace() {
  const [authReady, setAuthReady] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const { page, navigatePage } = useWorkspaceNavigation();
  const [aiResult, setAiResult] = useState<AiDecisionSupportResponse | null>(null);
  const [aiDialogOpen, setAiDialogOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandStrategies, setCommandStrategies] = useState<StrategyMeta[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [selectedStock, setSelectedStock] = useState<StockCardView | null>(null);
  const {
    loading,
    loadingState,
    setLoadingKey,
    setPaperLoading,
    withLoading,
  } = useWorkspaceLoading({
    onError: setError,
    onAuthRequired: handleAuthRequired,
  });
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
  const { monitorPageProps, paperPageProps } = useWorkspacePageProps({
    analysis,
    intradayConfirmations,
    loading,
    monitor,
    paper,
    watchDraft,
    setWatchDraft,
    onAddWatchlist: () => void addWatchlist(),
    onEditWatchlist: editWatchlistFromCard,
    onNavigatePage: navigatePage,
    onRefreshMonitor: () => void refreshMonitor(),
    onRemoveWatchlist: removeWatchlist,
    onRunPriorityAi: () => void runPriorityAi(),
    onSelectStock: setSelectedStock,
  });
  useEffect(() => {
    void restoreSession();
  }, []);

  useEffect(() => {
    if (authReady && currentUser) {
      void refreshMonitor();
      void loadCommandStrategies();
    }
  }, [authReady, currentUser?.id]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const modifier = event.metaKey || event.ctrlKey;
      if (modifier && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
        return;
      }
      if (event.key === "Escape") {
        setCommandOpen(false);
        return;
      }
      if (modifier && /^[1-8]$/.test(event.key)) {
        const nextPage = shortcutPage(event.key);
        if (nextPage) {
          event.preventDefault();
          navigatePage(nextPage);
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [navigatePage]);

  useEffect(() => {
    if (!notice) {
      return undefined;
    }
    const timer = window.setTimeout(() => setNotice(""), 3500);
    return () => window.clearTimeout(timer);
  }, [notice]);

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

  async function loadCommandStrategies() {
    try {
      const result = await strategiesApi.getStrategyMeta();
      setCommandStrategies(result.strategies ?? []);
    } catch {
      setCommandStrategies([]);
    }
  }

  function analyzeSymbolFromCommand(symbol: string) {
    analysis.setDraft((draft) => ({ ...draft, symbol }));
    navigatePage("analysis");
  }

  function openStrategyFromCommand(strategyKey: string) {
    playbookData.setStrategy(strategyKey);
    navigatePage("playbook");
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
        <CommandPalette
          open={commandOpen}
          strategies={commandStrategies}
          onClose={() => setCommandOpen(false)}
          onNavigate={navigatePage}
          onAnalyzeSymbol={analyzeSymbolFromCommand}
          onOpenStrategy={openStrategyFromCommand}
        />
        <WorkspacePageContent
          AnalysisPage={AnalysisPage}
          BacktestPage={BacktestPage}
          MonitorPage={MonitorPage}
          PaperTradingPage={PaperTradingPage}
          PerformanceDashboard={PerformanceDashboard}
          PlaybookPage={PlaybookPage}
          ResearchPage={ResearchPage}
          SettingsPage={SettingsPage}
          StrategyHubPage={StrategyHubPage}
          analysis={analysis}
          currentUser={currentUser}
          loading={loading}
          monitor={monitor}
          monitorPageProps={monitorPageProps}
          page={page}
          paperPageProps={paperPageProps}
          playbookData={playbookData}
          research={research}
          settingsData={settingsData}
          onSelectStock={setSelectedStock}
        />
      </main>
    </div>
  );
}

function shortcutPage(key: string): Page | null {
  if (key === "1") return "monitor";
  if (key === "2") return "analysis";
  if (key === "3") return "playbook";
  if (key === "4") return "strategy";
  if (key === "5") return "paper";
  if (key === "6") return "performance";
  if (key === "7") return "settings";
  return null;
}
