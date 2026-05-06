import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, request } from "../../api/base";
import {
  backtestsApi,
  type BacktestAttributionResponse,
  type BacktestCompareResponse,
  type BacktestMonthlyReturnsResponse,
  type BacktestOptimizationDetail,
  type BacktestOptimizationSummary,
  type BacktestParamGrid,
  type BacktestRunDetail,
  type BacktestRunSummary,
  type BacktestStatus,
  type BacktestStrategyCorrelationResponse,
  type BacktestTrade,
  type BacktestValidationDetail,
  type BacktestValidationSummary,
  type EquityPoint,
} from "../../api/backtests";
import type { BacktestFormState } from "./BacktestDashboard";
import type { OptimizationFormState, ValidationFormState } from "./BacktestResearchPanel";

interface StrategyStreamTokenResponse {
  stream_token: string;
  expires_in: number;
}

interface StrategyProgressMessage {
  type: "progress" | "error" | "ping";
  task_id?: number;
  status?: BacktestStatus;
  progress_pct?: number;
  message?: string;
  completed?: boolean;
}

type ProgressTask = {
  id: number;
  status: BacktestStatus;
  progress?: number | null;
  progress_pct?: number | null;
  error_message?: string | null;
};

export const initialBacktestForm: BacktestFormState = {
  name: "低吸策略组合回测",
  start_date: "2025-01-02",
  end_date: "2026-04-30",
  initial_capital: "500000",
  strategies: ["first_board", "volume_shrink"],
  execution_model: "open_price",
  max_position_pct: "30",
  max_positions: "8",
  max_daily_loss_pct: "5",
  max_single_order_pct: "30",
  min_cash_reserve: "5000",
  benchmark: "000300",
};

const initialOptimizationForm: OptimizationFormState = {
  name: "first_board 参数优化",
  strategy: "first_board",
  train_start: "2024-01-02",
  train_end: "2025-12-31",
  test_start: "2026-01-02",
  test_end: "2026-04-30",
  initial_capital: "500000",
  execution_model: "open_price",
  optimization_target: "sharpe",
  min_score: "70,75,80,85,90",
  max_position_pct: "0.2,0.3",
  max_holding_days: "3,5,7,10",
  stop_loss_pct: "-0.03,-0.05,-0.07",
  take_profit_pct: "0.08,0.12",
};

const initialValidationForm: ValidationFormState = {
  name: "first_board Walk-Forward 验证",
  strategy: "first_board",
  start_date: "2024-01-02",
  end_date: "2026-04-30",
  window_count: "4",
  train_ratio: "0.75",
  initial_capital: "500000",
  execution_model: "open_price",
  optimization_target: "sharpe",
};

export type BacktestDashboardActiveSection =
  | "all"
  | "quick"
  | "history"
  | "optimization"
  | "validation"
  | "compare"
  | "none";

