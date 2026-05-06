import { useEffect, useState } from "react";
import { strategiesApi } from "../../api/strategies";
import { STRATEGY_OPTIONS, type StrategyOption } from "../../constants/strategies";

export type BacktestStrategyOption = StrategyOption;

export function useBacktestStrategyOptions(): BacktestStrategyOption[] {
  const [options, setOptions] = useState<BacktestStrategyOption[]>([...STRATEGY_OPTIONS]);

  useEffect(() => {
    let cancelled = false;
    void strategiesApi.getStrategyMeta()
      .then((result) => {
        if (cancelled) return;
        const next = (result.strategies ?? [])
          .slice()
          .filter((strategy) => strategy.enabled !== false && strategy.visibility !== "hidden")
          .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
          .map((strategy) => {
            const label = strategy.display_name || strategy.name || strategy.key;
            const suffix = strategy.visibility === "backtest_only" ? "（仅回测研究）" : "";
            return [strategy.key, `${label}${suffix}`] as BacktestStrategyOption;
          });
        if (next.length) {
          setOptions(next);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setOptions([...STRATEGY_OPTIONS]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return options;
}
