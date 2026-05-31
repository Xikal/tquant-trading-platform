import { useCallback, useEffect } from "react";
import {
  backtestsApi,
  type BacktestAttributionResponse,
  type BacktestMonthlyReturnsResponse,
  type BacktestRunDetail,
  type BacktestRunSummary,
  type BacktestStrategyCorrelationResponse,
  type BacktestTrade,
  type EquityPoint,
} from "../../api/backtests";
import { useBacktestUiStore } from "../../stores/backtestUiStore";
import { useServerState } from "../../state/serverState";
import type { BacktestFormState } from "./backtestForms";
import {
  compactProgressPatch,
  errorMessage,
  isActiveStatus,
  parseNullablePercent,
  parseNullableNumber,
  parsePercent,
  parsePositiveNumber,
  startStrategyProgressStream,
  validateForm,
} from "./useBacktestDashboardHelpers";
import { useBacktestResearchState } from "./useBacktestResearchState";

export type BacktestDashboardActiveSection =
  | "all"
  | "quick"
  | "history"
  | "optimization"
  | "validation"
  | "compare"
  | "none";

const BACKTEST_SERVER_KEYS = {
  runs: ["backtest", "runs"] as const,
  selectedRun: ["backtest", "selected-run"] as const,
  equity: ["backtest", "equity"] as const,
  trades: ["backtest", "trades"] as const,
  monthlyReturns: ["backtest", "monthly-returns"] as const,
  attribution: ["backtest", "attribution"] as const,
  correlation: ["backtest", "correlation"] as const,
};

