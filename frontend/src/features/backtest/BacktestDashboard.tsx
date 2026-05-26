import { lazy, Suspense, useEffect } from "react";
import { Alert, Button, Collapse, Grid, Space, Tabs, Typography } from "antd";
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
import {
  BACKTEST_ATTRIBUTION_ITEM_STYLE,
  BACKTEST_ATTRIBUTION_STRIP_STYLE,
  BACKTEST_ATTRIBUTION_TITLE_STYLE,
  BACKTEST_METRIC_GRID_STYLE,
  BACKTEST_RUN_LIST_STYLE,
  BACKTEST_RUN_ROW_ACTIVE_STYLE,
  BACKTEST_RUN_ROW_META_STYLE,
  BACKTEST_RUN_ROW_STYLE,
  BACKTEST_RUN_ROW_TEXT_STYLE,
  BACKTEST_RUN_ROW_TITLE_STYLE,
  BACKTEST_STATUS_BASE_STYLE,
  BACKTEST_STATUS_LABEL_STYLE,
  BACKTEST_SUMMARY_ITEM_STYLE,
  BACKTEST_SUMMARY_LINE_STYLE,
  backtestStatusToneStyle,
  combineBacktestStyles,
} from "./backtestStyles";
import {
  BACKTEST_CHART_LEGEND_BENCHMARK_STYLE,
  BACKTEST_CHART_LEGEND_ITEM_STYLE,
  BACKTEST_CHART_LEGEND_STRATEGY_STYLE,
  BACKTEST_CHART_LEGEND_STYLE,
  BACKTEST_CHART_SVG_STYLE,
  BACKTEST_CHART_WRAP_STYLE,
} from "./backtestChartStyles";
import {
  BACKTEST_CHART_EMPTY_STYLE,
  BACKTEST_ERROR_STYLE,
  BACKTEST_HEADER_ACTIONS_STYLE,
  BACKTEST_HEADER_METRICS_STYLE,
  BACKTEST_HEADER_PILL_LABEL_STYLE,
  BACKTEST_HEADER_PILL_STYLE,
  BACKTEST_HEADER_PILL_VALUE_STYLE,
  BACKTEST_HEADER_SUMMARY_STYLE,
  BACKTEST_HEADER_TITLE_STYLE,
  BACKTEST_HEADER_TITLE_WRAP_STYLE,
  BACKTEST_PANEL_SURFACE_STYLE,
  BACKTEST_SECTION_META_STYLE,
  BACKTEST_STATUS_RAIL_GRID_STYLE,
  BACKTEST_STATUS_RAIL_STYLE,
  BACKTEST_STATUS_RAIL_SUMMARY_STYLE,
  BACKTEST_TAB_BODY_STYLE,
  BACKTEST_TABS_STYLE,
  backtestOverviewTabGridStyle,
  backtestSubmitTabGridStyle,
  backtestDashboardGridStyle,
  backtestHeroStyle,
} from "./backtestPageLayoutStyles";
import { backtestToneTextStyle } from "./backtestResearchStyles";