export function useBacktestDashboard(activeSection: BacktestDashboardActiveSection = "all") {
  const [form, setForm] = useState<BacktestFormState>(initialBacktestForm);
  const [runs, setRuns] = useState<BacktestRunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<BacktestRunDetail | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [optimizationForm, setOptimizationForm] = useState<OptimizationFormState>(initialOptimizationForm);
  const [optimizations, setOptimizations] = useState<BacktestOptimizationSummary[]>([]);
  const [selectedOptimizationId, setSelectedOptimizationId] = useState<number | null>(null);
  const [selectedOptimization, setSelectedOptimization] = useState<BacktestOptimizationDetail | null>(null);
  const [validationForm, setValidationForm] = useState<ValidationFormState>(initialValidationForm);
  const [validations, setValidations] = useState<BacktestValidationSummary[]>([]);
  const [selectedValidationId, setSelectedValidationId] = useState<number | null>(null);
  const [selectedValidation, setSelectedValidation] = useState<BacktestValidationDetail | null>(null);
  const [compareRunIds, setCompareRunIds] = useState("");
  const [compareResult, setCompareResult] = useState<BacktestCompareResponse | null>(null);
  const [monthlyReturns, setMonthlyReturns] = useState<BacktestMonthlyReturnsResponse | null>(null);
  const [attribution, setAttribution] = useState<BacktestAttributionResponse | null>(null);
  const [correlation, setCorrelation] = useState<BacktestStrategyCorrelationResponse | null>(null);
  const [researchLoading, setResearchLoading] = useState("");
  const [researchError, setResearchError] = useState("");
  const [researchNotice, setResearchNotice] = useState("");
  const selectedOptimizationIdRef = useRef<number | null>(null);
  const selectedValidationIdRef = useRef<number | null>(null);

  useEffect(() => {
    selectedOptimizationIdRef.current = selectedOptimizationId;
  }, [selectedOptimizationId]);

  useEffect(() => {
    selectedValidationIdRef.current = selectedValidationId;
  }, [selectedValidationId]);

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

  const loadResearch = useCallback(async () => {
    setResearchLoading("research");
    setResearchError("");
    try {
      const [optimizationList, validationList] = await Promise.allSettled([
        backtestsApi.listOptimizations({ limit: 20, offset: 0 }),
        backtestsApi.listValidations({ limit: 20, offset: 0 }),
      ]);
      if (optimizationList.status === "fulfilled") {
        const items = optimizationList.value.items ?? [];
        setOptimizations(items);
        const nextId = selectedOptimizationIdRef.current ?? items[0]?.id ?? null;
        selectedOptimizationIdRef.current = nextId;
        setSelectedOptimizationId(nextId);
        if (nextId) {
          const detail = await backtestsApi.getOptimization(nextId);
          setSelectedOptimization(detail);
        } else {
          setSelectedOptimization(null);
        }
      }
      if (validationList.status === "fulfilled") {
        const items = validationList.value.items ?? [];
        setValidations(items);
        const nextId = selectedValidationIdRef.current ?? items[0]?.id ?? null;
        selectedValidationIdRef.current = nextId;
        setSelectedValidationId(nextId);
        if (nextId) {
          const detail = await backtestsApi.getValidation(nextId);
          setSelectedValidation(detail);
        } else {
          setSelectedValidation(null);
        }
      }
    } catch (err) {
      setResearchError(errorMessage(err));
    } finally {
      setResearchLoading("");
    }
  }, []);

  useEffect(() => {
    if (activeSection === "none") return;
    if (["all", "quick", "history", "compare"].includes(activeSection)) {
      void loadRuns();
    }
  }, [activeSection, loadRuns]);

  useEffect(() => {
    if (["all", "optimization", "validation", "compare"].includes(activeSection)) {
      void loadResearch();
    }
  }, [activeSection, loadResearch]);

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

  const selectedOptimizationStatus = selectedOptimization?.status ?? null;
  const selectedValidationStatus = selectedValidation?.status ?? null;

  const patchOptimization = useCallback((optimizationId: number, patch: Partial<ProgressTask>) => {
    setSelectedOptimization((current) => (current?.id === optimizationId ? compactProgressPatch(current, patch) : current));
    setOptimizations((current) => current.map((item) => (item.id === optimizationId ? compactProgressPatch(item, patch) : item)));
  }, []);

  const patchValidation = useCallback((validationId: number, patch: Partial<ProgressTask>) => {
    setSelectedValidation((current) => (current?.id === validationId ? compactProgressPatch(current, patch) : current));
    setValidations((current) => current.map((item) => (item.id === validationId ? compactProgressPatch(item, patch) : item)));
  }, []);

  const refreshOptimizationDetail = useCallback(async (optimizationId: number) => {
    const detail = await backtestsApi.getOptimization(optimizationId);
    setSelectedOptimization(detail);
    setOptimizations((current) => current.map((item) => (item.id === optimizationId ? { ...item, ...detail } : item)));
  }, []);

  const refreshValidationDetail = useCallback(async (validationId: number) => {
    const detail = await backtestsApi.getValidation(validationId);
    setSelectedValidation(detail);
    setValidations((current) => current.map((item) => (item.id === validationId ? { ...item, ...detail } : item)));
  }, []);

  useEffect(() => {
    if (!selectedOptimizationId || !selectedOptimizationStatus || !isActiveStatus(selectedOptimizationStatus)) {
      return undefined;
    }
    const optimizationId = selectedOptimizationId;
    return startStrategyProgressStream({
      taskType: "optimize",
      taskId: optimizationId,
      currentStatus: selectedOptimizationStatus,
      onPatch: (patch) => patchOptimization(optimizationId, patch),
      onComplete: () => void refreshOptimizationDetail(optimizationId),
      onFallback: () => void refreshOptimizationDetail(optimizationId),
      onError: setResearchError,
    });
  }, [patchOptimization, refreshOptimizationDetail, selectedOptimizationId, selectedOptimizationStatus]);

  useEffect(() => {
    if (!selectedValidationId || !selectedValidationStatus || !isActiveStatus(selectedValidationStatus)) {
      return undefined;
    }
    const validationId = selectedValidationId;
    return startStrategyProgressStream({
      taskType: "validate",
      taskId: validationId,
      currentStatus: selectedValidationStatus,
      onPatch: (patch) => patchValidation(validationId, patch),
      onComplete: () => void refreshValidationDetail(validationId),
      onFallback: () => void refreshValidationDetail(validationId),
      onError: setResearchError,
    });
  }, [patchValidation, refreshValidationDetail, selectedValidationId, selectedValidationStatus]);

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

  const onOptimizationFormChange = useCallback((patch: Partial<OptimizationFormState>) => {
    setOptimizationForm((current) => ({ ...current, ...patch }));
  }, []);

  const submitOptimization = useCallback(async () => {
    setResearchLoading("optimize-submit");
    setResearchError("");
    setResearchNotice("");
    try {
      validateOptimizationForm(optimizationForm);
      const response = await backtestsApi.createOptimization({
        name: optimizationForm.name.trim(),
        strategy: optimizationForm.strategy,
        param_grid: buildParamGrid(optimizationForm),
        train_start: optimizationForm.train_start,
        train_end: optimizationForm.train_end,
        test_start: optimizationForm.test_start,
        test_end: optimizationForm.test_end,
        optimization_target: optimizationForm.optimization_target || "sharpe",
        initial_capital: parsePositiveNumber(optimizationForm.initial_capital, "初始资金"),
        execution_model: optimizationForm.execution_model,
      });
      setResearchNotice(response.message || `优化任务 #${response.id ?? response.run_id ?? "--"} 已提交`);
      await loadResearch();
    } catch (err) {
      setResearchError(errorMessage(err));
    } finally {
      setResearchLoading("");
    }
  }, [loadResearch, optimizationForm]);

  const selectOptimization = useCallback((optimizationId: number) => {
    selectedOptimizationIdRef.current = optimizationId;
    setSelectedOptimizationId(optimizationId);
    setResearchLoading("optimization-detail");
    setResearchError("");
    backtestsApi.getOptimization(optimizationId)
      .then(setSelectedOptimization)
      .catch((err) => setResearchError(errorMessage(err)))
      .finally(() => setResearchLoading(""));
  }, []);

  const cancelOptimization = useCallback(async (optimizationId: number) => {
    setResearchLoading("optimization-cancel");
    setResearchError("");
    try {
      const response = await backtestsApi.cancelOptimization(optimizationId);
      setResearchNotice(response.message || `优化任务 #${optimizationId} 已请求取消`);
      await loadResearch();
    } catch (err) {
      setResearchError(errorMessage(err));
    } finally {
      setResearchLoading("");
    }
  }, [loadResearch]);

  const deleteOptimization = useCallback(async (optimizationId: number) => {
    setResearchLoading("optimization-delete");
    setResearchError("");
    try {
      const response = await backtestsApi.deleteOptimization(optimizationId);
      setResearchNotice(response.message || `优化任务 #${optimizationId} 已删除`);
      if (selectedOptimizationId === optimizationId) {
        selectedOptimizationIdRef.current = null;
        setSelectedOptimizationId(null);
        setSelectedOptimization(null);
      }
      await loadResearch();
    } catch (err) {
      setResearchError(errorMessage(err));
    } finally {
      setResearchLoading("");
    }
  }, [loadResearch, selectedOptimizationId]);

  const onValidationFormChange = useCallback((patch: Partial<ValidationFormState>) => {
    setValidationForm((current) => ({ ...current, ...patch }));
  }, []);

  const submitValidation = useCallback(async () => {
    setResearchLoading("validate-submit");
    setResearchError("");
    setResearchNotice("");
    try {
      validateValidationForm(validationForm);
      const response = await backtestsApi.createValidation({
        name: validationForm.name.trim(),
        strategy: validationForm.strategy,
        start_date: validationForm.start_date,
        end_date: validationForm.end_date,
        window_count: Math.max(1, Math.round(parsePositiveNumber(validationForm.window_count, "窗口数"))),
        train_ratio: parsePositiveNumber(validationForm.train_ratio, "训练比例"),
        optimization_target: validationForm.optimization_target || "sharpe",
        initial_capital: parsePositiveNumber(validationForm.initial_capital, "初始资金"),
        execution_model: validationForm.execution_model,
      });
      setResearchNotice(response.message || `验证任务 #${response.id ?? response.run_id ?? "--"} 已提交`);
      await loadResearch();
    } catch (err) {
      setResearchError(errorMessage(err));
    } finally {
      setResearchLoading("");
    }
  }, [loadResearch, validationForm]);

  const selectValidation = useCallback((validationId: number) => {
    selectedValidationIdRef.current = validationId;
    setSelectedValidationId(validationId);
    setResearchLoading("validation-detail");
    setResearchError("");
    backtestsApi.getValidation(validationId)
      .then(setSelectedValidation)
      .catch((err) => setResearchError(errorMessage(err)))
      .finally(() => setResearchLoading(""));
  }, []);

  const cancelValidation = useCallback(async (validationId: number) => {
    setResearchLoading("validation-cancel");
    setResearchError("");
    try {
      const response = await backtestsApi.cancelValidation(validationId);
      setResearchNotice(response.message || `验证任务 #${validationId} 已请求取消`);
      await loadResearch();
    } catch (err) {
      setResearchError(errorMessage(err));
    } finally {
      setResearchLoading("");
    }
  }, [loadResearch]);

  const deleteValidation = useCallback(async (validationId: number) => {
    setResearchLoading("validation-delete");
    setResearchError("");
    try {
      const response = await backtestsApi.deleteValidation(validationId);
      setResearchNotice(response.message || `验证任务 #${validationId} 已删除`);
      if (selectedValidationId === validationId) {
        selectedValidationIdRef.current = null;
        setSelectedValidationId(null);
        setSelectedValidation(null);
      }
      await loadResearch();
    } catch (err) {
      setResearchError(errorMessage(err));
    } finally {
      setResearchLoading("");
    }
  }, [loadResearch, selectedValidationId]);

  const runCompare = useCallback(async () => {
    setResearchLoading("compare");
    setResearchError("");
    try {
      const runIds = parseRunIds(compareRunIds);
      const result = await backtestsApi.compareBacktests(runIds);
      setCompareResult(result);
    } catch (err) {
      setResearchError(errorMessage(err));
    } finally {
      setResearchLoading("");
    }
  }, [compareRunIds]);

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
    research: {
      optimizationForm,
      optimizations,
      selectedOptimizationId,
      selectedOptimization,
      validationForm,
      validations,
      selectedValidationId,
      selectedValidation,
      completedRuns: runs.filter((run) => run.status === "succeeded" || run.status === "completed"),
      compareRunIds,
      compareResult,
      monthlyReturns,
      attribution,
      correlation,
      loading: researchLoading,
      error: researchError,
      notice: researchNotice,
    },
    researchActions: {
      onOptimizationFormChange,
      onSubmitOptimization: submitOptimization,
      onSelectOptimization: selectOptimization,
      onCancelOptimization: cancelOptimization,
      onDeleteOptimization: deleteOptimization,
      onValidationFormChange,
      onSubmitValidation: submitValidation,
      onSelectValidation: selectValidation,
      onCancelValidation: cancelValidation,
      onDeleteValidation: deleteValidation,
      onCompareRunIdsChange: setCompareRunIds,
      onRunCompare: runCompare,
      onRefreshResearch: loadResearch,
    },
  };
}

