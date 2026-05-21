import { useCallback, useRef, useState } from "react";
import { appApi } from "../../api/appClient";
import { api } from "../../api/client";
import type {
  PaperAccount,
  PaperAgentRun,
  PaperAutoTradingStatus,
  PaperGroupedPerformance,
  PaperLedgerRepairResponse,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperSectorEtfT0Performance,
  PaperStockPnlItem,
  PaperStockPnlSummary,
  PaperTagPerformance,
  PaperTrade,
  PaperTradeTag,
  RiskEventItem,
} from "../../types";
import { errorMessage, nullableNumber, parseNumber } from "../workspace-shared/workspaceFormatters";
import type { PaperOrderDraft } from "../workspace-shared/workspaceTypes";

interface PaperLiveRefreshOptions {
  refreshPrices?: boolean;
}

interface UsePaperTradingParams {
  canManageReconcile?: boolean;
  setError: (value: string) => void;
  setLoading: (value: string) => void;
  setNotice: (value: string) => void;
  onAuthRequired: () => void;
}

export function usePaperTrading({ canManageReconcile = false, setError, setLoading, setNotice, onAuthRequired }: UsePaperTradingParams) {
  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [stockPnl, setStockPnl] = useState<PaperStockPnlItem[]>([]);
  const [stockPnlSummary, setStockPnlSummary] = useState<PaperStockPnlSummary | null>(null);
  const [performance, setPerformance] = useState<PaperPerformance | null>(null);
  const [sectorEtfT0Performance, setSectorEtfT0Performance] = useState<PaperSectorEtfT0Performance | null>(null);
  const [strategyPerformance, setStrategyPerformance] = useState<PaperGroupedPerformance[]>([]);
  const [marketPerformance, setMarketPerformance] = useState<PaperGroupedPerformance[]>([]);
  const [tagPerformance, setTagPerformance] = useState<PaperTagPerformance[]>([]);
  const [tradeTags, setTradeTags] = useState<Record<number, PaperTradeTag[]>>({});
  const [riskEvents, setRiskEvents] = useState<RiskEventItem[]>([]);
  const [autoTradingStatus, setAutoTradingStatus] = useState<PaperAutoTradingStatus | null>(null);
  const [autoTradingRuns, setAutoTradingRuns] = useState<PaperAgentRun[]>([]);
  const [ledgerRepairStatus, setLedgerRepairStatus] = useState<PaperLedgerRepairResponse | null>(null);
  const [draft, setDraft] = useState<PaperOrderDraft>({
    symbol: "",
    name: "",
    side: "buy",
    order_type: "market",
    quantity: "100",
    price: "",
    current_price: "",
    strategy_key: "",
    reason: "",
    require_intraday_confirmation: true,
  });

  async function load(allowRefresh = true, manageLoading = true) {
    try {
      if (manageLoading) setLoading("paper");
      setError("");
      const workspace = await api.getPaperWorkspaceBff();
      applyPaperWorkspace(workspace);
      await loadTradeTags(workspace.trades);
      if (canManageReconcile && workspace.account) {
        await refreshLedgerRepairStatus(false, workspace.account.id);
      } else if (!canManageReconcile) {
        setLedgerRepairStatus(null);
      }
      if (workspace.partial_errors.length > 0) {
        setError(workspace.partial_errors.map((item) => item.detail).join("；"));
      }
    } catch (err) {
      if (isAuthError(err)) {
        if (allowRefresh && (await refreshSession())) {
          await load(false, manageLoading);
          return;
        }
        requireLogin();
        return;
      }
      setError(errorMessage(err));
    } finally {
      if (manageLoading) setLoading("");
    }
  }

  function applyPaperWorkspace(workspace: Awaited<ReturnType<typeof api.getPaperWorkspaceBff>>) {
    setAccount(workspace.account);
    setPositions(workspace.positions);
    setOrders(workspace.orders);
    setTrades(workspace.trades);
    setStockPnl(workspace.stock_pnl?.items ?? []);
    setStockPnlSummary(workspace.stock_pnl?.summary ?? null);
    setPerformance(workspace.performance);
    setSectorEtfT0Performance(workspace.sector_etf_t0_performance);
    setStrategyPerformance(workspace.strategy_performance);
    setMarketPerformance(workspace.market_performance);
    setTagPerformance(workspace.tag_performance);
    setRiskEvents(workspace.risk_events);
    setAutoTradingStatus(workspace.auto_trading_status);
    setAutoTradingRuns(workspace.auto_trading_runs);
  }

  async function refreshAll() {
    await withPaperLoading("paper-refresh", async () => {
      await runAuthenticated(() => api.refreshPaperPositions());
      await load(false, false);
      setNotice("模拟盘与持仓价格已刷新");
    });
  }

  async function refreshLiveSnapshot(options: PaperLiveRefreshOptions = {}) {
    try {
      if (options.refreshPrices) {
        await runAuthenticated(() => api.refreshPaperPositions(), true);
      }
      const [
        accountResult,
        positionsResult,
        ordersResult,
        tradesResult,
        stockPnlResult,
        performanceResult,
        sectorEtfT0PerformanceResult,
        autoTradingStatusResult,
      ] = await Promise.allSettled([
        runAuthenticated(() => api.getPaperAccount(), true),
        runAuthenticated(() => api.getPaperPositions(), true),
        runAuthenticated(() => api.getPaperOrders(80), true),
        runAuthenticated(() => api.getPaperTrades(300), true),
        runAuthenticated(() => api.getPaperStockPnl(), true),
        runAuthenticated(() => api.getPaperPerformance(), true),
        runAuthenticated(() => api.getPaperSectorEtfT0Performance(), true),
        runAuthenticated(() => api.getPaperAutoTradingStatus(), true),
      ]);
      if (accountResult.status === "fulfilled") setAccount(accountResult.value);
      if (positionsResult.status === "fulfilled") setPositions(positionsResult.value.positions);
      if (ordersResult.status === "fulfilled") setOrders(ordersResult.value);
      if (tradesResult.status === "fulfilled") setTrades(tradesResult.value.trades);
      if (stockPnlResult.status === "fulfilled") {
        setStockPnl(stockPnlResult.value.items);
        setStockPnlSummary(stockPnlResult.value.summary);
      }
      if (performanceResult.status === "fulfilled") setPerformance(performanceResult.value);
      if (sectorEtfT0PerformanceResult.status === "fulfilled") setSectorEtfT0Performance(sectorEtfT0PerformanceResult.value);
      if (autoTradingStatusResult.status === "fulfilled") setAutoTradingStatus(autoTradingStatusResult.value);
    } catch (err) {
      if (isAuthError(err)) {
        requireLogin();
      }
      if (import.meta.env.DEV) {
        console.warn("模拟盘自动刷新失败，已保留上次数据。", err);
      }
    }
  }

  async function refreshAutoTradingStatus() {
    try {
      const status = await runAuthenticated(() => api.getPaperAutoTradingStatus(), false);
      setAutoTradingStatus(status);
    } catch (err) {
      if (isAuthError(err)) {
        requireLogin();
      }
    }
  }
  const refreshAutoTradingStatusRef = useRef(refreshAutoTradingStatus);
  refreshAutoTradingStatusRef.current = refreshAutoTradingStatus;
  const stableRefreshAutoTradingStatus = useCallback(
    () => refreshAutoTradingStatusRef.current(),
    [],
  );
  const refreshLiveSnapshotRef = useRef(refreshLiveSnapshot);
  refreshLiveSnapshotRef.current = refreshLiveSnapshot;
  const stableRefreshLiveSnapshot = useCallback(
    (options?: PaperLiveRefreshOptions) => refreshLiveSnapshotRef.current(options),
    [],
  );

  async function refreshLedgerRepairStatus(allowRefresh = true, accountId?: number) {
    if (!canManageReconcile) return null;
    const result = await runAuthenticated(
      () => api.reconcilePaperAccount({ account_id: accountId ?? account?.id, apply: false }),
      allowRefresh,
    );
    setLedgerRepairStatus(result);
    return result;
  }

  async function applyLedgerRepair() {
    if (!canManageReconcile) {
      throw new Error("当前账号没有对账修复权限");
    }
    return withPaperLoading("paper-ledger-repair", async () => {
      const result = await runAuthenticated(() => api.reconcilePaperAccount({ account_id: account?.id, apply: true }));
      setLedgerRepairStatus(result);
      await load(false, false);
      setNotice(result.issue_count > 0 ? `已修复 ${result.issue_count} 条异常成交` : "账户已完成重算");
      return result;
    });
  }

  async function togglePause() {
    await withPaperLoading("paper-status", async () => {
      const nextAccount = account?.status === "paused"
        ? await runAuthenticated(() => api.resumePaperAccount())
        : await runAuthenticated(() => api.pausePaperAccount());
      setAccount(nextAccount);
      setNotice(nextAccount.status === "paused" ? "模拟盘已暂停" : "模拟盘已恢复");
      await load(false, false);
    });
  }

  async function submitOrder() {
    await withPaperLoading("paper-order", async () => {
      const symbol = draft.symbol.trim();
      if (!symbol) {
        throw new Error("请填写模拟委托代码");
      }
      const quantity = parseNumber(draft.quantity);
      if (quantity <= 0 || quantity % 100 !== 0) {
        throw new Error("委托数量必须是 100 股整数倍");
      }
      const result = await runAuthenticated(() => api.createPaperOrder({
        symbol,
        name: draft.name.trim(),
        side: draft.side,
        order_type: draft.order_type,
        quantity,
        price: nullableNumber(draft.price),
        current_price: nullableNumber(draft.current_price),
        strategy_key: draft.strategy_key.trim(),
        reason: draft.reason.trim(),
        require_intraday_confirmation: true,
        source: "manual",
      }));
      setNotice(result.status === "filled" ? "模拟委托已成交" : result.reject_reason || "模拟委托已提交");
      await load();
    });
  }

  async function addTradeTag(tradeId: number, tag: string, note = "") {
    await withPaperLoading("paper-tags", async () => {
      const saved = await runAuthenticated(() => api.addPaperTradeTag(tradeId, { tag, note }));
      setTradeTags((current) => ({
        ...current,
        [tradeId]: upsertTag(current[tradeId] ?? [], saved),
      }));
      await refreshTagPerformance();
      setNotice(`已标记：${tag}`);
    });
  }

  async function deleteTradeTag(tradeId: number, tagId: number) {
    await withPaperLoading("paper-tags", async () => {
      await runAuthenticated(() => api.deletePaperTradeTag(tradeId, tagId));
      setTradeTags((current) => ({
        ...current,
        [tradeId]: (current[tradeId] ?? []).filter((item) => item.id !== tagId),
      }));
      await refreshTagPerformance();
      setNotice("标签已删除");
    });
  }

  async function loadTradeTags(tradeItems: PaperTrade[]) {
    const visibleTrades = tradeItems.slice(0, 20);
    if (!visibleTrades.length) {
      setTradeTags({});
      return;
    }
    const results = await Promise.allSettled(
      visibleTrades.map(async (trade) => [trade.id, await api.getPaperTradeTags(trade.id)] as const)
    );
    const next: Record<number, PaperTradeTag[]> = {};
    for (const result of results) {
      if (result.status === "fulfilled") {
        const [tradeId, tags] = result.value;
        next[tradeId] = tags;
      }
    }
    setTradeTags(next);
  }

  async function refreshTagPerformance() {
    try {
      const items = await runAuthenticated(() => api.getPaperPerformanceByTag(), false);
      setTagPerformance(items);
    } catch {
      setTagPerformance([]);
    }
  }

  async function withPaperLoading<T>(key: string, action: () => Promise<T>): Promise<T | undefined> {
    try {
      setLoading(key);
      setError("");
      return await action();
    } catch (err) {
      setError(errorMessage(err));
      return undefined;
    } finally {
      setLoading("");
    }
  }

  async function runAuthenticated<T>(action: () => Promise<T>, allowRefresh = true): Promise<T> {
    try {
      const result = await action();
      return result;
    } catch (err) {
      if (allowRefresh && isAuthError(err) && (await refreshSession())) {
        return runAuthenticated(action, false);
      }
      if (isAuthError(err)) {
        requireLogin();
        throw new Error("请先登录模拟盘");
      }
      throw err;
    }
  }

  async function refreshSession(): Promise<boolean> {
    try {
      await appApi.refreshAuth();
      return true;
    } catch {
      return false;
    }
  }

  function requireLogin() {
    onAuthRequired();
    setAccount(null);
    setPositions([]);
    setOrders([]);
    setTrades([]);
    setStockPnl([]);
    setStockPnlSummary(null);
    setPerformance(null);
    setSectorEtfT0Performance(null);
    setStrategyPerformance([]);
    setMarketPerformance([]);
    setTagPerformance([]);
    setTradeTags({});
    setRiskEvents([]);
    setAutoTradingStatus(null);
    setAutoTradingRuns([]);
    setLedgerRepairStatus(null);
  }

  return {
    account,
    positions,
    orders,
    trades,
    stockPnl,
    stockPnlSummary,
    performance,
    sectorEtfT0Performance,
    strategyPerformance,
    marketPerformance,
    tagPerformance,
    tradeTags,
    riskEvents,
    autoTradingStatus,
    autoTradingRuns,
    ledgerRepairStatus,
    draft,
    setDraft,
    load,
    refreshAll,
    refreshLiveSnapshot: stableRefreshLiveSnapshot,
    refreshAutoTradingStatus: stableRefreshAutoTradingStatus,
    refreshLedgerRepairStatus,
    applyLedgerRepair,
    submitOrder,
    addTradeTag,
    deleteTradeTag,
    togglePause,
  };
}

function upsertTag(tags: PaperTradeTag[], next: PaperTradeTag): PaperTradeTag[] {
  const withoutCurrent = tags.filter((item) => item.id !== next.id && item.tag !== next.tag);
  return [next, ...withoutCurrent];
}

function isAuthError(reason: unknown): boolean {
  const status = (reason as { status?: number } | null)?.status;
  if (status !== undefined) {
    return status === 401;
  }
  const message = errorMessage(reason).toLowerCase();
  return (
    message.includes("401") ||
    message.includes("not authenticated") ||
    message.includes("unauthorized")
  );
}
