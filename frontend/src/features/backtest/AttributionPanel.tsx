import { lazy, Suspense } from "react";
import { Button } from "antd";
import type {
  BacktestAttributionResponse,
  BacktestStrategyCorrelationResponse,
  EquityPoint,
} from "../../api/backtests";
import {
  formatInteger,
  formatMoneyOrPct,
  formatNumber,
  formatPct,
  toneFromNumber,
} from "./backtestDisplay";
import type { BacktestResearchState } from "./BacktestResearchPanel";
import { Empty, normalizeAttributionRows, PanelTitle } from "./BacktestResearchShared";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { BACKTEST_CHART_FALLBACK_STYLE } from "./backtestChartStyles";
import { BACKTEST_RESEARCH_CARD_STYLE, backtestToneTextStyle } from "./backtestResearchStyles";

const LazyBacktestReturnDistribution = lazy(() => import("./LazyBacktestReturnDistribution"));

export function AttributionPanel({ state, equity }: { state: BacktestResearchState; equity: EquityPoint[] }) {
  const attribution = state.attribution;
  const correlation = state.correlation;
  const strategy = attribution?.strategy ?? attribution?.by_strategy ?? [];
  const canExport = Boolean(
    strategy.length ||
    attribution?.industry?.length ||
    attribution?.market_state?.length ||
    attribution?.data_quality?.length ||
    attribution?.failure_reasons?.length
  );
  return (
    <section style={BACKTEST_RESEARCH_CARD_STYLE}>
      <PanelTitle
        title="归因面板"
        meta="策略 / 行业 / 市场 / 质量"
        action={canExport ? <Button onClick={() => exportAttributionCsv(attribution)}>导出 CSV</Button> : null}
      />
      <AttributionTable title="策略归因" items={strategy} />
      <AttributionTable title="行业归因" items={attribution?.industry ?? []} />
      <AttributionTable title="市场状态归因" items={attribution?.market_state ?? []} />
      <AttributionTable title="质量分桶" items={attribution?.data_quality ?? []} />
      <AttributionTable title="失败原因" items={attribution?.failure_reasons ?? []} />
      <StrategyDecompositionTable attribution={attribution} />
      <PanelTitle title="收益分布" meta="日收益直方图 + 正态拟合" />
      <Suspense fallback={<div style={BACKTEST_CHART_FALLBACK_STYLE}>收益分布加载中...</div>}>
        <LazyBacktestReturnDistribution points={equity} />
      </Suspense>
      <PanelTitle title="相关性矩阵" meta="Pearson" />
      <CorrelationMatrixTable correlation={correlation} />
    </section>
  );
}

interface CorrelationRow {
  strategy: string;
  values: Record<string, number | undefined>;
}

function CorrelationMatrixTable({ correlation }: { correlation: BacktestStrategyCorrelationResponse | null }) {
  const strategies = correlation?.strategies ?? [];
  const rows: CorrelationRow[] = strategies.map((strategy, rowIndex) => ({
    strategy,
    values: Object.fromEntries(strategies.map((target, columnIndex) => [target, correlation?.matrix?.[rowIndex]?.[columnIndex]])),
  }));
  return (
    <VirtualGrid<CorrelationRow>
      className="backtest-correlation"
      rowKey="strategy"
      dataSource={rows}
      locale={{ emptyText: <Empty text="选择多策略回测后显示策略相关性矩阵。" /> }}
      scroll={{ x: Math.max(680, strategies.length * 96) }}
      columns={[
        { title: "策略", dataIndex: "strategy", fixed: "left" },
        ...strategies.map((strategy) => ({
          title: strategy,
          render: (_value: unknown, row: CorrelationRow) => formatNumber(row.values[strategy]),
        })),
      ]}
    />
  );
}

function AttributionTable({ title, items }: { title: string; items: NonNullable<BacktestAttributionResponse["industry"]> }) {
  return (
    <VirtualGrid<NonNullable<BacktestAttributionResponse["industry"]>[number]>
      className="backtest-data-table narrow"
      rowKey={(item) => `${title}-${item.bucket}`}
      title={() => title}
      dataSource={items}
      locale={{ emptyText: <Empty text={`${title} 等待接口返回。`} /> }}
      columns={[
        { title: "分桶", render: (_value, item) => item.label || item.bucket },
        { title: "交易", dataIndex: "trade_count", align: "right", render: (value) => formatInteger(value) },
        { title: "胜率", dataIndex: "win_rate_pct", align: "right", render: (value) => formatPct(value) },
        {
          title: "收益贡献",
          align: "right",
          render: (_value, item) => {
            const value = item.net_pnl ?? item.contribution_pct ?? item.return_pct;
            return <span style={backtestToneTextStyle(toneFromNumber(value))}>{formatMoneyOrPct(item.net_pnl, item.contribution_pct ?? item.return_pct)}</span>;
          },
        },
      ]}
    />
  );
}

function StrategyDecompositionTable({ attribution }: { attribution: BacktestAttributionResponse | null }) {
  const rows = [
    ...normalizeAttributionRows("策略", attribution?.strategy ?? attribution?.by_strategy ?? []),
    ...normalizeAttributionRows("行业", attribution?.industry ?? []),
    ...normalizeAttributionRows("市场", attribution?.market_state ?? []),
    ...normalizeAttributionRows("质量", attribution?.data_quality ?? []),
    ...normalizeAttributionRows("失败", attribution?.failure_reasons ?? []),
  ]
    .sort((a, b) => Math.abs(b.returnValue) - Math.abs(a.returnValue))
    .slice(0, 10);
  return (
    <VirtualGrid<(typeof rows)[number]>
      className="backtest-data-table decomposition"
      rowKey={(item) => `${item.group}-${item.label}`}
      title={() => "策略拆解对比"}
      dataSource={rows}
      locale={{ emptyText: <Empty text="暂无可拆解的策略归因数据。" /> }}
      columns={[
        { title: "类型", dataIndex: "group" },
        { title: "分桶", dataIndex: "label" },
        { title: "样本", dataIndex: "tradeCount", align: "right", render: (value) => formatInteger(value) },
        { title: "胜率", dataIndex: "winRate", align: "right", render: (value) => formatPct(value) },
        {
          title: "收益贡献",
          align: "right",
          render: (_value, item) => <span style={backtestToneTextStyle(toneFromNumber(item.returnValue))}>{formatMoneyOrPct(item.netPnl, item.returnValue)}</span>,
        },
      ]}
    />
  );
}

function exportAttributionCsv(attribution: BacktestAttributionResponse | null) {
  const rows = [
    ["类型", "分桶", "样本", "胜率", "收益贡献"],
    ...normalizeAttributionRows("策略", attribution?.strategy ?? attribution?.by_strategy ?? []).map(csvRow),
    ...normalizeAttributionRows("行业", attribution?.industry ?? []).map(csvRow),
    ...normalizeAttributionRows("市场", attribution?.market_state ?? []).map(csvRow),
    ...normalizeAttributionRows("质量", attribution?.data_quality ?? []).map(csvRow),
    ...normalizeAttributionRows("失败", attribution?.failure_reasons ?? []).map(csvRow),
  ];
  const csv = rows.map((row) => row.map(escapeCsvCell).join(",")).join("\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `backtest-attribution-${new Date().toISOString().slice(0, 10)}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function csvRow(item: ReturnType<typeof normalizeAttributionRows>[number]) {
  return [
    item.group,
    item.label,
    String(item.tradeCount),
    `${item.winRate}`,
    `${item.returnValue}`,
  ];
}

function escapeCsvCell(value: string) {
  return `"${String(value).replace(/"/g, '""')}"`;
}