export function useBacktestDashboard(activeSection: BacktestDashboardActiveSection = "all") {
  const form = useBacktestUiStore((state) => state.form);
  const [runs, setRuns] = useServerState<BacktestRunSummary[]>(BACKTEST_SERVER_KEYS.runs, []);
  const [selectedRun, setSelectedRun] = useServerState<BacktestRunDetail | null>(BACKTEST_SERVER_KEYS.selectedRun, null);
  const [equity, setEquity] = useServerState<EquityPoint[]>(BACKTEST_SERVER_KEYS.equity, []);
  const [trades, setTrades] = useServerState<BacktestTrade[]>(BACKTEST_SERVER_KEYS.trades, []);
  const loading = useBacktestUiStore((state) => state.loading);
  const error = useBacktestUiStore((state) => state.error);
  const notice = useBacktestUiStore((state) => state.notice);
  const [monthlyReturns, setMonthlyReturns] = useServerState<BacktestMonthlyReturnsResponse | null>(
    BACKTEST_SERVER_KEYS.monthlyReturns,
    null,
  );
  const [attribution, setAttribution] = useServerState<BacktestAttributionResponse | null>(BACKTEST_SERVER_KEYS.attribution, null);
  const [correlation, setCorrelation] = useServerState<BacktestStrategyCorrelationResponse | null>(
    BACKTEST_SERVER_KEYS.correlation,
    null,
  );
  const setForm = useBacktestUiStore((state) => state.setForm);
  const setLoading = useBacktestUiStore((state) => state.setLoading);
  const setError = useBacktestUiStore((state) => state.setError);
  const setNotice = useBacktestUiStore((state) => state.setNotice);

  const loadDetail = useCallback(async (runId: number) => {
    setLoading("detail");
    setError("");
    try {
      const [detailResult, equityResult, tradesResult, monthlyResult, attributionResult, correlationResult] = await Promise.allSettled([
        backtestsApi.getBacktest(runId),
        backtestsApi.getBacktestEquity(runId),
        backtestsApi.getBacktestTrades(runId, { limit: 50, offset: 0 }),
        backtestsApi.getMonthlyReturns(runId),
        backtestsApi.getAttribution(runId),
        backtestsApi.getStrategyCorrelation(runId),
      ]);
      if (detailResult.status === "fulfilled") {
        setSelectedRun(detailResult.value);
      }
      if (equityResult.status === "fulfilled") {
        setEquity(equityResult.value);
      } else {
        setEquity([]);
      }
      if (tradesResult.status === "fulfilled") {
        setTrades(tradesResult.value.items ?? []);
      } else {
        setTrades([]);
      }
      setMonthlyReturns(monthlyResult.status === "fulfilled" ? monthlyResult.value : null);
      setAttribution(attributionResult.status === "fulfilled" ? attributionResult.value : null);
      setCorrelation(correlationResult.status === "fulfilled" ? correlationResult.value : null);
      const rejected = [detailResult, equityResult, tradesResult].find(
        (item): item is PromiseRejectedResult => item.status === "rejected"
      );
      if (rejected && detailResult.status !== "fulfilled") {
        throw rejected.reason;
      }
    } catch (err) {
      setError(errorMessage(err));
      setSelectedRun(null);
      setMonthlyReturns(null);
      setAttribution(null);
      setCorrelation(null);
    } finally {
      setLoading("");
    }
  }, []);

  const loadRuns = useCallback(async () => {
    setLoading("list");
    setError("");
    try {
      const result = await backtestsApi.listBacktests({ limit: 20, offset: 0 });
      setRuns(result.items ?? []);
      const nextRun = result.items?.[0];
      if (nextRun) {
        await loadDetail(nextRun.id);
      } else {
        setSelectedRun(null);
        setMonthlyReturns(null);
        setAttribution(null);
        setCorrelation(null);
        setEquity([]);
        setTrades([]);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading("");
    }
  }, [loadDetail]);

  useEffect(() => {
    if (activeSection === "none") return;
    if (["all", "quick", "history", "compare"].includes(activeSection)) {
      void loadRuns();
    }
  }, [activeSection, loadRuns]);

  const selectedRunId = selectedRun?.id ?? null;
  const selectedRunStatus = selectedRun?.status ?? null;

  useEffect(() => {
    if (!selectedRunId || !selectedRunStatus || !isActiveStatus(selectedRunStatus)) {
      return undefined;
    }
    const runId = selectedRunId;
    return startStrategyProgressStream({
      taskType: "backtest",
      taskId: runId,
      currentStatus: selectedRunStatus,
      onPatch: (patch) => {
        setSelectedRun((current) => (current?.id === runId ? compactProgressPatch(current, patch) : current));
        setRuns((current) => current.map((run) => (run.id === runId ? compactProgressPatch(run, patch) : run)));
      },
      onComplete: () => void loadDetail(runId),
      onFallback: () => void loadDetail(runId),
      onError: setError,
    });
  }, [loadDetail, selectedRunId, selectedRunStatus]);

  const onFormChange = useCallback((patch: Partial<BacktestFormState>) => {
    setForm((current) => ({ ...current, ...patch }));
  }, []);

  const onToggleStrategy = useCallback((strategy: string) => {
    setForm((current) => {
      const exists = current.strategies.includes(strategy);
      return {
        ...current,
        strategies: exists
          ? current.strategies.filter((item) => item !== strategy)
          : [...current.strategies, strategy],
      };
    });
  }, []);

  const submit = useCallback(async () => {
    setLoading("submit");
    setError("");
    setNotice("");
    try {
      validateForm(form);
      const response = await backtestsApi.createBacktest({
        name: form.name.trim(),
        start_date: form.start_date,
        end_date: form.end_date,
        initial_capital: parsePositiveNumber(form.initial_capital),
        strategies: form.strategies,
        execution_model: form.execution_model,
        resource_tier: form.resource_tier,
        risk_limits: {
          max_position_pct: parsePercent(form.max_position_pct),
          max_positions: Math.max(1, Math.round(parsePositiveNumber(form.max_positions))),
          max_daily_loss_pct: parseNullablePercent(form.max_daily_loss_pct),
          max_single_order_pct: parseNullablePercent(form.max_single_order_pct),
          min_cash_reserve: parseNullableNumber(form.min_cash_reserve),
        },
        benchmark: form.benchmark.trim() || "000300",
      });
      setNotice(response.message || `回测任务 #${response.run_id ?? response.id ?? "--"} 已提交`);
      await loadRuns();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading("");
    }
  }, [form, loadRuns]);

  const selectRun = useCallback((runId: number) => {
    void loadDetail(runId);
  }, [loadDetail]);

  const cancelRun = useCallback(async (runId: number) => {
    setLoading("cancel");
    setError("");
    try {
      const response = await backtestsApi.cancelBacktest(runId);
      setNotice(response.message || `回测任务 #${runId} 已请求取消`);
      await loadRuns();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading("");
    }
  }, [loadRuns]);

  const { research, researchActions } = useBacktestResearchState({
    activeSection,
    runs,
    monthlyReturns,
    attribution,
    correlation,
  });

  return {
    form,
    runs,
    selectedRun,
    equity,
    trades,
    loading,
    error,
    notice,
    onFormChange,
    onToggleStrategy,
    submit,
    loadRuns,
    selectRun,
    cancelRun,
    research,
    researchActions,
  };
}
