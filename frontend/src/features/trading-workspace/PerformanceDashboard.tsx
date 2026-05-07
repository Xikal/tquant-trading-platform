import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import { NumberField } from "../../components/shared/FormFields";
import type { PaperPerformanceDashboard, PaperStrategyCorrelation, PaperStrategyMarketPerformance, PaperStrategyTrend } from "../../types";
import { EmptyState, MetricGrid } from "./WorkspaceComponents";
import { formatAmount, formatPct, shortTime, strategyLabel, toneFromChange } from "./workspaceFormatters";
import type { MetricItem } from "./workspaceTypes";

const RANGE_OPTIONS = [7, 30, 90, 180] as const;

export function PerformanceDashboard() {
  const [days, setDays] = useState<number>(30);
  const [customDays, setCustomDays] = useState("30");
  const [dashboard, setDashboard] = useState<PaperPerformanceDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async (nextDays = days) => {
    try {
      setLoading(true);
      setError("");
      setDashboard(await api.getPaperPerformanceDashboard(nextDays));
    } catch (err) {
      setError(err instanceof Error ? err.message : "绩效看板加载失败");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void loadDashboard(days);
  }, [days, loadDashboard]);

  const latestEquity = lastOf(dashboard?.equity_curve ?? []);
  const strategyRows = useMemo(
    () => [...(dashboard?.strategy_trend ?? [])].sort(compareStrategyTrend).slice(0, 8),
    [dashboard]
  );
  const matrixRows = useMemo(
    () => [...(dashboard?.strategy_market_matrix ?? [])].sort(compareStrategyMarket).slice(0, 10),
    [dashboard]
  );
  const correlation = dashboard?.strategy_correlation;
  const correlationPairs = useMemo(() => buildCorrelationPairs(correlation).slice(0, 8), [correlation]);
  const customDaysError = validateCustomDays(customDays);
  const applyCustomDays = useCallback(() => {
    const parsed = Math.round(Number(customDays));
    if (!customDaysError) {
      setDays(parsed);
    }
  }, [customDays, customDaysError]);

  return (
    <section className="page-grid performance-dashboard-grid">
      <section className="panel performance-hero">
        <div>
          <p className="eyebrow">PAPER PERFORMANCE</p>
          <h2>模拟盘绩效看板</h2>
          <span>收盘后归档战绩，按策略与市场状态追踪趋势。只用于复盘，不代表真实交易指令。</span>
        </div>
        <div className="performance-actions">
          <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
            {RANGE_OPTIONS.map((value) => (
              <option value={value} key={value}>{value}日</option>
            ))}
          </select>
          <NumberField
            label="自定义天数"
            value={customDays}
            min={1}
            max={730}
            error={customDaysError}
            onChange={(event) => setCustomDays(event.target.value)}
          />
          <button type="button" className="ghost-button" onClick={applyCustomDays} disabled={Boolean(customDaysError)}>
            应用
          </button>
          <button type="button" className="ghost-button" onClick={() => void loadDashboard()} disabled={loading}>
            {loading ? "刷新中..." : "刷新"}
          </button>
        </div>
      </section>

      <MetricStrip
        items={[
          { label: "总资产", value: formatAmount(dashboard?.account.total_assets), tone: "neutral" },
          { label: "累计收益", value: formatPct(dashboard?.account.total_return_pct), tone: toneFromChange(dashboard?.account.total_return_pct) },
          { label: "最新净值点", value: latestEquity?.date ?? "--", tone: "neutral" },
          { label: "更新时间", value: shortTime(dashboard?.updated_at) || "--", tone: "neutral" },
        ]}
      />

      {error ? <section className="panel performance-alert">{error}</section> : null}

      <section className="panel performance-chart-panel performance-equity-chart">
        <div className="panel-title">
          <h2>资产曲线</h2>
          <span className="hint">总资产与累计收益趋势</span>
        </div>
        <LineChart
          points={(dashboard?.equity_curve ?? []).map((item) => ({
            x: item.date.slice(5),
            y: item.total_assets,
            label: `${item.date} · ${formatAmount(item.total_assets)}`,
          }))}
          tone="gold"
        />
      </section>

      <section className="panel performance-chart-panel performance-winrate-chart">
        <div className="panel-title">
          <h2>胜率趋势</h2>
          <span className="hint">胜率与净胜率分开观察</span>
        </div>
        <LineChart
          points={(dashboard?.win_rate_trend ?? []).map((item) => ({
            x: item.date.slice(5),
            y: item.net_win_rate_pct,
            label: `${item.date} · 净胜率 ${formatPct(item.net_win_rate_pct)}`,
          }))}
          tone="red"
        />
      </section>

      <section className="panel performance-report">
        <div className="panel-title">
          <h2>战绩总结</h2>
          <span className="hint">{dashboard?.today_report?.report_date ?? "暂无日报"}</span>
        </div>
        {dashboard?.today_report ? (
          <div className="performance-report-body">
            <p>{dashboard.today_report.overall_summary}</p>
            <div className="performance-report-block">
              <strong>策略亮点</strong>
              {(dashboard.today_report.strategy_highlights.length ? dashboard.today_report.strategy_highlights : [{ strategy: "暂无", comment: "暂无策略级日报。", trend: "stable" }]).map((item, index) => (
                <span key={`${item.strategy}-${index}`}>{strategyLabel(item.strategy)}：{item.comment}</span>
              ))}
            </div>
            <div className="performance-report-block">
              <strong>风险提醒</strong>
              {(dashboard.today_report.risk_alerts.length ? dashboard.today_report.risk_alerts : [{ level: "info", content: "暂无额外风险提醒。" }]).map((item, index) => (
                <span key={`${item.level}-${index}`}>{item.content}</span>
              ))}
            </div>
            <div className="performance-suggestion">{dashboard.today_report.suggestion}</div>
          </div>
        ) : (
          <EmptyPerformance text="暂无每日复盘，收盘归档或手动归档后显示。" />
        )}
      </section>

      <section className="panel performance-strategy">
        <div className="panel-title">
          <h2>策略趋势</h2>
          <span className="hint">按平均收益排序</span>
        </div>
        <div className="performance-table">
          <div className="performance-table-head">
            <span>策略</span>
            <span>成交</span>
            <span>胜率</span>
            <span>净胜率</span>
            <span>均收</span>
          </div>
          {strategyRows.length ? strategyRows.map((item) => <StrategyTrendRow item={item} key={item.strategy_key} />) : <EmptyPerformance text="暂无策略绩效归档" />}
        </div>
      </section>

      <section className="panel performance-market">
        <div className="panel-title">
          <h2>市场状态热力</h2>
          <span className="hint">查看哪些环境更适合模拟执行</span>
        </div>
        <div className="market-heatmap">
          {(dashboard?.market_perf_heatmap ?? []).length ? dashboard!.market_perf_heatmap.map((item) => (
            <div className={`market-heatmap-card ${toneFromChange(item.avg_return_pct)}`} key={item.market_state}>
              <strong>{item.market_state || "未分类"}</strong>
              <span>成交 {item.trade_count}</span>
              <span>胜率 {formatPct(item.avg_win_rate_pct)}</span>
              <span>均收 {formatPct(item.avg_return_pct)}</span>
            </div>
          )) : <EmptyPerformance text="暂无市场状态归档" />}
        </div>
      </section>

      <section className="panel performance-strategy-market">
        <div className="panel-title">
          <h2>策略 × 市场状态</h2>
          <span className="hint">同一策略在不同市场环境下分开看</span>
        </div>
        <div className="performance-table performance-matrix-table">
          <div className="performance-table-head">
            <span>策略 / 环境</span>
            <span>成交</span>
            <span>胜率</span>
            <span>净胜率</span>
            <span>均收</span>
          </div>
          {matrixRows.length ? matrixRows.map((item) => <StrategyMarketRow item={item} key={`${item.strategy_key}-${item.market_state}`} />) : <EmptyPerformance text="暂无策略环境交叉归档" />}
        </div>
      </section>

      <section className="panel performance-correlation">
        <div className="panel-title">
          <h2>策略相关性</h2>
          <span className="hint">避免多个同向策略同时放大仓位</span>
        </div>
        {correlationPairs.length ? (
          <div className="performance-table performance-correlation-table">
            <div className="performance-table-head">
              <span>策略组合</span>
              <span>相关性</span>
              <span>重叠交易日</span>
              <span>风险</span>
            </div>
            {correlationPairs.map((item) => (
              <CorrelationRow item={item} key={`${item.strategy_a}-${item.strategy_b}`} />
            ))}
          </div>
        ) : (
          <EmptyPerformance text={correlation?.notes?.[0] ?? "暂无足够交易日计算策略相关性。"} />
        )}
      </section>
    </section>
  );
}

