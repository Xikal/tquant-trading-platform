import { useCallback, useEffect, useState } from "react";
import { backtestsApi, type BacktestRunDetail, type BacktestRunSummary, type BacktestTrade, type EquityPoint } from "../../api/backtests";
import type { BacktestFormState } from "./BacktestDashboard";

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

export function useBacktestDashboard() {
  const [form, setForm] = useState<BacktestFormState>(initialBacktestForm);
  const [runs, setRuns] = useState<BacktestRunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<BacktestRunDetail | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadDetail = useCallback(async (runId: number) => {
    setLoading("detail");
    setError("");
    try {
      const [detailResult, equityResult, tradesResult] = await Promise.allSettled([
        backtestsApi.getBacktest(runId),
        backtestsApi.getBacktestEquity(runId),
        backtestsApi.getBacktestTrades(runId, { page: 1, pageSize: 50 }),
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
      const rejected = [detailResult, equityResult, tradesResult].find(
        (item): item is PromiseRejectedResult => item.status === "rejected"
      );
      if (rejected && detailResult.status !== "fulfilled") {
        throw rejected.reason;
      }
    } catch (err) {
      setError(errorMessage(err));
      setSelectedRun(null);
    } finally {
      setLoading("");
    }
  }, []);

  const loadRuns = useCallback(async () => {
    setLoading("list");
    setError("");
    try {
      const result = await backtestsApi.listBacktests({ page: 1, pageSize: 20 });
      setRuns(result.items ?? []);
      const nextRun = result.items?.[0];
      if (nextRun) {
        await loadDetail(nextRun.id);
      } else {
        setSelectedRun(null);
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
    void loadRuns();
  }, [loadRuns]);

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
  };
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