function validateOptimizationForm(form: OptimizationFormState) {
  if (!form.name.trim()) {
    throw new Error("请填写优化任务名称");
  }
  if (!form.strategy) {
    throw new Error("请选择优化策略");
  }
  if (!form.train_start || !form.train_end || !form.test_start || !form.test_end) {
    throw new Error("请填写训练/验证日期范围");
  }
  if (form.train_start > form.train_end || form.test_start > form.test_end) {
    throw new Error("日期范围不合法");
  }
  if (!Object.keys(buildParamGrid(form)).length) {
    throw new Error("至少填写一个参数网格");
  }
  parsePositiveNumber(form.initial_capital, "初始资金");
}

function validateValidationForm(form: ValidationFormState) {
  if (!form.name.trim()) {
    throw new Error("请填写验证任务名称");
  }
  if (!form.strategy) {
    throw new Error("请选择验证策略");
  }
  if (!form.start_date || !form.end_date) {
    throw new Error("请填写验证日期范围");
  }
  if (form.start_date > form.end_date) {
    throw new Error("开始日期不能晚于结束日期");
  }
  parsePositiveNumber(form.window_count, "窗口数");
  parsePositiveNumber(form.train_ratio, "训练比例");
  parsePositiveNumber(form.initial_capital, "初始资金");
}