const LazyBacktestEquityChart = lazy(() => import("./LazyBacktestEquityChart"));
const { useBreakpoint } = Grid;

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
  const screens = useBreakpoint();
  const wideLayout = Boolean(screens.xl);
  useBacktestUiStore((state) => state.verdictThresholdVersion);
  const setMode = useBacktestUiStore((state) => state.setMode);
  const bumpVerdictThresholdVersion = useBacktestUiStore((state) => state.bumpVerdictThresholdVersion);
  const runningCount = runs.filter((run) => run.status === "queued" || run.status === "running").length;
  const completedCount = runs.filter((run) => run.status === "completed" || run.status === "succeeded").length;
  const tabItems = [
    {
      key: "submit",
      label: "提交任务",
      children: (
        <div style={backtestSubmitTabGridStyle(wideLayout)}>
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
          <RunListPanel
            runs={runs}
            selectedId={selectedId}
            onSelectRun={onSelectRun}
          />
        </div>
      ),
    },
    {
      key: "overview",
      label: "结果概览",
      children: (
        <div style={backtestOverviewTabGridStyle(wideLayout)}>
          <RunDetailPanel
            loading={loading}
            selectedAttribution={selectedAttribution}
            selectedMetrics={selectedMetrics}
            selectedRun={selectedRun}
            onCancelRun={onCancelRun}
          />
          <section className="panel" style={BACKTEST_PANEL_SURFACE_STYLE}>
            <PanelHeader title="净值曲线" action={<span style={BACKTEST_SECTION_META_STYLE}>策略 vs 基准 / 可缩放交互图</span>} />
            <EquityChart points={equity} />
          </section>
        </div>
      ),
    },
    {
      key: "trades",
      label: "成交明细",
      children: <TradesPanel trades={trades} />,
    },
    {
      key: "research",
      label: "研究闭环",
      children: <BacktestResearchTabs state={research} actions={researchActions} equity={equity} />,
    },
  ];

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
    <section className="backtest-page" style={backtestDashboardGridStyle(wideLayout)}>
      <div className="panel" style={backtestHeroStyle(wideLayout)}>
        <div style={BACKTEST_HEADER_TITLE_WRAP_STYLE}>
          <Typography.Text strong style={BACKTEST_HEADER_TITLE_STYLE}>回测页</Typography.Text>
          <Typography.Text style={BACKTEST_HEADER_SUMMARY_STYLE}>
            {runs.length} 任务 / {runningCount} 运行 / {trades.length} 成交
          </Typography.Text>
        </div>
        <div style={BACKTEST_HEADER_METRICS_STYLE}>
          <HeaderPill label="任务" value={String(runs.length)} />
          <HeaderPill label="运行中" value={String(runningCount)} tone={runningCount ? "warn" : "neutral"} />
          <HeaderPill label="已完成" value={String(completedCount)} tone={completedCount ? "up" : "neutral"} />
          <HeaderPill label="成交" value={String(trades.length)} />
        </div>
        <div style={BACKTEST_HEADER_ACTIONS_STYLE}>
          <Collapse
            ghost
            size="small"
            style={BACKTEST_STATUS_RAIL_STYLE}
            items={[{
              key: "status",
              label: <span style={BACKTEST_STATUS_RAIL_SUMMARY_STYLE}>状态图例</span>,
              children: (
                <div style={BACKTEST_STATUS_RAIL_GRID_STYLE}>
                  {(Object.keys(STATUS_META) as BacktestStatus[]).map((status) => (
                    <span
                      key={status}
                      style={combineBacktestStyles(BACKTEST_STATUS_BASE_STYLE, backtestStatusToneStyle(STATUS_META[status].tone))}
                    >
                      {status}<small style={BACKTEST_STATUS_LABEL_STYLE}>{STATUS_META[status].label}</small>
                    </span>
                  ))}
                </div>
              ),
            }]}
          />
        </div>
      </div>
      <Tabs
        size="small"
        style={BACKTEST_TABS_STYLE}
        tabBarGutter={8}
        items={tabItems.map((item) => ({
          ...item,
          children: <div style={BACKTEST_TAB_BODY_STYLE}>{item.children}</div>,
        }))}
      />
    </section>
  );
}

function HeaderPill({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "up" | "warn" | "neutral" }) {
  const toneStyle = tone === "up"
    ? { borderColor: "rgba(34, 197, 94, 0.4)", background: "rgba(34, 197, 94, 0.12)" }
    : tone === "warn"
      ? { borderColor: "rgba(214, 165, 92, 0.42)", background: "rgba(214, 165, 92, 0.14)" }
      : undefined;
  return (
    <span style={{ ...BACKTEST_HEADER_PILL_STYLE, ...toneStyle }}>
      <small style={BACKTEST_HEADER_PILL_LABEL_STYLE}>{label}</small>
      <strong style={BACKTEST_HEADER_PILL_VALUE_STYLE}>{value}</strong>
    </span>
  );
}

