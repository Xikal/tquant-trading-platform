import { useEffect, useRef } from "react";
import { appApi } from "../../api/appClient";
import { clearAuthTokens, getAuthAccessToken, shouldAttemptAuthRefresh } from "../../api/base";
import { api } from "../../api/client";
import { strategiesApi } from "../../api/strategies";
import { useWorkspaceStore } from "../../stores/workspaceStore";
import { LoginPage } from "./LoginPage";
import { TradingWorkspaceChrome } from "./TradingWorkspaceChrome";
import { nullableNumber, parseNumber } from "../workspace-shared/workspaceFormatters";
import { isLoading } from "./loadingState";
import type { Page, StockCardView } from "../workspace-shared/workspaceTypes";
import { useAnalysisData } from "./useAnalysisData";
import { useMonitorData } from "./useMonitorData";
import { usePaperIntraday } from "./usePaperIntraday";
import { usePaperTrading } from "./usePaperTrading";
import { usePlaybookData } from "./usePlaybookData";
import { useSettingsData } from "./useSettingsData";
import { useWorkspaceLoading } from "./useWorkspaceLoading";
import { useWorkspaceNavigation } from "./useWorkspaceNavigation";
import { useWorkspacePageProps } from "./useWorkspacePageProps";
import { useWorkspaceAutoRefresh } from "./useWorkspaceAutoRefresh";
import { WORKSPACE_AUTH_LOADING_STYLE } from "./workspaceShellStyles";
export function TradingWorkspace() {
  const { page, navigatePage } = useWorkspaceNavigation();
  const authReady = useWorkspaceStore((state) => state.authReady);
  const currentUser = useWorkspaceStore((state) => state.currentUser);
  const notice = useWorkspaceStore((state) => state.notice);
  const error = useWorkspaceStore((state) => state.error);
  const commandOpen = useWorkspaceStore((state) => state.commandOpen);
  const aiDialogOpen = useWorkspaceStore((state) => state.aiDialogOpen);
  const selectedStock = useWorkspaceStore((state) => state.selectedStock);
  const authDraft = useWorkspaceStore((state) => state.authDraft);
  const watchDraft = useWorkspaceStore((state) => state.watchDraft);
  const editingWatchSymbol = useWorkspaceStore((state) => state.editingWatchSymbol);
  const aiResult = useWorkspaceStore((state) => state.aiResult);
  const commandStrategies = useWorkspaceStore((state) => state.commandStrategies);
  const strategyMeta = useWorkspaceStore((state) => state.strategyMeta);
  const setAuthReady = useWorkspaceStore((state) => state.setAuthReady);
  const setAuthDraft = useWorkspaceStore((state) => state.setAuthDraft);
  const setWatchDraft = useWorkspaceStore((state) => state.setWatchDraft);
  const setEditingWatchSymbol = useWorkspaceStore((state) => state.setEditingWatchSymbol);
  const setCurrentUser = useWorkspaceStore((state) => state.setCurrentUser);
  const setNotice = useWorkspaceStore((state) => state.setNotice);
  const setError = useWorkspaceStore((state) => state.setError);
  const setCommandOpen = useWorkspaceStore((state) => state.setCommandOpen);
  const setAiDialogOpen = useWorkspaceStore((state) => state.setAiDialogOpen);
  const setSelectedStock = useWorkspaceStore((state) => state.setSelectedStock);
  const setAiResult = useWorkspaceStore((state) => state.setAiResult);
  const setCommandStrategies = useWorkspaceStore((state) => state.setCommandStrategies);
  const setStrategyMeta = useWorkspaceStore((state) => state.setStrategyMeta);
  const clearTransientUi = useWorkspaceStore((state) => state.clearTransientUi);
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
    active: Boolean(currentUser) && page === "monitor",
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
  const paper = usePaperTrading({
    canManageReconcile: Boolean(currentUser?.roles.some((role) => {
      const normalized = role.trim().toLowerCase();
      return normalized === "admin" || normalized === "administrator";
    })),
    setError,
    setLoading: setPaperLoading,
    setNotice,
    onAuthRequired: handleAuthRequired,
  });
  const paperLiveRefreshRef = useRef(paper.refreshLiveSnapshot);
  useEffect(() => {
    paperLiveRefreshRef.current = paper.refreshLiveSnapshot;
  }, [paper.refreshLiveSnapshot]);
  useWorkspaceAutoRefresh({
    currentUser,
    page,
    fetchMonitorData: monitor.fetchMonitorData,
    paperTradingTime: paper.autoTradingStatus?.trading_time,
    refreshPaperLiveSnapshotRef: paperLiveRefreshRef,
  });
  const settingsData = useSettingsData({
    withLoading,
    setError,
    setNotice,
    setRuntime: monitor.setRuntime,
  });
  usePaperIntraday({
    currentUser,
    page,
    positions: paper.positions,
    refreshAutoTradingStatus: paper.refreshAutoTradingStatus,
  });
  const { monitorPageProps, paperPageProps } = useWorkspacePageProps({
    analysis,
    loading,
    monitor,
    paper,
    watchDraft,
    setWatchDraft,
    editingWatchSymbol,
    currentUser,
    onAddWatchlist: () => void addWatchlist(),
    onEditWatchlist: editWatchlistFromCard,
    onNavigatePage: navigatePage,
    onRefreshMonitor: () => void refreshMonitor(),
    onRemoveWatchlist: removeWatchlist,
    onCancelWatchlistEdit: cancelWatchlistEdit,
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
      if (modifier && /^[1-7]$/.test(event.key)) {
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
    clearTransientUi();
  }, [clearTransientUi, page]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }
    if (page === "settings") {
      void settingsData.loadSettings();
    }
    if (page === "paper") {
      void paper.load();
    }
  }, [currentUser, page]);

  async function restoreSession() {
    try {
      setLoadingKey("auth-restore", true);
      let restored = false;
      if (getAuthAccessToken()) {
        try {
          const result = await appApi.getMe();
          setCurrentUser(result.user);
          restored = true;
        } catch {
          // Fall through to refresh; do not clear tokens before trying the
          // httpOnly refresh cookie-backed path.
        }
      }
      if (restored) {
        return;
      }
      if (shouldAttemptAuthRefresh()) {
        try {
          const result = await appApi.refreshAuth();
          setCurrentUser(result.user);
        } catch {
          clearAuthTokens();
          setCurrentUser(null);
        }
      } else {
        setCurrentUser(null);
      }
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
        : await appApi.login({
            username,
            password,
            device_name: "web-workspace",
            remember: authDraft.remember,
          });
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
      const nextStrategies = result.strategies ?? [];
      setCommandStrategies(nextStrategies);
      setStrategyMeta(nextStrategies);
    } catch {
      setCommandStrategies([]);
      setStrategyMeta([]);
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

  function preparePaperOrder(payload: { symbol: string; name?: string; price?: number | null }) {
    const symbol = payload.symbol.trim();
    const priceText = payload.price == null ? "" : String(payload.price);
    paper.setDraft({
      ...paper.draft,
      symbol,
      name: payload.name || paper.draft.name,
      side: "buy",
      price: priceText,
      current_price: priceText,
      require_intraday_confirmation: false,
    });
    setNotice(`${symbol} 已填入模拟委托，打开录入委托即可提交`);
    navigatePage("paper");
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
      setNotice(editingWatchSymbol ? `${symbol} 持仓信息已更新` : "持仓信息已保存");
      setEditingWatchSymbol("");
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
      if (editingWatchSymbol === symbol) {
        setEditingWatchSymbol("");
        resetWatchDraft();
      }
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
    setEditingWatchSymbol(source.symbol);
    setNotice(`${card.name} 已载入编辑区，修改后点击更新持仓`);
    window.requestAnimationFrame(() => {
      document.querySelector(".monitor-input")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      const input = document.querySelector<HTMLInputElement>(".monitor-input input:not(:disabled)");
      input?.focus();
    });
  }

  function cancelWatchlistEdit() {
    setEditingWatchSymbol("");
    resetWatchDraft();
    setNotice("已取消持仓编辑");
  }

  function resetWatchDraft() {
    setWatchDraft({
      symbol: "",
      name: "",
      base_position: "0",
      available_position: "0",
      cost_basis: "",
      memo: "",
    });
  }

  async function runPriorityAi() {
    setAiDialogOpen(true);
    setAiResult(null);
    await withLoading("ai", async () => {
      const result = await api.buildAiDecisionSupport({
        task: "priority_board_summary",
        title: "生产优先榜盘中解读",
        include_ai: true,
        payload: {
          market_state: monitor.priorityBoard?.market_state_text,
          hot_industries: monitor.priorityBoard?.hot_industries,
          total_candidates: monitor.priorityBoard?.total_candidates,
          immediate_count: monitor.priorityBoard?.immediate_count,
          focus_count: monitor.priorityBoard?.focus_count,
          items: monitor.priorityBoard?.items ?? [],
        },
      });
      setAiResult(result);
    });
  }

  if (!authReady) {
    return (
      <div style={WORKSPACE_AUTH_LOADING_STYLE}>
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
    <TradingWorkspaceChrome
      aiDialogOpen={aiDialogOpen}
      aiLoading={isLoading(loadingState, "ai")}
      aiResult={aiResult}
      analysis={analysis}
      commandOpen={commandOpen}
      commandStrategies={commandStrategies}
      currentUser={currentUser}
      error={error}
      loading={loading}
      monitor={monitor}
      monitorPageProps={monitorPageProps}
      notice={notice}
      page={page}
      paperPageProps={paperPageProps}
      paperRefreshLoading={isLoading(loadingState, "paper") || isLoading(loadingState, "paper-refresh") || isLoading(loadingState, "paper-quotes")}
      playbookData={playbookData}
      selectedStock={selectedStock}
      settingsData={settingsData}
      strategyMeta={strategyMeta}
      onAnalyzeSymbol={analyzeSymbolFromCommand}
      onCloseAi={() => setAiDialogOpen(false)}
      onCloseCommand={() => setCommandOpen(false)}
      onCloseError={() => setError("")}
      onCloseStock={() => setSelectedStock(null)}
      onLogout={() => void logout()}
      onNavigate={navigatePage}
      onOpenStrategy={openStrategyFromCommand}
      onPaperRefresh={page === "paper" ? () => void paper.refreshAll() : undefined}
      onPreparePaperOrder={preparePaperOrder}
      onSelectStock={setSelectedStock}
      onUserUpdate={setCurrentUser}
    />
  );
}

function shortcutPage(key: string): Page | null {
  if (key === "1") return "monitor";
  if (key === "2") return "analysis";
  if (key === "3") return "playbook";
  if (key === "4") return "strategy-tracking";
  if (key === "5") return "backtest";
  if (key === "6") return "paper";
  if (key === "7") return "settings";
  return null;
}
