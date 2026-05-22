import { lazy, Suspense, useEffect } from "react";
import { Button } from "antd";
import type {
  BacktestAttribution,
  BacktestExecutionModel,
  BacktestResourceTier,
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestStatus,
  BacktestTrade,
  EquityPoint,
} from "../../api/backtests";
import type { BacktestFormState } from "./backtestForms";
import {
  formatBacktestStrategies,
  formatBacktestStrategy,
  formatDateTime,
  formatInteger,
  formatMoney,
  formatNumber,
  formatPct,
  formatPrice,
  formatResourceTier,
  backtestVerdictThresholds,
  loadBacktestVerdictThresholds,
  percentFromRatio,
  toneFromNumber,
} from "./backtestDisplay";
import { EmptyLine, Metric, PanelHeader, ProgressCell } from "./BacktestDashboard.components";
import {
  STATUS_META,
  dateRange,
  formatWaitSeconds,
  isCancellableStatus,
  statusMeta,
} from "./BacktestDashboard.helpers";
import { BacktestResearchPanel, type BacktestResearchActions, type BacktestResearchState } from "./BacktestResearchPanel";
import { useBacktestStrategyOptions } from "./useBacktestStrategyOptions";
import { backtestVerdict } from "../../utils/uxClarity";
import { useBacktestUiStore } from "../../stores/backtestUiStore";
import { DataTable } from "../../ui/table/DataTable";
import { BacktestSubmitPanel } from "./BacktestSubmitPanel";

const LazyBacktestEquityChart = lazy(() => import("./LazyBacktestEquityChart"));

export type { BacktestFormState } from "./backtestForms";

export interface BacktestDashboardProps {
  form: BacktestFormState;
  runs: BacktestRunSummary[];
  selectedRun: BacktestRunDetail | null;
  equity: EquityPoint[];
  trades: BacktestTrade[];
  loading: string;
  error: string;
  notice: string;
  research: BacktestResearchState;
  researchActions: BacktestResearchActions;
  onFormChange: (patch: Partial<BacktestFormState>) => void;
  onToggleStrategy: (strategy: string) => void;
  onSubmit: () => void;
  onRefresh: () => void;
  onSelectRun: (runId: number) => void;
  onCancelRun: (runId: number) => void;
}

