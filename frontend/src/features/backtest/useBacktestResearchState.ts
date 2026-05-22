import { useCallback, useEffect, useRef } from "react";
import {
  backtestsApi,
  type BacktestAttributionResponse,
  type BacktestMonthlyReturnsResponse,
  type BacktestRunSummary,
  type BacktestStrategyCorrelationResponse,
} from "../../api/backtests";
import { useBacktestUiStore } from "../../stores/backtestUiStore";
import type { OptimizationFormState, ValidationFormState } from "./backtestForms";
import type { BacktestDashboardActiveSection } from "./useBacktestDashboard";
import {
  buildParamGrid,
  compactProgressPatch,
  errorMessage,
  isActiveStatus,
  parsePositiveNumber,
  parseRunIds,
  startStrategyProgressStream,
  type ProgressTask,
  validateOptimizationForm,
  validateValidationForm,
} from "./useBacktestDashboardHelpers";

interface UseBacktestResearchStateParams {
  activeSection: BacktestDashboardActiveSection;
  runs: BacktestRunSummary[];
  monthlyReturns: BacktestMonthlyReturnsResponse | null;
  attribution: BacktestAttributionResponse | null;
  correlation: BacktestStrategyCorrelationResponse | null;
}

export function useBacktestResearchState({
  activeSection,
  runs,
  monthlyReturns,
  attribution,
  correlation,
}: UseBacktestResearchStateParams) {
  const optimizationForm = useBacktestUiStore((state) => state.optimizationForm);
  const optimizations = useBacktestUiStore((state) => state.optimizations);
  const selectedOptimizationId = useBacktestUiStore((state) => state.selectedOptimizationId);
  const selectedOptimization = useBacktestUiStore((state) => state.selectedOptimization);
  const validationForm = useBacktestUiStore((state) => state.validationForm);
  const validations = useBacktestUiStore((state) => state.validations);
  const selectedValidationId = useBacktestUiStore((state) => state.selectedValidationId);
  const selectedValidation = useBacktestUiStore((state) => state.selectedValidation);
  const compareRunIds = useBacktestUiStore((state) => state.compareRunIds);
  const compareResult = useBacktestUiStore((state) => state.compareResult);
  const researchLoading = useBacktestUiStore((state) => state.researchLoading);
  const researchError = useBacktestUiStore((state) => state.researchError);
  const researchNotice = useBacktestUiStore((state) => state.researchNotice);
  const setOptimizationForm = useBacktestUiStore((state) => state.setOptimizationForm);
  const setOptimizations = useBacktestUiStore((state) => state.setOptimizations);
  const setSelectedOptimizationId = useBacktestUiStore((state) => state.setSelectedOptimizationId);
  const setSelectedOptimization = useBacktestUiStore((state) => state.setSelectedOptimization);
  const setValidationForm = useBacktestUiStore((state) => state.setValidationForm);
  const setValidations = useBacktestUiStore((state) => state.setValidations);
  const setSelectedValidationId = useBacktestUiStore((state) => state.setSelectedValidationId);
  const setSelectedValidation = useBacktestUiStore((state) => state.setSelectedValidation);
  const setCompareRunIds = useBacktestUiStore((state) => state.setCompareRunIds);
  const setCompareResult = useBacktestUiStore((state) => state.setCompareResult);
  const setResearchLoading = useBacktestUiStore((state) => state.setResearchLoading);
  const setResearchError = useBacktestUiStore((state) => state.setResearchError);
  const setResearchNotice = useBacktestUiStore((state) => state.setResearchNotice);
  const selectedOptimizationIdRef = useRef<number | null>(null);
  const selectedValidationIdRef = useRef<number | null>(null);

  useEffect(() => {
    selectedOptimizationIdRef.current = selectedOptimizationId;
  }, [selectedOptimizationId]);

  useEffect(() => {
    selectedValidationIdRef.current = selectedValidationId;
  }, [selectedValidationId]);

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
        setSelectedOptimization(nextId ? await backtestsApi.getOptimization(nextId) : null);
      }
      if (validationList.status === "fulfilled") {
        const items = validationList.value.items ?? [];
        setValidations(items);
        const nextId = selectedValidationIdRef.current ?? items[0]?.id ?? null;
        selectedValidationIdRef.current = nextId;
        setSelectedValidationId(nextId);
        setSelectedValidation(nextId ? await backtestsApi.getValidation(nextId) : null);
      }
    } catch (err) {
      setResearchError(errorMessage(err));
    } finally {
      setResearchLoading("");
    }
  }, []);

  useEffect(() => {
    if (["all", "optimization", "validation", "compare"].includes(activeSection)) {
      void loadResearch();
    }
  }, [activeSection, loadResearch]);

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

  const selectedOptimizationStatus = selectedOptimization?.status ?? null;
  const selectedValidationStatus = selectedValidation?.status ?? null;

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
        auto_promote_state_params: validationForm.auto_promote_state_params,
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

  const promoteValidationStateParams = useCallback(async (validationId: number) => {
    setResearchLoading("validation-promote");
    setResearchError("");
    try {
      const response = await backtestsApi.promoteValidationStateParams(validationId, true);
      setResearchNotice(`分市场状态参数晋级完成：${String(response.promoted_count ?? 0)} 个，跳过 ${String(response.skipped_count ?? 0)} 个。`);
      await loadResearch();
    } catch (err) {
      setResearchError(errorMessage(err));
    } finally {
      setResearchLoading("");
    }
  }, [loadResearch]);

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
      onPromoteValidationStateParams: promoteValidationStateParams,
      onCompareRunIdsChange: setCompareRunIds,
      onRunCompare: runCompare,
      onRefreshResearch: loadResearch,
    },
  };
}
