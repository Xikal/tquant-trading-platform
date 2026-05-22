import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  type BacktestCreateRequest,
  type BacktestExecutionModel,
  backtestsApi,
} from "../../api/backtests";
import {
  strategiesApi,
  type StrategyPreset,
} from "../../api/strategies";
import { applyBacktestVerdictThresholds } from "../backtest/backtestDisplay";
import {
  useStrategyHubUiStore,
  type StrategyHubTab,
  type StrategyQuickForm,
} from "../../stores/strategyHubStore";

export type { StrategyHubTab, StrategyQuickForm } from "../../stores/strategyHubStore";

export function useStrategyHub() {
  const tab = useStrategyHubUiStore((state) => state.tab);
  const setTabState = useStrategyHubUiStore((state) => state.setTab);
  const confirmOpen = useStrategyHubUiStore((state) => state.confirmOpen);
  const setConfirmOpen = useStrategyHubUiStore((state) => state.setConfirmOpen);
  const strategies = useStrategyHubUiStore((state) => state.strategies);
  const presets = useStrategyHubUiStore((state) => state.presets);
  const runs = useStrategyHubUiStore((state) => state.runs);
  const form = useStrategyHubUiStore((state) => state.form);
  const loading = useStrategyHubUiStore((state) => state.loading);
  const error = useStrategyHubUiStore((state) => state.error);
  const notice = useStrategyHubUiStore((state) => state.notice);
  const setStrategies = useStrategyHubUiStore((state) => state.setStrategies);
  const setPresets = useStrategyHubUiStore((state) => state.setPresets);
  const setRuns = useStrategyHubUiStore((state) => state.setRuns);
  const setForm = useStrategyHubUiStore((state) => state.setForm);
  const setLoading = useStrategyHubUiStore((state) => state.setLoading);
  const setError = useStrategyHubUiStore((state) => state.setError);
  const setNotice = useStrategyHubUiStore((state) => state.setNotice);
  const loadSeqRef = useRef(0);

  const selectedStrategies = useMemo(
    () => strategies.filter((strategy) => form.strategies.includes(strategy.key)),
    [form.strategies, strategies],
  );

  const setTab = useCallback((nextTab: StrategyHubTab) => {
    setLoading((current) => (nextTab === tab ? current : "tab-switch"));
    setTabState(nextTab);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", nextTab);
      window.history.replaceState({}, "", `${url.pathname}${url.search}`);
    }
  }, [tab]);

  useEffect(() => {
    if (loading !== "tab-switch") return undefined;
    const timer = window.setTimeout(() => {
      setLoading((current) => (current === "tab-switch" ? "" : current));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [loading, tab]);

  const load = useCallback(async () => {
    const seq = loadSeqRef.current + 1;
    loadSeqRef.current = seq;
    setLoading("load");
    setError("");
    const workspaceResult = await Promise.allSettled([strategiesApi.getStrategyWorkspaceBff()]);
    if (loadSeqRef.current !== seq) return;
    const workspace = workspaceResult[0];
    if (workspace.status === "fulfilled") {
      const payload = workspace.value;
      const visibleStrategies = (payload.strategy_meta?.strategies ?? []).filter(
        (strategy) => strategy.enabled !== false && strategy.visibility !== "hidden",
      );
      setStrategies(visibleStrategies);
      if (visibleStrategies.length) {
        setForm((current) => current.strategies.length
          ? current
          : { ...current, strategies: visibleStrategies.slice(0, 2).map((strategy) => strategy.key) });
      }
      setPresets(payload.presets?.presets ?? []);
      setRuns(payload.recent_runs?.items ?? []);
      applyBacktestVerdictThresholds(payload.verdict_thresholds);
      if (payload.partial_errors.length) {
        setNotice("部分策略数据加载失败，可稍后重试。");
      }
    } else {
      setError(toMessage(workspace.reason));
    }
    if (loadSeqRef.current === seq) setLoading("");
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const updateForm = useCallback((patch: Partial<StrategyQuickForm>) => {
    setForm((current) => ({ ...current, ...patch }));
  }, []);

  const toggleStrategy = useCallback((key: string) => {
    setForm((current) => {
      const exists = current.strategies.includes(key);
      return {
        ...current,
        strategies: exists
          ? current.strategies.filter((item) => item !== key)
          : [...current.strategies, key],
      };
    });
  }, []);

  const applyPreset = useCallback((preset: StrategyPreset) => {
    const config = preset.config ?? {};
    setForm((current) => ({
      ...current,
      name: preset.name,
      start_date: rangeStart(String(config.range ?? "12m")),
      end_date: shiftDate(0),
      initial_capital: String(config.initial_capital ?? current.initial_capital),
      execution_model: normalizeExecutionModel(config.execution_model, current.execution_model),
      max_position_pct: String(config.max_position_pct ?? current.max_position_pct),
      max_single_order_pct: String(config.max_single_order_pct ?? Math.max(Number(config.max_position_pct ?? current.max_position_pct) / 2, 1)),
      max_positions: String(config.max_positions ?? current.max_positions),
      max_daily_loss_pct: String(config.max_daily_loss_pct ?? current.max_daily_loss_pct),
      min_cash_reserve: String(config.min_cash_reserve ?? current.min_cash_reserve),
      benchmark: String(config.benchmark ?? current.benchmark),
      strategies: Array.isArray(config.strategies)
        ? config.strategies.map(String)
        : current.strategies,
    }));
    setNotice(`已套用预设：${preset.name}`);
  }, []);

  const submit = useCallback(async (): Promise<boolean> => {
    setLoading("submit");
    setError("");
    setNotice("");
    try {
      validateForm(form);
      const payload: BacktestCreateRequest = {
        name: form.name.trim(),
        start_date: form.start_date,
        end_date: form.end_date,
        initial_capital: parsePositive(form.initial_capital),
        strategies: form.strategies,
        execution_model: form.execution_model,
        benchmark: form.benchmark.trim() || "000300",
        risk_limits: {
          max_position_pct: parsePercent(form.max_position_pct),
          max_positions: Math.max(1, Math.round(parsePositive(form.max_positions))),
          max_daily_loss_pct: parsePercent(form.max_daily_loss_pct),
          max_single_order_pct: parsePercent(form.max_single_order_pct),
          min_cash_reserve: parsePositive(form.min_cash_reserve),
        },
      };
      const result = await backtestsApi.createBacktest(payload);
      setConfirmOpen(false);
      setNotice(result.message || `回测任务 #${result.run_id ?? result.id ?? "--"} 已提交`);
      const runResult = await backtestsApi.listBacktests({ limit: 8, offset: 0 });
      setRuns(runResult.items ?? []);
      return true;
    } catch (err) {
      setError(toMessage(err));
      return false;
    } finally {
      setLoading("");
    }
  }, [form]);

  const submitQuickBacktest = useCallback(async (): Promise<boolean> => {
    setLoading("quick-submit");
    setError("");
    setNotice("");
    const productionStrategies = strategies
      .filter((strategy) =>
        strategy.enabled !== false &&
        strategy.visibility === "full" &&
        (strategy.tier === "core" || strategy.tier === "auxiliary")
      )
      .map((strategy) => strategy.key);
    try {
      const selected = form.strategies.length ? form.strategies : productionStrategies;
      const payload: BacktestCreateRequest = {
        name: "一键快速回测",
        start_date: form.start_date || shiftDate(-183),
        end_date: form.end_date || shiftDate(0),
        initial_capital: 500000,
        strategies: selected.length ? selected : ["first_board", "volume_shrink"],
        execution_model: "conservative_slippage",
        benchmark: "000300",
        risk_limits: {
          max_position_pct: 0.3,
          max_positions: 8,
          max_daily_loss_pct: 0.05,
          max_single_order_pct: 0.15,
          min_cash_reserve: 5000,
        },
      };
      const result = await backtestsApi.createBacktest(payload);
      setNotice(result.message || `一键回测任务 #${result.run_id ?? result.id ?? "--"} 已提交，预计 2-5 分钟。`);
      const runResult = await backtestsApi.listBacktests({ limit: 8, offset: 0 });
      setRuns(runResult.items ?? []);
      setTab("history");
      return true;
    } catch (err) {
      setError(toMessage(err));
      return false;
    } finally {
      setLoading("");
    }
  }, [form.end_date, form.start_date, form.strategies, setTab, strategies]);

  const selectedStrategyNames = useMemo(() => {
    const nameByKey = new Map(strategies.map((strategy) => [strategy.key, strategy.display_name || strategy.name || strategy.key]));
    return form.strategies.map((key) => nameByKey.get(key) || key);
  }, [form.strategies, strategies]);

  return {
    tab,
    setTab,
    strategies,
    presets,
    runs,
    form,
    selectedStrategies,
    selectedStrategyNames,
    confirmOpen,
    setConfirmOpen,
    loading,
    error,
    notice,
    load,
    updateForm,
    toggleStrategy,
    applyPreset,
    submit,
    submitQuickBacktest,
  };
}

function validateForm(form: StrategyQuickForm) {
  if (!form.name.trim()) throw new Error("请填写回测名称");
  if (!form.start_date || !form.end_date) throw new Error("请选择回测时间范围");
  if (new Date(form.start_date) > new Date(form.end_date)) throw new Error("开始日期不能晚于结束日期");
  if (!form.strategies.length) throw new Error("至少选择一个策略");
  parsePositive(form.initial_capital);
  parsePositive(form.max_positions);
  parsePositive(form.max_daily_loss_pct);
  parsePositive(form.max_single_order_pct);
  parsePositive(form.min_cash_reserve);
}

function parsePositive(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error("数值必须大于 0");
  }
  return parsed;
}

function parsePercent(value: string): number {
  const parsed = parsePositive(value);
  return parsed > 1 ? parsed / 100 : parsed;
}

function normalizeExecutionModel(value: unknown, fallback: BacktestExecutionModel): BacktestExecutionModel {
  if (
    value === "conservative_slippage" ||
    value === "open_price" ||
    value === "close_price" ||
    value === "next_open" ||
    value === "vwap" ||
    value === "market_impact"
  ) {
    return value;
  }
  return fallback;
}

function rangeStart(range: string): string {
  if (range === "24m") return shiftDate(-730);
  if (range === "6m") return shiftDate(-183);
  return shiftDate(-365);
}

function shiftDate(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function toMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