export function BacktestDashboard({
  form,
  runs,
  selectedRun,
  equity,
  trades,
  loading,
  error,
  notice,
  research,
  researchActions,
  onFormChange,
  onSubmit,
  onRefresh,
  onSelectRun,
  onCancelRun,
}: BacktestDashboardProps) {
  const strategyOptions = useBacktestStrategyOptions();
  const selectedId = selectedRun?.id ?? runs[0]?.id;
  const selectedMetrics = selectedRun ? resolveMetrics(selectedRun) : null;
  const selectedAttribution = selectedRun ? resolveAttribution(selectedRun) : null;
  const mode = useBacktestUiStore((state) => state.mode);
  useBacktestUiStore((state) => state.verdictThresholdVersion);
  const setMode = useBacktestUiStore((state) => state.setMode);
  const bumpVerdictThresholdVersion = useBacktestUiStore((state) => state.bumpVerdictThresholdVersion);

  useEffect(() => {
    let active = true;
    void loadBacktestVerdictThresholds().then(() => {
      if (active) bumpVerdictThresholdVersion();
    });
    return () => {
      active = false;
    };
  }, [bumpVerdictThresholdVersion]);

  return (
    <section className="page-grid backtest-grid">
      <div className="panel backtest-hero">
        <div>
          <span className="backtest-kicker">Backtest Loop v2 · Phase3</span>
          <h1>回测基础看板</h1>
          <p>提交异步组合回测，跟踪任务状态，并用净值曲线和成交明细检查策略闭环。</p>
        </div>
        <details className="backtest-status-rail" aria-label="任务状态图例">
          <summary>任务状态图例</summary>
          <div>
            {(Object.keys(STATUS_META) as BacktestStatus[]).map((status) => (
              <span className={`backtest-status ${STATUS_META[status].tone}`} key={status}>
                {status}<small>{STATUS_META[status].label}</small>
              </span>
            ))}
          </div>
        </details>
      </div>

      <BacktestSubmitPanel
        form={form}
        loading={loading}
        error={error}
        notice={notice}
        mode={mode}
        strategyOptions={strategyOptions}
        onModeChange={setMode}
        onFormChange={onFormChange}
        onSubmit={onSubmit}
        onRefresh={onRefresh}
      />

      <section className="panel backtest-runs">
        <PanelHeader title="任务列表" action={<span className="backtest-muted">{runs.length} 条</span>} />
        <div className="backtest-run-list">
          {runs.length ? runs.map((run) => (
            <Button
              type="text"
              className={`backtest-run-row${selectedId === run.id ? " active" : ""}`}
              onClick={() => onSelectRun(run.id)}
              key={run.id}
            >
              <span className={`backtest-status ${statusMeta(run.status).tone}`}>
                {run.status}<small>{statusMeta(run.status).label}</small>
              </span>
              <strong>{run.name || `回测 #${run.id}`}</strong>
              <span>{dateRange(run)}</span>
              <ProgressCell progress={run.progress} status={run.status} waitSeconds={run.estimated_wait_seconds} />
              <span>{formatResourceTier(run.resource_tier)}</span>
              <small>{formatDateTime(run.created_at)}</small>
            </Button>
          )) : <EmptyLine text="暂无回测任务，提交后会出现在这里。" />}
        </div>
      </section>

      <section className="panel backtest-detail">
        <PanelHeader
          title={selectedRun ? `详情摘要 #${selectedRun.id}` : "详情摘要"}
          action={selectedRun && isCancellableStatus(selectedRun.status) ? (
            <Button size="small" danger onClick={() => onCancelRun(selectedRun.id)} disabled={loading === "cancel"} loading={loading === "cancel"}>取消任务</Button>
          ) : null}
        />
        {selectedRun ? (
          <>
            <div className="backtest-summary-line">
              <span>{selectedRun.name}</span>
              <span>{formatBacktestStrategies(selectedRun.strategies)}</span>
              <span>{selectedRun.execution_model || "--"} · {formatResourceTier(selectedRun.resource_tier)} · {selectedRun.benchmark || "--"}</span>
            </div>
            <ResultSummaryBanner metrics={selectedMetrics} resourceTier={selectedRun.resource_tier} />
            {selectedRun.error_message ? <div className="backtest-error">{selectedRun.error_message}</div> : null}
            <div className="backtest-metric-grid">
              <Metric label="总收益" value={formatPct(selectedMetrics?.total_return_pct)} tone={toneFromNumber(selectedMetrics?.total_return_pct)} />
              <Metric label="基准" value={formatPct(selectedMetrics?.benchmark_return_pct)} tone={toneFromNumber(selectedMetrics?.benchmark_return_pct)} />
              <Metric label="Alpha" value={formatPct(selectedMetrics?.benchmark_alpha_pct)} tone={toneFromNumber(selectedMetrics?.benchmark_alpha_pct)} />
              <Metric label="Sharpe" value={formatNumber(selectedMetrics?.sharpe_ratio ?? selectedMetrics?.sharpe)} />
              <Metric label="Sortino" value={formatNumber(selectedMetrics?.sortino_ratio ?? selectedMetrics?.sortino)} />
              <Metric label="Calmar" value={formatNumber(selectedMetrics?.calmar_ratio ?? selectedMetrics?.calmar)} />
              <Metric label="IR" value={formatNumber(selectedMetrics?.information_ratio)} />
              <Metric label="MaxDD" value={formatPct(selectedMetrics?.max_drawdown_pct)} tone="down" />
              <Metric label="胜率" value={formatPct(selectedMetrics?.win_rate_pct)} />
              <Metric label="交易数" value={formatInteger(selectedMetrics?.total_trades ?? selectedMetrics?.trade_count)} />
              <Metric label="利润因子" value={formatNumber(selectedMetrics?.profit_factor)} />
              <Metric label="队列深度" value={formatInteger(selectedRun.queue_depth)} />
              <Metric label="等待时间" value={formatWaitSeconds(selectedRun.estimated_wait_seconds)} />
              <Metric label="风控" value={`${formatPct(percentFromRatio(selectedRun.risk_limits?.max_position_pct), 0)} / ${selectedRun.risk_limits?.max_positions ?? "--"}仓`} />
            </div>
            {selectedAttribution ? <AttributionStrip attribution={selectedAttribution} /> : null}
          </>
        ) : <EmptyLine text="选择一条任务查看摘要。" />}
      </section>

      <section className="panel backtest-equity">
        <PanelHeader title="净值曲线" action={<span className="backtest-muted">策略 vs 基准 / 可缩放交互图</span>} />
        <EquityChart points={equity} />
      </section>

      <section className="panel backtest-trades">
        <PanelHeader title="交易明细" action={<span className="backtest-muted">{trades.length} 笔</span>} />
        <DataTable<BacktestTrade>
          rowKey={(trade) => String(trade.id)}
          dataSource={trades}
          locale={{ emptyText: <EmptyLine text="暂无成交明细。" /> }}
          scroll={{ x: 980, y: 360 }}
          columns={[
            { title: "日期", dataIndex: "trade_date" },
            {
              title: "标的",
              dataIndex: "symbol",
              render: (symbol) => <strong>{symbol}</strong>,
            },
            {
              title: "方向",
              dataIndex: "side",
              render: (side) => <span className={side === "buy" ? "buy" : "sell"}>{side === "buy" ? "买入" : "卖出"}</span>,
            },
            {
              title: "数量",
              dataIndex: "quantity",
              align: "right",
              render: (quantity) => formatInteger(quantity),
            },
            {
              title: "成交价",
              dataIndex: "price",
              align: "right",
              render: (price) => formatPrice(price),
            },
            {
              title: "净额",
              dataIndex: "net_amount",
              align: "right",
              render: (amount) => formatMoney(amount),
            },
            {
              title: "策略",
              render: (_value, trade) => formatBacktestStrategy(trade.strategy_key ?? trade.strategy),
            },
            {
              title: "收益",
              dataIndex: "return_pct",
              align: "right",
              render: (value) => <span className={toneFromNumber(value)}>{formatPct(value)}</span>,
            },
            {
              title: "退出",
              dataIndex: "exit_reason",
              render: (reason) => reason || "--",
            },
          ]}
        />
      </section>

      <BacktestResearchPanel state={research} actions={researchActions} equity={equity} />
    </section>
  );
}