function buildParamGrid(form: OptimizationFormState): BacktestParamGrid {
  const entries: Array<[keyof OptimizationFormState, string]> = [
    ["min_score", "min_score"],
    ["max_position_pct", "max_position_pct"],
    ["max_holding_days", "max_holding_days"],
    ["stop_loss_pct", "stop_loss_pct"],
    ["take_profit_pct", "take_profit_pct"],
  ];
  return entries.reduce<BacktestParamGrid>((grid, [field, paramName]) => {
    const values = parseParamList(form[field]);
    if (values.length) {
      grid[paramName] = values;
    }
    return grid;
  }, {});
}

function parseParamList(value: string): Array<number | string> {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const parsed = Number(item);
      return Number.isFinite(parsed) ? parsed : item;
    });
}

function parseRunIds(value: string): number[] {
  const runIds = value
    .split(/[,\s]+/)
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item) && item > 0);
  if (!runIds.length) {
    throw new Error("请至少输入一个有效 run id");
  }
  return [...new Set(runIds)];
}

function validateForm(form: BacktestFormState) {
  if (!form.name.trim()) {
    throw new Error("请填写回测任务名称");
  }
  if (!form.start_date || !form.end_date) {
    throw new Error("请选择回测日期范围");
  }
  if (form.start_date > form.end_date) {
    throw new Error("开始日期不能晚于结束日期");
  }
  if (!form.strategies.length) {
    throw new Error("至少选择一个策略");
  }
  parsePositiveNumber(form.initial_capital, "初始资金");
  parsePositiveNumber(form.max_positions, "最大持仓数");
}

