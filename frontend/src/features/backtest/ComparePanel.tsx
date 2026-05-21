import { lazy, Suspense, useMemo, useState } from "react";
import { Button } from "antd";
import {
  formatBacktestStrategy,
  formatInteger,
  formatNumber,
  formatPct,
  toneFromNumber,
} from "./backtestDisplay";
import type { BacktestResearchActions, BacktestResearchState } from "./BacktestResearchPanel";
import { Empty, parseRunIdsLoose, PanelTitle, sortCompareItems } from "./BacktestResearchShared";

const LazyBacktestCompareChart = lazy(() => import("./LazyBacktestCompareChart"));
const LazyBacktestMonthlyHeatmap = lazy(() => import("./LazyBacktestMonthlyHeatmap"));

export function ComparePanel({ state, actions }: { state: BacktestResearchState; actions: BacktestResearchActions }) {
  const [sortKey, setSortKey] = useState<"return" | "sharpe" | "drawdown">("return");
  const selectedRunIds = parseRunIdsLoose(state.compareRunIds);
  const compareItems = useMemo(
    () => sortCompareItems(state.compareResult?.items ?? [], sortKey),
    [state.compareResult?.items, sortKey],
  );
  const toggleRunId = (runId: number) => {
    const next = selectedRunIds.includes(runId)
      ? selectedRunIds.filter((item) => item !== runId)
      : [...selectedRunIds, runId];
    actions.onCompareRunIdsChange(next.join(","));
  };
  return (
    <section className="backtest-research-card">
      <PanelTitle title="回测对比" meta="复选运行 + 可排序指标 + ECharts" />
      <div className="backtest-run-picker" aria-label="已完成回测快捷选择">
        {state.completedRuns.slice(0, 8).map((run) => (
          <Button
            type={selectedRunIds.includes(run.id) ? "primary" : "default"}
            onClick={() => toggleRunId(run.id)}
            key={run.id}
          >
            #{run.id} {formatBacktestStrategy(run.strategies?.[0] ?? run.strategy_keys?.[0])}
          </Button>
        ))}
      </div>
      <div className="backtest-compare-actions">
        <span>已选 {selectedRunIds.length} 个回测</span>
        <Button onClick={actions.onRunCompare} disabled={state.loading === "compare" || selectedRunIds.length < 2}>
          {state.loading === "compare" ? "对比中..." : "运行对比"}
        </Button>
      </div>
      <div className="backtest-data-table narrow" role="table" aria-label="回测对比指标">
        <div className="row head" role="row">
          <span>Run</span>
          <Button type="text" size="small" onClick={() => setSortKey("return")}>收益</Button>
          <Button type="text" size="small" onClick={() => setSortKey("sharpe")}>Sharpe</Button>
          <Button type="text" size="small" onClick={() => setSortKey("drawdown")}>MaxDD</Button>
        </div>
        {compareItems.map((item) => (
          <div className="row" role="row" key={item.run_id}>
            <span>#{item.run_id} {item.name ?? ""}</span>
            <span className={toneFromNumber(item.metrics?.total_return_pct)}>{formatPct(item.metrics?.total_return_pct)}</span>
            <span>{formatNumber(item.metrics?.sharpe ?? item.metrics?.sharpe_ratio)}</span>
            <span className="down">{formatPct(item.metrics?.max_drawdown_pct)}</span>
          </div>
        ))}
        {compareItems.length ? null : <Empty text="选择至少 2 个已完成回测后运行对比。" />}
      </div>
      <Suspense fallback={<div className="backtest-chart-fallback">对比图加载中...</div>}>
        <LazyBacktestCompareChart result={state.compareResult} />
      </Suspense>
      <PanelTitle title="月度收益" meta="按月聚合" />
      <Suspense fallback={<div className="backtest-chart-fallback">热力图加载中...</div>}>
        <LazyBacktestMonthlyHeatmap items={state.monthlyReturns?.items ?? []} />
      </Suspense>
      <div className="backtest-data-table narrow" role="table" aria-label="月度收益">
        <div className="row head" role="row">
          <span>月份</span>
          <span>策略</span>
          <span>基准</span>
          <span>交易</span>
        </div>
        {(state.monthlyReturns?.items ?? []).map((item) => (
          <div className="row" role="row" key={item.month}>
            <span>{item.month}</span>
            <span className={toneFromNumber(item.return_pct)}>{formatPct(item.return_pct)}</span>
            <span>{formatPct(item.benchmark_return_pct)}</span>
            <span>{formatInteger(item.trade_count)}</span>
          </div>
        ))}
        {state.monthlyReturns?.items?.length ? null : <Empty text="选择已完成回测后读取月度收益。" />}
      </div>
    </section>
  );
}