function resolveMetrics(run: BacktestRunDetail) {
  return run.result?.metrics ?? run.result?.summary ?? run.summary ?? null;
}

function ResultSummaryBanner({ metrics, resourceTier }: { metrics: unknown; resourceTier?: BacktestResourceTier | null }) {
  if (!isRecord(metrics)) return null;
  const totalReturn = numeric(metrics.total_return_pct);
  const maxDrawdown = numeric(metrics.max_drawdown_pct);
  const sharpe = numeric(metrics.sharpe_ratio) ?? numeric(metrics.sharpe);
  const verdict = backtestVerdict(totalReturn, sharpe, maxDrawdown, backtestVerdictThresholds(resourceTier));
  const warnings = [
    maxDrawdown !== undefined && maxDrawdown <= -15 ? `最大回撤 ${formatPct(maxDrawdown)} 超过警戒线` : "",
    sharpe !== undefined && sharpe < 0.5 ? `Sharpe ${formatNumber(sharpe)} 偏低` : "",
  ].filter(Boolean);
  return (
    <div className={`backtest-result-banner ${verdict.tone === "bad" ? "warn" : verdict.tone}`}>
      <strong>{verdict.title}：{totalReturn === undefined ? "等待指标汇总" : `组合收益 ${formatPct(totalReturn)}`}</strong>
      <em>{verdict.detail}</em>
      <span>{warnings.length ? warnings.join("；") : "未触发主要异常标记，仍需结合成交明细确认。"}</span>
    </div>
  );
}

