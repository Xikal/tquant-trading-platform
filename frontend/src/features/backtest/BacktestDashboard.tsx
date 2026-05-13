import { lazy, Suspense, type ReactNode } from "react";
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
import {
  BACKTEST_EXECUTION_MODELS,
  formatBacktestStrategies,
  formatBacktestStrategy,
  formatDateTime,
  formatInteger,
  formatMoney,
  formatNumber,
  formatPct,
  formatPrice,
  formatResourceTier,
  percentFromRatio,
  toneFromNumber,
  BACKTEST_RESOURCE_TIER_OPTIONS,
} from "./backtestDisplay";
import { BacktestResearchPanel, type BacktestResearchActions, type BacktestResearchState } from "./BacktestResearchPanel";
import { useBacktestStrategyOptions } from "./useBacktestStrategyOptions";
import { DateField, NumberField, SelectField, TextField } from "../../components/shared/FormFields";
import { ErrorBanner } from "../../components/shared/Feedback";

const LazyBacktestEquityChart = lazy(() => import("./LazyBacktestEquityChart"));

export interface BacktestFormState {
  name: string;
  start_date: string;
  end_date: string;
  initial_capital: string;
  strategies: string[];
  execution_model: BacktestExecutionModel;
  resource_tier: BacktestResourceTier;
  max_position_pct: string;
  max_positions: string;
  max_daily_loss_pct: string;
  max_single_order_pct: string;
  min_cash_reserve: string;
  benchmark: string;
}

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