function MetricStrip({ items }: { items: MetricItem[] }) {
  return <MetricGrid items={items} className="performance-metrics" as="section" />;
}

function StrategyTrendRow({ item }: { item: PaperStrategyTrend }) {
  const latest = lastOf(item.points);
  const avgTone = toneFromChange(latest?.avg_return_pct);
  return (
    <div className="performance-table-row">
      <strong>{strategyLabel(item.strategy_key)}</strong>
      <span>{latest?.trade_count ?? "--"}</span>
      <span>{formatPct(latest?.win_rate_pct)}</span>
      <span>{formatPct(latest?.net_win_rate_pct)}</span>
      <span className={avgTone}>{formatPct(latest?.avg_return_pct)}</span>
    </div>
  );
}

function StrategyMarketRow({ item }: { item: PaperStrategyMarketPerformance }) {
  const avgTone = toneFromChange(item.avg_return_pct);
  return (
    <div className="performance-table-row">
      <strong>{strategyLabel(item.strategy_key)} / {item.market_state || "未分类"}</strong>
      <span>{item.trades}</span>
      <span>{formatPct(item.win_rate_pct)}</span>
      <span>{formatPct(item.net_win_rate_pct)}</span>
      <span className={avgTone}>{formatPct(item.avg_return_pct)}</span>
    </div>
  );
}

