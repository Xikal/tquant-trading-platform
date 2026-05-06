import { useCallback, useState } from "react";
import { api } from "../../api/client";
import type {
  BacktestResult,
  BacktestRun,
  LowBuyExecutionBacktestResult,
  LowBuyPriorityBoardResult,
  LowBuyTradeLifecycle,
  ReplayItem,
  StrategyValidationReport,
} from "../../types";
import { DEFAULT_PLAYBOOK_STRATEGY } from "./workspaceConstants";
import { errorMessage, parseNumber } from "./workspaceFormatters";
import type { BacktestDraft } from "./workspaceTypes";

type WorkspaceLoader = <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;

const VALIDATION_STRATEGIES = [
  "first_board",
  "volume_shrink",
  "late_session_strong_support",
  "core_midcap_vwap_ma5_retrace",
  "sector_mainline_first_divergence_low_buy",
];

export function useResearchData({
  withLoading,
  setError,
}: {
  withLoading: WorkspaceLoader;
  setError: (message: string) => void;
}) {
  const [draft, setDraft] = useState<BacktestDraft>({
    symbol: "300059",
    bar_period: "5m",
    lookback_bars: "60",
    initial_position: "1000",
    walk_forward_windows: "4",
    low_buy_strategy: DEFAULT_PLAYBOOK_STRATEGY,
    low_buy_lookback_days: "60",
    low_buy_limit: "160",
  });
  const [replays, setReplays] = useState<ReplayItem[]>([]);
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [backtestRuns, setBacktestRuns] = useState<BacktestRun[]>([]);
  const [executionBacktest, setExecutionBacktest] = useState<LowBuyExecutionBacktestResult | null>(null);
  const [strategyValidation, setStrategyValidation] = useState<StrategyValidationReport | null>(null);
  const [tradeLifecycles, setTradeLifecycles] = useState<LowBuyTradeLifecycle[]>([]);
  const [researchBoard, setResearchBoard] = useState<LowBuyPriorityBoardResult | null>(null);

  const loadResearch = useCallback(async () => {
    await withLoading("research", async () => {
      const [replayResult, boardResult, lifecycleResult, runResult] = await Promise.allSettled([
        api.listReplays(),
        api.getLowBuyPriorityBoard(18),
        api.getLowBuyLifecycle(undefined, false, 40),
        api.listBacktestRuns(20),
      ]);
      if (replayResult.status === "fulfilled") {
        setReplays(replayResult.value);
      }
      if (boardResult.status === "fulfilled") {
        setResearchBoard(boardResult.value);
      }
      if (lifecycleResult.status === "fulfilled") {
        setTradeLifecycles(lifecycleResult.value.items);
      }
      if (runResult.status === "fulfilled") {
        setBacktestRuns(runResult.value.runs);
      }
      const rejected = [replayResult, boardResult, lifecycleResult, runResult].find(
        (item): item is PromiseRejectedResult => item.status === "rejected"
      );
      if (rejected) {
        setError(errorMessage(rejected.reason));
      }
    });
  }, [setError, withLoading]);

  const runBacktest = useCallback(async () => {
    await withLoading("backtest", async () => {
      const [symbolResult, executionResult] = await Promise.allSettled([
        api.runBacktest({
          symbol: draft.symbol.trim(),
          lookback_bars: lookbackDaysToBars(parseNumber(draft.lookback_bars), draft.bar_period),
          bar_period: draft.bar_period,
          initial_position: parseNumber(draft.initial_position),
          walk_forward_windows: parseNumber(draft.walk_forward_windows),
        }),
        api.getLowBuyExecutionBacktest(
          draft.low_buy_strategy,
          parseNumber(draft.low_buy_lookback_days),
          parseNumber(draft.low_buy_limit)
        ),
      ]);
      if (symbolResult.status === "fulfilled") {
        setBacktestResult(symbolResult.value);
      }
      if (executionResult.status === "fulfilled") {
        setExecutionBacktest(executionResult.value);
      }
      const rejected = [symbolResult, executionResult].find(
        (item): item is PromiseRejectedResult => item.status === "rejected"
      );
      if (rejected) {
        throw rejected.reason;
      }
    });
  }, [draft, withLoading]);

  const runStrategyValidation = useCallback(async () => {
    await withLoading("strategy-validation", async () => {
      const result = await api.runStrategyValidation({
        strategies: VALIDATION_STRATEGIES,
        lookback_days: parseNumber(draft.low_buy_lookback_days),
        max_signals_per_day: 8,
      });
      setStrategyValidation(result);
    });
  }, [draft.low_buy_lookback_days, withLoading]);

  return {
    draft,
    setDraft,
    replays,
    backtestResult,
    backtestRuns,
    executionBacktest,
    strategyValidation,
    tradeLifecycles,
    researchBoard,
    loadResearch,
    runBacktest,
    runStrategyValidation,
  };
}

function lookbackDaysToBars(days: number, period: BacktestDraft["bar_period"]): number {
  const barsPerDay = period === "1m" ? 240 : period === "5m" ? 48 : 16;
  return Math.max(1, Math.round(days * barsPerDay));
}
