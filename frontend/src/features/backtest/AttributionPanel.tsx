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
    <section className="backtest-research-card">
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
      <Suspense fallback={<div className="backtest-chart-fallback">收益分布加载中...</div>}>
        <LazyBacktestReturnDistribution points={equity} />
      </Suspense>
      <PanelTitle title="相关性矩阵" meta="Pearson" />
      <div
        className={correlationGridClass(correlation?.strategies?.length ?? 0)}
        role="table"
        aria-label="策略相关性矩阵"
      >
        {correlation?.strategies?.length ? (
          <>
            <div className="cell head">策略</div>
            {correlation.strategies.map((strategyName) => <div className="cell head" key={strategyName}>{strategyName}</div>)}
            {correlation.strategies.map((strategyName, rowIndex) => (
              <MatrixRow correlation={correlation} strategyName={strategyName} rowIndex={rowIndex} key={strategyName} />
            ))}
          </>
        ) : <Empty text="选择多策略回测后显示策略相关性矩阵。" />}
      </div>
    </section>
  );
}

function correlationGridClass(strategyCount: number): string {
  if (strategyCount <= 0) {
    return "backtest-correlation";
  }
  return `backtest-correlation backtest-correlation-cols-${Math.min(Math.max(strategyCount + 1, 3), 18)}`;
}

function MatrixRow({
  correlation,
  strategyName,
  rowIndex,
}: {
  correlation: BacktestStrategyCorrelationResponse;
  strategyName: string;
  rowIndex: number;
}) {
  return (
    <>
      <div className="cell head">{strategyName}</div>
      {correlation.strategies.map((target, columnIndex) => (
        <div className="cell" key={`${strategyName}-${target}`}>{formatNumber(correlation.matrix?.[rowIndex]?.[columnIndex])}</div>
      ))}
    </>
  );
}

function AttributionTable({ title, items }: { title: string; items: NonNullable<BacktestAttributionResponse["industry"]> }) {
  return (
    <div className="backtest-data-table narrow" role="table" aria-label={title}>
      <div className="row caption" role="row">{title}</div>
      <div className="row head" role="row">
        <span>分桶</span>
        <span>交易</span>
        <span>胜率</span>
        <span>收益贡献</span>
      </div>
      {items.slice(0, 6).map((item) => (
        <div className="row" role="row" key={`${title}-${item.bucket}`}>
          <span>{item.label || item.bucket}</span>
          <span>{formatInteger(item.trade_count)}</span>
          <span>{formatPct(item.win_rate_pct)}</span>
          <span className={toneFromNumber(item.net_pnl ?? item.contribution_pct ?? item.return_pct)}>{formatMoneyOrPct(item.net_pnl, item.contribution_pct ?? item.return_pct)}</span>
        </div>
      ))}
      {items.length ? null : <Empty text={`${title} 等待接口返回。`} />}
    </div>
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
    <div className="backtest-data-table decomposition" role="table" aria-label="策略拆解对比">
      <div className="row caption" role="row">策略拆解对比</div>
      <div className="row head" role="row">
        <span>类型</span>
        <span>分桶</span>
        <span>样本</span>
        <span>胜率</span>
        <span>收益贡献</span>
      </div>
      {rows.map((item) => (
        <div className="row" role="row" key={`${item.group}-${item.label}`}>
          <span>{item.group}</span>
          <span>{item.label}</span>
          <span>{formatInteger(item.tradeCount)}</span>
          <span>{formatPct(item.winRate)}</span>
          <span className={toneFromNumber(item.returnValue)}>{formatMoneyOrPct(item.netPnl, item.returnValue)}</span>
        </div>
      ))}
      {rows.length ? null : <Empty text="暂无可拆解的策略归因数据。" />}
    </div>
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