type CorrelationPair = {
  strategy_a: string;
  strategy_b: string;
  correlation: number;
  overlap_days: number;
  risk_level: "low" | "medium" | "high";
  risk_text: string;
};

function CorrelationRow({ item }: { item: CorrelationPair }) {
  const riskTone = item.risk_level === "high" ? "down" : item.risk_level === "medium" ? "warn" : "up";
  return (
    <div className="performance-table-row">
      <strong>{strategyLabel(item.strategy_a)} / {strategyLabel(item.strategy_b)}</strong>
      <span className={riskTone}>{formatCorrelation(item.correlation)}</span>
      <span>{item.overlap_days}</span>
      <span>{item.risk_text}</span>
    </div>
  );
}

function buildCorrelationPairs(correlation?: PaperStrategyCorrelation | null): CorrelationPair[] {
  if (!correlation?.strategies?.length || !correlation.matrix?.length) {
    return [];
  }
  const pairs: CorrelationPair[] = [];
  correlation.strategies.forEach((left, leftIndex) => {
    correlation.strategies.slice(leftIndex + 1).forEach((right, offset) => {
      const rightIndex = leftIndex + offset + 1;
      const value = correlation.matrix[leftIndex]?.[rightIndex];
      if (typeof value !== "number" || !Number.isFinite(value)) {
        return;
      }
      pairs.push({
        strategy_a: left,
        strategy_b: right,
        correlation: value,
        overlap_days: correlation.sample_days,
        risk_level: Math.abs(value) >= 0.75 ? "high" : Math.abs(value) >= 0.45 ? "medium" : "low",
        risk_text:
          Math.abs(value) >= 0.75
            ? "同向度高，避免同时加仓"
            : Math.abs(value) >= 0.45
              ? "中等相关，注意仓位叠加"
              : "相关性低，可分散观察",
      });
    });
  });
  return pairs.sort((left, right) => Math.abs(right.correlation) - Math.abs(left.correlation));
}

function LineChart({
  points,
  tone,
}: {
  points: Array<{ x: string; y: number; label: string }>;
  tone: "gold" | "red";
}) {
  if (points.length < 2) {
    return <EmptyPerformance text="归档点不足，至少需要 2 个交易日。" />;
  }
  const width = 560;
  const height = 170;
  const padding = 20;
  const yValues = points.map((item) => item.y);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);
  const span = maxY - minY || 1;
  const path = points
    .map((item, index) => {
      const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - ((item.y - minY) / span) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div className="performance-line-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="绩效趋势图">
        <path d={path} className={`line-${tone}`} fill="none" />
        {points.map((item, index) => {
          const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
          const y = height - padding - ((item.y - minY) / span) * (height - padding * 2);
          return <circle key={`${item.x}-${index}`} cx={x} cy={y} r="3.5"><title>{item.label}</title></circle>;
        })}
      </svg>
      <div className="performance-chart-axis">
        <span>{points[0]?.x}</span>
        <span>{lastOf(points)?.x}</span>
      </div>
    </div>
  );
}

function EmptyPerformance({ text }: { text: string }) {
  return <EmptyState text={text} className="performance-empty" />;
}

function validateCustomDays(value: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 1) return "至少 1 天";
  if (parsed > 730) return "最多 730 天";
  return "";
}

function compareStrategyTrend(left: PaperStrategyTrend, right: PaperStrategyTrend): number {
  const leftReturn = lastOf(left.points)?.avg_return_pct ?? 0;
  const rightReturn = lastOf(right.points)?.avg_return_pct ?? 0;
  return rightReturn - leftReturn;
}

function compareStrategyMarket(left: PaperStrategyMarketPerformance, right: PaperStrategyMarketPerformance): number {
  if (right.trades !== left.trades) {
    return right.trades - left.trades;
  }
  return right.avg_return_pct - left.avg_return_pct;
}

function formatCorrelation(value: number): string {
  if (!Number.isFinite(value)) return "--";
  return value.toFixed(2);
}

function lastOf<T>(items: T[]): T | undefined {
  return items.length ? items[items.length - 1] : undefined;
}