function RunListPanel({
  runs,
  selectedId,
  onSelectRun,
}: {
  runs: BacktestRunSummary[];
  selectedId?: number;
  onSelectRun: (runId: number) => void;
}) {
  return (
    <section className="panel" style={BACKTEST_PANEL_SURFACE_STYLE}>
      <PanelHeader title="任务列表" action={<span style={BACKTEST_SECTION_META_STYLE}>{runs.length} 条</span>} />
      <div style={BACKTEST_RUN_LIST_STYLE}>
        {runs.length ? runs.map((run) => (
          <Button
            type="text"
            onClick={() => onSelectRun(run.id)}
            key={run.id}
            style={combineBacktestStyles(BACKTEST_RUN_ROW_STYLE, selectedId === run.id ? BACKTEST_RUN_ROW_ACTIVE_STYLE : undefined)}
          >
            <span
              style={combineBacktestStyles(BACKTEST_STATUS_BASE_STYLE, backtestStatusToneStyle(statusMeta(run.status).tone))}
            >
              {run.status}<small style={BACKTEST_STATUS_LABEL_STYLE}>{statusMeta(run.status).label}</small>
            </span>
            <span style={BACKTEST_RUN_ROW_TEXT_STYLE}>
              <strong style={BACKTEST_RUN_ROW_TITLE_STYLE}>{run.name || `回测 #${run.id}`}</strong>
              <span style={BACKTEST_RUN_ROW_META_STYLE}>
                <span>#{run.id}</span>
                <span>{formatBacktestStrategies(run.strategies ?? run.strategy_keys ?? []) || "--"}</span>
                <span>{dateRange(run)}</span>
              </span>
            </span>
            <ProgressCell progress={run.progress} status={run.status} waitSeconds={run.estimated_wait_seconds} />
          </Button>
        )) : <EmptyLine text="暂无回测任务，提交后会出现在这里。" />}
      </div>
    </section>
  );
}

function RunDetailPanel({
  loading,
  selectedAttribution,
  selectedMetrics,
  selectedRun,
  onCancelRun,
}: {
  loading: string;
  selectedAttribution: BacktestAttribution | null;
  selectedMetrics: ReturnType<typeof resolveMetrics>;
  selectedRun: BacktestRunDetail | null;
  onCancelRun: (runId: number) => void;
}) {
  return (
    <section className="panel" style={BACKTEST_PANEL_SURFACE_STYLE}>
      <PanelHeader
        title={selectedRun ? `详情摘要 #${selectedRun.id}` : "详情摘要"}
        action={selectedRun && isCancellableStatus(selectedRun.status) ? (
          <Button size="small" danger onClick={() => onCancelRun(selectedRun.id)} disabled={loading === "cancel"} loading={loading === "cancel"}>取消任务</Button>
        ) : null}
      />
      {selectedRun ? (
        <>
          <div style={BACKTEST_SUMMARY_LINE_STYLE}>
            <span style={BACKTEST_SUMMARY_ITEM_STYLE}>{selectedRun.name}</span>
            <span style={BACKTEST_SUMMARY_ITEM_STYLE}>{formatBacktestStrategies(selectedRun.strategies)}</span>
            <span style={BACKTEST_SUMMARY_ITEM_STYLE}>{selectedRun.execution_model || "--"} · {formatResourceTier(selectedRun.resource_tier)} · {selectedRun.benchmark || "--"}</span>
          </div>
          <ResultSummaryBanner metrics={selectedMetrics} resourceTier={selectedRun.resource_tier} />
          {selectedRun.error_message ? <div style={BACKTEST_ERROR_STYLE}>{selectedRun.error_message}</div> : null}
          <div style={BACKTEST_METRIC_GRID_STYLE}>
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
  );
}

function TradesPanel({ trades }: { trades: BacktestTrade[] }) {
  return (
    <section className="panel" style={BACKTEST_PANEL_SURFACE_STYLE}>
      <PanelHeader title="交易明细" action={<span style={BACKTEST_SECTION_META_STYLE}>{trades.length} 笔</span>} />
      <DataTable<BacktestTrade>
        rowKey={(trade) => String(trade.id)}
        dataSource={trades}
        locale={{ emptyText: <EmptyLine text="暂无成交明细。" /> }}
        scroll={{ x: 980, y: 520 }}
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
            render: (value) => <span style={backtestToneTextStyle(toneFromNumber(value))}>{formatPct(value)}</span>,
          },
          {
            title: "退出",
            dataIndex: "exit_reason",
            render: (reason) => reason || "--",
          },
        ]}
      />
    </section>
  );
}

