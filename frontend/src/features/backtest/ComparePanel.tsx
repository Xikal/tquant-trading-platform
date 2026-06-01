import { lazy, Suspense, useMemo } from "react";
import { Button } from "antd";
import type { BacktestCompareItem, BacktestMonthlyReturn } from "../../api/backtests";
import {
  formatBacktestStrategy,
  formatInteger,
  formatNumber,
  formatPct,
  toneFromNumber,
} from "./backtestDisplay";
import type { BacktestResearchActions, BacktestResearchState } from "./BacktestResearchPanel";
import { Empty, parseRunIdsLoose, PanelTitle, sortCompareItems } from "./BacktestResearchShared";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { useBacktestResearchUiStore } from "../../stores/backtestResearchUiStore";
import { BACKTEST_CHART_FALLBACK_STYLE } from "./backtestChartStyles";
import {
  BACKTEST_COMPARE_ACTIONS_META_STYLE,
  BACKTEST_COMPARE_ACTIONS_STYLE,
  BACKTEST_RESEARCH_CARD_STYLE,
  BACKTEST_RUN_PICKER_BUTTON_STYLE,
  BACKTEST_RUN_PICKER_STYLE,
  backtestToneTextStyle,
} from "./backtestResearchStyles";

const LazyBacktestCompareChart = lazy(() => import("./LazyBacktestCompareChart"));
const LazyBacktestMonthlyHeatmap = lazy(() => import("./LazyBacktestMonthlyHeatmap"));

export function ComparePanel({ state, actions }: { state: BacktestResearchState; actions: BacktestResearchActions }) {
  const sortKey = useBacktestResearchUiStore((ui) => ui.compareSortKey);
  const setSortKey = useBacktestResearchUiStore((ui) => ui.setCompareSortKey);
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
    <section style={BACKTEST_RESEARCH_CARD_STYLE}>
      <PanelTitle title="回测对比" meta="复选运行 + 可排序指标 + ECharts" />
      <div style={BACKTEST_RUN_PICKER_STYLE} aria-label="已完成回测快捷选择">
        {state.completedRuns.slice(0, 8).map((run) => (
          <Button
            type={selectedRunIds.includes(run.id) ? "primary" : "default"}
            onClick={() => toggleRunId(run.id)}
            key={run.id}
            style={BACKTEST_RUN_PICKER_BUTTON_STYLE}
          >
            #{run.id} {formatBacktestStrategy(run.strategies?.[0] ?? run.strategy_keys?.[0])}
          </Button>
        ))}
      </div>
      <div style={BACKTEST_COMPARE_ACTIONS_STYLE}>
        <span style={BACKTEST_COMPARE_ACTIONS_META_STYLE}>已选 {selectedRunIds.length} 个回测</span>
        <Button onClick={actions.onRunCompare} disabled={state.loading === "compare" || selectedRunIds.length < 2}>
          {state.loading === "compare" ? "对比中..." : "运行对比"}
        </Button>
      </div>
      <VirtualGrid<BacktestCompareItem>
        className="backtest-data-table narrow"
        rowKey="run_id"
        dataSource={compareItems}
        locale={{ emptyText: <Empty text="选择至少 2 个已完成回测后运行对比。" /> }}
        columns={[
          { title: "Run", render: (_value, item) => `#${item.run_id} ${item.name ?? ""}` },
          {
            title: <Button type="text" size="small" onClick={() => setSortKey("return")}>收益</Button>,
            render: (_value, item) => <span style={backtestToneTextStyle(toneFromNumber(item.metrics?.total_return_pct))}>{formatPct(item.metrics?.total_return_pct)}</span>,
          },
          {
            title: <Button type="text" size="small" onClick={() => setSortKey("sharpe")}>Sharpe</Button>,
            render: (_value, item) => formatNumber(item.metrics?.sharpe ?? item.metrics?.sharpe_ratio),
          },
          {
            title: <Button type="text" size="small" onClick={() => setSortKey("drawdown")}>最大回撤</Button>,
            render: (_value, item) => <span style={backtestToneTextStyle("down")}>{formatPct(item.metrics?.max_drawdown_pct)}</span>,
          },
        ]}
      />
      <Suspense fallback={<div style={BACKTEST_CHART_FALLBACK_STYLE}>对比图加载中...</div>}>
        <LazyBacktestCompareChart result={state.compareResult} />
      </Suspense>
      <PanelTitle title="月度收益" meta="按月聚合" />
      <Suspense fallback={<div style={BACKTEST_CHART_FALLBACK_STYLE}>热力图加载中...</div>}>
        <LazyBacktestMonthlyHeatmap items={state.monthlyReturns?.items ?? []} />
      </Suspense>
      <VirtualGrid<BacktestMonthlyReturn>
        className="backtest-data-table narrow"
        rowKey="month"
        dataSource={state.monthlyReturns?.items ?? []}
        locale={{ emptyText: <Empty text="选择已完成回测后读取月度收益。" /> }}
        columns={[
          { title: "月份", dataIndex: "month" },
          { title: "策略", dataIndex: "return_pct", render: (value) => <span style={backtestToneTextStyle(toneFromNumber(value))}>{formatPct(value)}</span> },
          { title: "基准", dataIndex: "benchmark_return_pct", render: (value) => formatPct(value) },
          { title: "交易", dataIndex: "trade_count", align: "right", render: (value) => formatInteger(value) },
        ]}
      />
    </section>
  );
}