function numeric(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function resolveAttribution(run: BacktestRunDetail): BacktestAttribution | null {
  const raw = run.attribution ?? run.result?.attribution ?? run.result?.metrics?.attribution;
  return isAttribution(raw) ? raw : null;
}

function AttributionStrip({ attribution }: { attribution: BacktestAttribution }) {
  const buckets = [
    ...(attribution.industry ?? []).slice(0, 2).map((item) => ({ ...item, group: "行业" })),
    ...(attribution.market_state ?? []).slice(0, 2).map((item) => ({ ...item, group: "市场" })),
    ...(attribution.data_quality ?? []).slice(0, 2).map((item) => ({ ...item, group: "数据" })),
  ];
  if (!buckets.length) {
    return null;
  }
  return (
    <div className="backtest-attribution-strip">
      <strong>分桶归因</strong>
      {buckets.map((item) => (
        <span key={`${item.group}-${item.bucket}`}>
          {item.group}:{item.bucket} · 信号 {formatInteger(item.signal_count)} · 交易 {formatInteger(item.trade_count)} · 胜率 {formatPct(item.win_rate_pct, 1)}
        </span>
      ))}
    </div>
  );
}

function isAttribution(value: unknown): value is BacktestAttribution {
  if (!value || typeof value !== "object") {
    return false;
  }
  const payload = value as BacktestAttribution;
  return Boolean(payload.industry?.length || payload.market_state?.length || payload.data_quality?.length);
}

function EquityChart({ points }: { points: EquityPoint[] }) {
  const finite = points.filter((point) => Number.isFinite(point.nav));
  if (finite.length < 2) {
    return <div className="backtest-chart-empty">净值曲线等待回测完成后生成。</div>;
  }
  return (
    <Suspense fallback={<EquityMiniChart points={points} />}>
      <LazyBacktestEquityChart points={points} />
    </Suspense>
  );
}

function EquityMiniChart({ points }: { points: EquityPoint[] }) {
  const finite = points.filter((point) => Number.isFinite(point.nav));
  if (finite.length < 2) {
    return <div className="backtest-chart-empty">净值曲线等待回测完成后生成。</div>;
  }

  const values = finite.flatMap((point) => [
    point.nav,
    typeof point.benchmark_nav === "number" ? point.benchmark_nav : point.nav,
  ]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const strategyPath = buildLinePath(finite.map((point) => point.nav), min, max);
  const benchmarkPath = buildLinePath(finite.map((point) => point.benchmark_nav ?? point.nav), min, max);
  const last = finite[finite.length - 1];

  return (
    <div className="backtest-chart-wrap">
      <svg viewBox="0 0 640 220" role="img" aria-label="回测净值曲线">
        <defs>
          <linearGradient id="backtestGlow" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#67e8f9" stopOpacity="0.36" />
            <stop offset="100%" stopColor="#d6a55c" stopOpacity="0.04" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="640" height="220" rx="18" fill="url(#backtestGlow)" />
        {[40, 85, 130, 175].map((y) => (
          <line x1="24" x2="616" y1={y} y2={y} stroke="rgba(148, 163, 184, 0.22)" key={y} />
        ))}
        <path d={benchmarkPath} fill="none" stroke="rgba(214, 165, 92, 0.72)" strokeDasharray="7 6" strokeWidth="3" />
        <path d={strategyPath} fill="none" stroke="#67e8f9" strokeWidth="4" strokeLinecap="round" />
      </svg>
      <div className="backtest-chart-legend">
        <span><i className="strategy" /> 策略 NAV {formatNumber(last.nav)}</span>
        <span><i className="benchmark" /> 基准 NAV {formatNumber(last.benchmark_nav)}</span>
        <span>样本 {finite[0].date} → {last.date}</span>
      </div>
    </div>
  );
}

function buildLinePath(values: Array<number | null | undefined>, min: number, max: number): string {
  const width = 592;
  const height = 156;
  const range = max - min || 1;
  return values.map((value, index) => {
    const x = 24 + (values.length === 1 ? 0 : (index / (values.length - 1)) * width);
    const y = 188 - (((value ?? min) - min) / range) * height;
    return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}
