import { useState } from "react";
import { appApi } from "../../api/appClient";
import { api } from "../../api/client";
import type {
  PaperAccount,
  PaperGroupedPerformance,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperTrade,
  RiskEventItem,
} from "../../types";
import { errorMessage, nullableNumber, parseNumber } from "./workspaceFormatters";
import type { PaperOrderDraft } from "./workspaceTypes";

interface UsePaperTradingParams {
  setError: (value: string) => void;
  setLoading: (value: string) => void;
  setNotice: (value: string) => void;
  onAuthRequired: () => void;
}

export function usePaperTrading({ setError, setLoading, setNotice, onAuthRequired }: UsePaperTradingParams) {
  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [performance, setPerformance] = useState<PaperPerformance | null>(null);
  const [strategyPerformance, setStrategyPerformance] = useState<PaperGroupedPerformance[]>([]);
  const [marketPerformance, setMarketPerformance] = useState<PaperGroupedPerformance[]>([]);
  const [riskEvents, setRiskEvents] = useState<RiskEventItem[]>([]);
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
    require_intraday_confirmation: false,
  });

  async function load(allowRefresh = true) {
    try {
      setLoading("paper");
      setError("");
      const [
        accountResult,
        positionsResult,
        ordersResult,
        tradesResult,
        performanceResult,
        strategyPerformanceResult,
        marketPerformanceResult,
        riskEventsResult,
      ] = await Promise.allSettled([
        api.getPaperAccount(),
        api.getPaperPositions(),
        api.getPaperOrders(80),
        api.getPaperTrades(80),
        api.getPaperPerformance(),
        api.getPaperPerformanceByStrategy(),
        api.getPaperPerformanceByMarketState(),
        api.evaluatePaperRiskEvents(),
      ]);
      const rejected = [
        accountResult,
        positionsResult,
        ordersResult,
        tradesResult,
        performanceResult,
        strategyPerformanceResult,
        marketPerformanceResult,
        riskEventsResult,
      ].find((item): item is PromiseRejectedResult => item.status === "rejected");
      if (rejected && isAuthError(rejected.reason)) {
        if (allowRefresh && (await refreshSession())) {
          await load(false);
          return;
        }
        requireLogin();
        return;
      }
      if (accountResult.status === "fulfilled") setAccount(accountResult.value);
      if (positionsResult.status === "fulfilled") setPositions(positionsResult.value.positions);
      if (ordersResult.status === "fulfilled") setOrders(ordersResult.value);
      if (tradesResult.status === "fulfilled") setTrades(tradesResult.value.trades);
      if (performanceResult.status === "fulfilled") setPerformance(performanceResult.value);
      if (strategyPerformanceResult.status === "fulfilled") setStrategyPerformance(strategyPerformanceResult.value);
      if (marketPerformanceResult.status === "fulfilled") setMarketPerformance(marketPerformanceResult.value);
      if (riskEventsResult.status === "fulfilled") setRiskEvents(riskEventsResult.value);
      if (rejected) setError(errorMessage(rejected.reason));
    } finally {
      setLoading("");
    }
  }

  async function refreshPositions() {
    await withPaperLoading("paper-quotes", async () => {
      const result = await runAuthenticated(() => api.refreshPaperPositions());
      setPositions(result.positions);
      const [accountResult, performanceResult] = await Promise.allSettled([
        runAuthenticated(() => api.getPaperAccount(), false),
        runAuthenticated(() => api.getPaperPerformance(), false),
      ]);
      if (accountResult.status === "fulfilled") setAccount(accountResult.value);
      if (performanceResult.status === "fulfilled") setPerformance(performanceResult.value);
    });
  }

  async function togglePause() {
    await withPaperLoading("paper-status", async () => {
      const nextAccount = account?.status === "paused"
        ? await runAuthenticated(() => api.resumePaperAccount())
        : await runAuthenticated(() => api.pausePaperAccount());
      setAccount(nextAccount);
      setNotice(nextAccount.status === "paused" ? "模拟盘已暂停" : "模拟盘已恢复");
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
        require_intraday_confirmation: draft.require_intraday_confirmation,
        source: "manual",
      }));
      setNotice(result.status === "filled" ? "模拟委托已成交" : result.reject_reason || "模拟委托已提交");
      await load();
    });
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
    setPerformance(null);
    setStrategyPerformance([]);
    setMarketPerformance([]);
    setRiskEvents([]);
  }

  return {
    account,
    positions,
    orders,
    trades,
    performance,
    strategyPerformance,
    marketPerformance,
    riskEvents,
    draft,
    setDraft,
    load,
    refreshPositions,
    submitOrder,
    togglePause,
  };
}

function isAuthError(reason: unknown): boolean {
  const message = errorMessage(reason).toLowerCase();
  return (
    message.includes("401") ||
    message.includes("not authenticated") ||
    message.includes("unauthorized") ||
    message.includes("未登录") ||
    message.includes("登录")
  );
}
