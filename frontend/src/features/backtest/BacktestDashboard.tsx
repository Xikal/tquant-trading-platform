import type { ReactNode } from "react";
import type {
  BacktestAttribution,
  BacktestExecutionModel,
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestStatus,
  BacktestTrade,
  EquityPoint,
} from "../../api/backtests";

export interface BacktestFormState {
  name: string;
  start_date: string;
  end_date: string;
  initial_capital: string;
  strategies: string[];
  execution_model: BacktestExecutionModel;
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
  onFormChange: (patch: Partial<BacktestFormState>) => void;
  onToggleStrategy: (strategy: string) => void;
  onSubmit: () => void;
  onRefresh: () => void;
  onSelectRun: (runId: number) => void;
  onCancelRun: (runId: number) => void;
}

const STRATEGY_OPTIONS = [
  ["first_board", "首板回调"],
  ["volume_shrink", "量能低吸"],
  ["late_session_strong_support", "收盘强势承接"],
  ["core_midcap_vwap_ma5_retrace", "中军回踩"],
  ["sector_mainline_first_divergence_low_buy", "主线首分歧"],
] as const;

const EXECUTION_MODELS: Array<[BacktestExecutionModel, string]> = [
  ["open_price", "开盘价成交"],
  ["next_open", "次日开盘"],
  ["close_price", "收盘价成交"],
  ["vwap", "VWAP 近似"],
];

const STATUS_META: Record<BacktestStatus, { label: string; tone: string }> = {
  pending: { label: "待运行", tone: "pending" },
  queued: { label: "队列中", tone: "pending" },
  running: { label: "运行中", tone: "running" },
  completed: { label: "已完成", tone: "completed" },
  succeeded: { label: "已完成", tone: "completed" },
  failed: { label: "失败", tone: "failed" },
  cancelled: { label: "已取消", tone: "cancelled" },
  deleted: { label: "已删除", tone: "cancelled" },
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
  onFormChange,
  onToggleStrategy,
  onSubmit,
  onRefresh,
  onSelectRun,
  onCancelRun,
}: BacktestDashboardProps) {
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
        <div className="backtest-status-rail" aria-label="任务状态图例">
          {(Object.keys(STATUS_META) as BacktestStatus[]).map((status) => (
            <span className={`backtest-status ${STATUS_META[status].tone}`} key={status}>
              {status}<small>{STATUS_META[status].label}</small>
            </span>
          ))}
        </div>
      </div>

      <aside className="panel backtest-submit">
        <PanelHeader title="提交回测任务" action={<button type="button" onClick={onRefresh} disabled={loading === "list"}>刷新</button>} />
        {notice ? <div className="backtest-notice">{notice}</div> : null}
        {error ? <div className="backtest-error">{error}</div> : null}
        <div className="backtest-form">
          <label className="backtest-field wide">
            <span>任务名称</span>
            <input value={form.name} onChange={(event) => onFormChange({ name: event.target.value })} />
          </label>
          <div className="backtest-field-group wide">
            <span>日期范围</span>
            <label>
              <small>开始</small>
              <input type="date" value={form.start_date} onChange={(event) => onFormChange({ start_date: event.target.value })} />
            </label>
            <label>
              <small>结束</small>
              <input type="date" value={form.end_date} onChange={(event) => onFormChange({ end_date: event.target.value })} />
            </label>
          </div>
          <label className="backtest-field">
            <span>初始资金</span>
            <input inputMode="decimal" value={form.initial_capital} onChange={(event) => onFormChange({ initial_capital: event.target.value })} />
          </label>
          <label className="backtest-field">
            <span>基准</span>
            <input value={form.benchmark} onChange={(event) => onFormChange({ benchmark: event.target.value })} />
          </label>
          <label className="backtest-field wide">
            <span>执行模型</span>
            <select value={form.execution_model} onChange={(event) => onFormChange({ execution_model: event.target.value as BacktestExecutionModel })}>
              {EXECUTION_MODELS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
            </select>
          </label>
          <div className="backtest-strategy-picker wide">
            <span>策略多选</span>
            {STRATEGY_OPTIONS.map(([key, label]) => (
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
          <label className="backtest-field">
            <span>单票仓位 %</span>
            <input inputMode="decimal" value={form.max_position_pct} onChange={(event) => onFormChange({ max_position_pct: event.target.value })} />
          </label>
          <label className="backtest-field">
            <span>最大持仓数</span>
            <input inputMode="numeric" value={form.max_positions} onChange={(event) => onFormChange({ max_positions: event.target.value })} />
          </label>
          <label className="backtest-field">
            <span>日亏损暂停 %</span>
            <input inputMode="decimal" value={form.max_daily_loss_pct} onChange={(event) => onFormChange({ max_daily_loss_pct: event.target.value })} />
          </label>
          <label className="backtest-field">
            <span>单笔上限 %</span>
            <input inputMode="decimal" value={form.max_single_order_pct} onChange={(event) => onFormChange({ max_single_order_pct: event.target.value })} />
          </label>
          <label className="backtest-field wide">
            <span>最低现金保留</span>
            <input inputMode="decimal" value={form.min_cash_reserve} onChange={(event) => onFormChange({ min_cash_reserve: event.target.value })} />
          </label>
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
              <span>{(selectedRun.strategies ?? []).join(" / ") || "--"}</span>
              <span>{selectedRun.execution_model || "--"} · {selectedRun.benchmark || "--"}</span>
            </div>
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
              <Metric label="风控" value={`${formatPct(percentFromRatio(selectedRun.risk_limits?.max_position_pct), 0)} / ${selectedRun.risk_limits?.max_positions ?? "--"}仓`} />
            </div>
            {selectedAttribution ? <AttributionStrip attribution={selectedAttribution} /> : null}
          </>
        ) : <EmptyLine text="选择一条任务查看摘要。" />}
      </section>

      <section className="panel backtest-equity">
        <PanelHeader title="净值曲线" action={<span className="backtest-muted">策略 vs 基准 / SVG 轻量图</span>} />
        <EquityMiniChart points={equity} />
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
              <span>{trade.strategy}</span>
              <span className={toneFromNumber(trade.return_pct)}>{formatPct(trade.return_pct)}</span>
              <span>{trade.exit_reason || "--"}</span>
            </div>
          )) : <EmptyLine text="暂无成交明细。" />}
        </div>
      </section>
    </section>
  );
}

function resolveMetrics(run: BacktestRunDetail) {
  return run.result?.metrics ?? run.result?.summary ?? run.summary ?? null;
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

function formatDateTime(value?: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatNumber(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2);
}

function formatInteger(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function formatMoney(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function formatPrice(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toFixed(3);
}

function formatPct(value?: number | null, digits = 2): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

function percentFromRatio(value?: number | null): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.abs(value) <= 1 ? value * 100 : value;
}

function toneFromNumber(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral";
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "neutral";
}