const STATUS_META: Record<BacktestStatus, { label: string; tone: string }> = {
  pending: { label: "待运行", tone: "pending" },
  queued: { label: "队列中", tone: "pending" },
  running: { label: "运行中", tone: "running" },
  completed: { label: "已完成", tone: "completed" },
  succeeded: { label: "已完成", tone: "completed" },
  failed: { label: "失败", tone: "failed" },
  cancelled: { label: "已取消", tone: "cancelled" },
  deleted: { label: "已删除", tone: "cancelled" },
  timeout: { label: "已超时", tone: "failed" },
};

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
  onToggleStrategy,
  onSubmit,
  onRefresh,
  onSelectRun,
  onCancelRun,
}: BacktestDashboardProps) {
  const strategyOptions = useBacktestStrategyOptions();
  const selectedId = selectedRun?.id ?? runs[0]?.id;
  const selectedMetrics = selectedRun ? resolveMetrics(selectedRun) : null;
  const selectedAttribution = selectedRun ? resolveAttribution(selectedRun) : null;
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

      <aside className="panel backtest-submit">
        <PanelHeader title="提交回测任务" action={<button type="button" onClick={onRefresh} disabled={loading === "list"}>刷新</button>} />
        {notice ? <div className="backtest-notice">{notice}</div> : null}
        {error ? <ErrorBanner message={error} /> : null}
        <div className="backtest-form">
          <TextField fieldClassName="wide" label="任务名称" value={form.name} onChange={(event) => onFormChange({ name: event.target.value })} />
          <div className="backtest-field-group wide">
            <span>日期范围</span>
            <DateField label="开始" value={form.start_date} onChange={(event) => onFormChange({ start_date: event.target.value })} />
            <DateField label="结束" value={form.end_date} onChange={(event) => onFormChange({ end_date: event.target.value })} />
          </div>
          <NumberField label="初始资金" value={form.initial_capital} onChange={(event) => onFormChange({ initial_capital: event.target.value })} />
          <TextField label="基准" value={form.benchmark} onChange={(event) => onFormChange({ benchmark: event.target.value })} />
          <SelectField
            fieldClassName="wide"
            label="执行模型"
            value={form.execution_model}
            options={BACKTEST_EXECUTION_MODELS.map(([value, label]) => ({ value, label }))}
            onChange={(event) => onFormChange({ execution_model: event.target.value as BacktestExecutionModel })}
          />
          <SelectField
            fieldClassName="wide"
            label="资源等级"
            value={form.resource_tier}
            options={BACKTEST_RESOURCE_TIER_OPTIONS.map(([value, label]) => ({ value, label }))}
            onChange={(event) => onFormChange({ resource_tier: event.target.value as BacktestResourceTier })}
          />
          <div className="backtest-strategy-picker wide">
            <span>策略多选</span>
            {strategyOptions.map(([key, label]) => (
              <label className={form.strategies.includes(key) ? "selected" : ""} key={key}>
                <input
                  type="checkbox"
                  checked={form.strategies.includes(key)}
                  onChange={() => onToggleStrategy(key)}
                />
                <strong>{label}</strong>
                <small>{key}</small>
              </label>
            ))}
          </div>
          <NumberField label="单票仓位" suffix="%" value={form.max_position_pct} onChange={(event) => onFormChange({ max_position_pct: event.target.value })} />
          <NumberField label="最大持仓数" value={form.max_positions} onChange={(event) => onFormChange({ max_positions: event.target.value })} />
          <NumberField label="日亏损暂停" suffix="%" value={form.max_daily_loss_pct} onChange={(event) => onFormChange({ max_daily_loss_pct: event.target.value })} />
          <NumberField label="单笔上限" suffix="%" value={form.max_single_order_pct} onChange={(event) => onFormChange({ max_single_order_pct: event.target.value })} />
          <NumberField fieldClassName="wide" label="最低现金保留" value={form.min_cash_reserve} onChange={(event) => onFormChange({ min_cash_reserve: event.target.value })} />
          <button type="button" className="primary backtest-submit-button wide" onClick={onSubmit} disabled={loading === "submit"}>
            {loading === "submit" ? "提交中..." : "提交任务"}
          </button>
        </div>
      </aside>

      <section className="panel backtest-runs">
        <PanelHeader title="任务列表" action={<span className="backtest-muted">{runs.length} 条</span>} />
        <div className="backtest-run-list">
          {runs.length ? runs.map((run) => (
            <button
              type="button"
              className={`backtest-run-row${selectedId === run.id ? " active" : ""}`}
              onClick={() => onSelectRun(run.id)}
              key={run.id}
            >
              <span className={`backtest-status ${statusMeta(run.status).tone}`}>
                {run.status}<small>{statusMeta(run.status).label}</small>
              </span>
              <strong>{run.name || `回测 #${run.id}`}</strong>
              <span>{dateRange(run)}</span>
              <span>{formatProgress(run.progress, run.status)}</span>
              <span>{formatResourceTier(run.resource_tier)}</span>
              <small>{formatDateTime(run.created_at)}</small>
            </button>
          )) : <EmptyLine text="暂无回测任务，提交后会出现在这里。" />}
        </div>
      </section>

      <section className="panel backtest-detail">
        <PanelHeader
          title={selectedRun ? `详情摘要 #${selectedRun.id}` : "详情摘要"}
          action={selectedRun && isCancellableStatus(selectedRun.status) ? (
            <button type="button" className="danger" onClick={() => onCancelRun(selectedRun.id)} disabled={loading === "cancel"}>取消任务</button>
          ) : null}
        />
        {selectedRun ? (
          <>
            <div className="backtest-summary-line">
              <span>{selectedRun.name}</span>
              <span>{formatBacktestStrategies(selectedRun.strategies)}</span>
              <span>{selectedRun.execution_model || "--"} · {formatResourceTier(selectedRun.resource_tier)} · {selectedRun.benchmark || "--"}</span>
            </div>
            <ResultSummaryBanner metrics={selectedMetrics} />
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
        <div className="backtest-trade-table" role="table" aria-label="回测交易明细">
          <div className="backtest-trade-row head" role="row">
            <span>日期</span>
            <span>标的</span>
            <span>方向</span>
            <span>数量</span>
            <span>成交价</span>
            <span>净额</span>
            <span>策略</span>
            <span>收益</span>
            <span>退出</span>
          </div>
          {trades.length ? trades.map((trade) => (
            <div className="backtest-trade-row" role="row" key={trade.id}>
              <span>{trade.trade_date}</span>
              <strong>{trade.symbol}</strong>
              <span className={trade.side === "buy" ? "buy" : "sell"}>{trade.side}</span>
              <span>{formatInteger(trade.quantity)}</span>
              <span>{formatPrice(trade.price)}</span>
              <span>{formatMoney(trade.net_amount)}</span>
              <span>{formatBacktestStrategy(trade.strategy_key ?? trade.strategy)}</span>
              <span className={toneFromNumber(trade.return_pct)}>{formatPct(trade.return_pct)}</span>
              <span>{trade.exit_reason || "--"}</span>
            </div>
          )) : <EmptyLine text="暂无成交明细。" />}
        </div>
      </section>

      <BacktestResearchPanel state={research} actions={researchActions} equity={equity} />
    </section>
  );
}

function resolveMetrics(run: BacktestRunDetail) {
  return run.result?.metrics ?? run.result?.summary ?? run.summary ?? null;
}

function ResultSummaryBanner({ metrics }: { metrics: unknown }) {
  if (!isRecord(metrics)) return null;
  const totalReturn = numeric(metrics.total_return_pct);
  const maxDrawdown = numeric(metrics.max_drawdown_pct);
  const sharpe = numeric(metrics.sharpe_ratio) ?? numeric(metrics.sharpe);
  const message = totalReturn === undefined
    ? "回测已完成，等待指标汇总。"
    : totalReturn >= 0
      ? `组合收益 ${formatPct(totalReturn)}，当前结果为正。`
      : `组合收益 ${formatPct(totalReturn)}，需要复核策略或风控。`;
  const warnings = [
    maxDrawdown !== undefined && maxDrawdown <= -15 ? `最大回撤 ${formatPct(maxDrawdown)} 超过警戒线` : "",
    sharpe !== undefined && sharpe < 0.5 ? `Sharpe ${formatNumber(sharpe)} 偏低` : "",
  ].filter(Boolean);
  return (
    <div className={`backtest-result-banner ${totalReturn !== undefined && totalReturn < 0 ? "warn" : "ok"}`}>
      <strong>{message}</strong>
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

function PanelHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="backtest-panel-title">
      <h2>{title}</h2>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: string }) {
  return (
    <div className={`backtest-metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <div className="backtest-empty">{text}</div>;
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

function dateRange(run: BacktestRunSummary): string {
  if (!run.start_date && !run.end_date) {
    return "--";
  }
  return `${run.start_date ?? "--"} → ${run.end_date ?? "--"}`;
}

function formatProgress(progress: number | null | undefined, status: BacktestStatus): string {
  if (status === "completed" || status === "succeeded") return "100%";
  if (typeof progress !== "number" || !Number.isFinite(progress)) {
    return status === "running" ? "运行中" : "--";
  }
  return `${Math.round(progress)}%`;
}

function statusMeta(status: BacktestStatus): { label: string; tone: string } {
  return STATUS_META[status] ?? STATUS_META.pending;
}

function isCancellableStatus(status: BacktestStatus): boolean {
  return status === "queued" || status === "pending" || status === "running";
}

function formatWaitSeconds(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return "--";
  if (value < 60) return `${Math.round(value)} 秒`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return seconds > 0 ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分`;
}