function parsePositiveNumber(value: string, label = "数值"): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${label}必须大于 0`);
  }
  return parsed;
}

function parseNullableNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  return parsePositiveNumber(trimmed);
}

function parsePercent(value: string): number {
  return parsePositiveNumber(value, "百分比") / 100;
}

function parseNullablePercent(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  return parsePercent(trimmed);
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "请求失败";
}

function isActiveStatus(status: BacktestStatus): boolean {
  return status === "pending" || status === "queued" || status === "running";
}

function compactProgressPatch<T extends ProgressTask>(item: T, patch: Partial<ProgressTask>): T {
  return {
    ...item,
    ...(patch.status ? { status: patch.status } : {}),
    ...(typeof patch.progress === "number" ? { progress: patch.progress } : {}),
    ...(typeof patch.progress_pct === "number" ? { progress_pct: patch.progress_pct } : {}),
    ...(patch.error_message ? { error_message: patch.error_message } : {}),
  };
}

function startStrategyProgressStream({
  taskType,
  taskId,
  currentStatus,
  onPatch,
  onComplete,
  onFallback,
  onError,
}: {
  taskType: "backtest" | "optimize" | "validate";
  taskId: number;
  currentStatus: BacktestStatus;
  onPatch: (patch: Partial<ProgressTask>) => void;
  onComplete: () => void;
  onFallback: () => void;
  onError: (message: string) => void;
}): () => void {
  let closed = false;
  let socket: WebSocket | null = null;
  let fallbackTimer: number | undefined;
  let reconnectTimer: number | undefined;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;

  const startFallback = () => {
    if (fallbackTimer || closed) return;
    fallbackTimer = window.setInterval(onFallback, 3000);
  };

  const closeSocket = () => {
    const currentSocket = socket;
    socket = null;
    if (currentSocket && currentSocket.readyState !== WebSocket.CLOSED) {
      currentSocket.close();
    }
  };

  const scheduleReconnect = () => {
    if (closed || fallbackTimer || reconnectTimer) return;
    if (reconnectAttempts >= maxReconnectAttempts) {
      startFallback();
      return;
    }
    reconnectAttempts += 1;
    const delayMs = Math.min(1000 * 2 ** (reconnectAttempts - 1), 16000);
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = undefined;
      connect();
    }, delayMs);
    closeSocket();
  };

  const connect = () => {
    request<StrategyStreamTokenResponse>("/strategy/stream-token", { method: "POST" })
      .then((payload) => {
        if (closed || !payload.stream_token) return;
        socket = new WebSocket(strategyProgressUrl(taskType, taskId, payload.stream_token));
        socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as StrategyProgressMessage;
            if (message.task_id !== taskId) return;
            if (message.type === "ping") return;
            reconnectAttempts = 0;
            if (message.type === "error") {
              onError(message.message || "策略任务进度连接异常，已切换轮询。");
              startFallback();
              return;
            }
            const patch: Partial<ProgressTask> = {
              status: message.status ?? currentStatus,
              progress: message.progress_pct,
              progress_pct: message.progress_pct,
            };
            onPatch(patch);
            if (message.completed) onComplete();
          } catch {
            scheduleReconnect();
          }
        };
        socket.onerror = scheduleReconnect;
        socket.onclose = (event) => {
          if (!closed && event.code !== 1000) {
            scheduleReconnect();
          };
        };
      })
      .catch(scheduleReconnect);
  };

  connect();

  return () => {
    closed = true;
    if (fallbackTimer) window.clearInterval(fallbackTimer);
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    closeSocket();
  };
}

function strategyProgressUrl(taskType: string, taskId: number, streamToken: string): string {
  const apiBase = API_BASE === "__NATIVE_API_BASE_REQUIRED__" ? "/api" : API_BASE;
  const base = apiBase.startsWith("http")
    ? apiBase.replace(/\/api\/?$/, "").replace(/^http/, "ws")
    : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;
  const params = new URLSearchParams({
    stream_token: streamToken,
    interval_seconds: "3",
  });
  return `${base}/ws/strategy/${encodeURIComponent(taskType)}/${encodeURIComponent(String(taskId))}?${params.toString()}`;
}