function BacktestResearchTabs({
  actions,
  equity,
  state,
}: {
  actions: BacktestResearchActions;
  equity: EquityPoint[];
  state: BacktestResearchState;
}) {
  return (
    <Tabs
      size="small"
      tabBarGutter={8}
      items={[
        { key: "optimization", label: "参数优化", children: <BacktestResearchPanel state={state} actions={actions} sections={["optimization"]} equity={equity} /> },
        { key: "validation", label: "样本外验证", children: <BacktestResearchPanel state={state} actions={actions} sections={["validation"]} equity={equity} /> },
        { key: "compare", label: "多任务对比", children: <BacktestResearchPanel state={state} actions={actions} sections={["compare"]} equity={equity} /> },
        { key: "attribution", label: "归因复盘", children: <BacktestResearchPanel state={state} actions={actions} sections={["attribution"]} equity={equity} /> },
        { key: "capacity", label: "容量评估", children: <BacktestResearchPanel state={state} actions={actions} sections={["capacity"]} equity={equity} /> },
      ]}
    />
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
    <Alert
      style={{ margin: "10px 0" }}
      type={verdict.tone === "bad" ? "warning" : verdict.tone === "warn" ? "warning" : "success"}
      showIcon
      message={`${verdict.title}：${totalReturn === undefined ? "等待指标汇总" : `组合收益 ${formatPct(totalReturn)}`}`}
      description={
        <Space direction="vertical" size={2}>
          <Typography.Text type="secondary">{verdict.detail}</Typography.Text>
          <Typography.Text type="secondary">
            {warnings.length ? warnings.join("；") : "未触发主要异常标记，仍需结合成交明细确认。"}
          </Typography.Text>
        </Space>
      }
    />
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
    <div style={BACKTEST_ATTRIBUTION_STRIP_STYLE}>
      <strong style={BACKTEST_ATTRIBUTION_TITLE_STYLE}>分桶归因</strong>
      {buckets.map((item) => (
        <span key={`${item.group}-${item.bucket}`} style={BACKTEST_ATTRIBUTION_ITEM_STYLE}>
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
    return <div style={BACKTEST_CHART_EMPTY_STYLE}>净值曲线等待回测完成后生成。</div>;
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
    return <div style={BACKTEST_CHART_EMPTY_STYLE}>净值曲线等待回测完成后生成。</div>;
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
    <div style={BACKTEST_CHART_WRAP_STYLE}>
      <svg viewBox="0 0 640 220" role="img" aria-label="回测净值曲线" style={BACKTEST_CHART_SVG_STYLE}>
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
      <div style={BACKTEST_CHART_LEGEND_STYLE}>
        <span style={BACKTEST_CHART_LEGEND_ITEM_STYLE}><i style={BACKTEST_CHART_LEGEND_STRATEGY_STYLE} /> 策略 NAV {formatNumber(last.nav)}</span>
        <span style={BACKTEST_CHART_LEGEND_ITEM_STYLE}><i style={BACKTEST_CHART_LEGEND_BENCHMARK_STYLE} /> 基准 NAV {formatNumber(last.benchmark_nav)}</span>
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
