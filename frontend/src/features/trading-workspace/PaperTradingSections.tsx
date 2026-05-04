import type {
  IntradayConfirmationItem,
  PaperAccount,
  PaperAgentRun,
  PaperGroupedPerformance,
  PaperOrder,
  PaperOrderStatus,
  PaperPerformance,
  PaperPosition,
  PaperTagPerformance,
  PaperTrade,
  PaperTradeTag,
  RiskEventItem,
} from "../../types";
import type { ReactNode } from "react";
import { OrderEntryModal } from "./PaperOrderEntryModal";
import { EmptyState, InfoPill, MetricGrid } from "./WorkspaceComponents";
import { formatInteger, formatMoneyPlain, formatNumber, formatPct, formatPrice, toneFromChange } from "./workspaceFormatters";
import type { MetricItem } from "./workspaceTypes";

type Tone = "up" | "down" | "neutral";
type StatusTone = Tone | "warn";

const ORDER_STATUS_TEXT: Record<PaperOrderStatus, string> = {
  pending: "待成交",
  filled: "已成交",
  partial: "部分成交",
  rejected: "已拒绝",
  cancelled: "已撤销",
};

const ORDER_STATUS_TONE: Record<PaperOrderStatus, StatusTone> = {
  pending: "warn",
  filled: "down",
  partial: "warn",
  rejected: "up",
  cancelled: "neutral",
};

export function PaperMetricGrid({
  account,
  performance,
  loading,
}: {
  account: PaperAccount | null;
  performance: PaperPerformance | null;
  loading: boolean;
}) {
  const paused = account?.status === "paused";
  const metrics = [
    { label: "总资产", value: formatMoneyPlain(account?.total_assets), tone: "neutral" as const },
    { label: "可用资金", value: formatMoneyPlain(account?.cash_available), tone: "neutral" as const },
    { label: "持仓市值", value: formatMoneyPlain(account?.market_value), tone: "neutral" as const },
    { label: "浮动盈亏", value: formatNumber(account?.unrealized_pnl), tone: toneFromChange(account?.unrealized_pnl) },
    { label: "总收益率", value: formatPct(performance?.total_return_pct), tone: toneFromChange(performance?.total_return_pct) },
    { label: "净胜率", value: formatPct(performance?.net_win_rate_pct), tone: toneFromChange(performance?.net_win_rate_pct) },
    { label: "状态", value: account ? (paused ? "已暂停" : "运行中") : "--", tone: paused ? ("warn" as const) : ("down" as const) },
  ] satisfies MetricItem[];

  return <MetricGrid items={metrics} className="paper-metrics" loading={loading} as="section" />;
}

export { OrderEntryModal };

export function PaperPositionsPanel({
  positions,
  intradayConfirmations,
  loading,
}: {
  positions: PaperPosition[];
  intradayConfirmations: IntradayConfirmationItem[];
  loading: boolean;
}) {
  return (
    <section className="panel paper-positions">
      <div className="panel-title">
        <h2>模拟持仓</h2>
        <span className="hint">{positions.length ? `${Math.min(positions.length, 10)} / ${positions.length} 只 · 可滑动` : "暂无持仓"}</span>
      </div>
      <DataBody loading={loading} columns={4}>
        <IntradayConfirmationStrip items={intradayConfirmations} />
        <div className="stock-list compact">
          {positions.length ? positions.map((item) => <PositionRow key={item.id} item={item} />) : <EmptyState text="暂无模拟持仓" />}
        </div>
      </DataBody>
    </section>
  );
}

export function PaperBottomPanels({
  loading,
  orders,
  trades,
  performance,
  strategyPerformance,
  marketPerformance,
  tagPerformance,
  tradeTags,
  riskEvents,
  autoTradingRuns,
  onAddTradeTag,
  onDeleteTradeTag,
}: {
  loading: boolean;
  orders: PaperOrder[];
  trades: PaperTrade[];
  performance: PaperPerformance | null;
  strategyPerformance: PaperGroupedPerformance[];
  marketPerformance: PaperGroupedPerformance[];
  tagPerformance: PaperTagPerformance[];
  tradeTags: Record<number, PaperTradeTag[]>;
  riskEvents: RiskEventItem[];
  autoTradingRuns: PaperAgentRun[];
  onAddTradeTag: (tradeId: number, tag: string) => void;
  onDeleteTradeTag: (tradeId: number, tagId: number) => void;
}) {
  return (
    <div className="paper-bottom-grid">
      <section className="panel paper-orders">
        <div className="panel-title">
          <h2>委托记录</h2>
          <span className="hint">最多显示 3 条 · 可上下滑动</span>
        </div>
        <DataBody loading={loading} columns={5}>
          <div className="paper-table-head paper-order-head">
            <span>标的</span>
            <span>类型</span>
            <span>状态</span>
            <span>数量</span>
            <span>成交</span>
            <span>备注</span>
          </div>
          <div className="line-list">
            {orders.length ? orders.map((item) => <OrderRow key={item.id} item={item} />) : <EmptyState text="暂无委托" />}
          </div>
        </DataBody>
      </section>

      <section className="panel paper-trades">
        <div className="panel-title">
          <h2>成交与绩效</h2>
          <span className="hint">最多显示 3 条 · 可上下滑动</span>
        </div>
        <DataBody loading={loading} columns={4}>
          <PerformancePills performance={performance} />
          <TagPerformanceStrip items={tagPerformance} />
          <RiskEventList items={riskEvents} />
          <div className="paper-table-head paper-trade-head with-tags">
            <span>标的</span>
            <span>方向</span>
            <span>数量</span>
            <span>价格</span>
            <span>时间</span>
            <span>标签</span>
          </div>
          <div className="line-list">
            {trades.length ? trades.map((item) => (
              <TradeRow
                key={item.id}
                item={item}
                tags={tradeTags[item.id] ?? []}
                onAddTag={onAddTradeTag}
                onDeleteTag={onDeleteTradeTag}
              />
            )) : <EmptyState text="暂无成交" />}
          </div>
        </DataBody>
      </section>

      <section className="panel paper-performance">
        <div className="panel-title">
          <h2>策略绩效</h2>
        </div>
        <DataBody loading={loading} columns={6}>
          <GroupedPerformanceTable items={strategyPerformance} emptyText="暂无策略绩效" />
        </DataBody>
      </section>

      <section className="panel paper-market-performance">
        <div className="panel-title">
          <h2>市场状态绩效</h2>
        </div>
        <DataBody loading={loading} columns={6}>
          <GroupedPerformanceTable items={marketPerformance} emptyText="暂无市场状态绩效" />
        </DataBody>
      </section>

      <section className="panel paper-agent-runs">
        <div className="panel-title">
          <h2>自动交易日志</h2>
          <span className="hint">最近 20 次</span>
        </div>
        <DataBody loading={loading} columns={4}>
          <AgentRunList items={autoTradingRuns} />
        </DataBody>
      </section>
    </div>
  );
}

export function formatPaperDateTime(value?: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value.slice(0, 19).replace("T", " ");
  return parsed.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).replace(/\//g, "-");
}

export function resolvePaperMarketState(): "open" | "closed" | "lunch_break" {
  const now = new Date();
  const day = now.getDay();
  if (day === 0 || day === 6) return "closed";
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (minutes >= 9 * 60 + 30 && minutes < 11 * 60 + 30) return "open";
  if (minutes >= 13 * 60 && minutes < 15 * 60) return "open";
  if (minutes >= 11 * 60 + 30 && minutes < 13 * 60) return "lunch_break";
  return "closed";
}

function RiskEventList({ items }: { items: RiskEventItem[] }) {
  if (!items.length) return null;
  return (
    <div className="context-row paper-context-row">
      {items.slice(0, 2).map((item) => (
        <span key={item.id}>{item.severity === "high" ? "高风险" : "提醒"}：{item.message}</span>
      ))}
    </div>
  );
}

function IntradayConfirmationStrip({ items }: { items: IntradayConfirmationItem[] }) {
  if (!items.length) return null;
  return (
    <div className="context-row paper-context-row">
      {items.slice(0, 3).map((item) => {
        const confirmed = item.confirmed || item.late_confirmed;
        return (
          <span key={item.symbol}>
            {item.symbol}：{confirmed ? "承接确认" : "等待确认"} · VWAP {formatPrice(item.vwap)}
          </span>
        );
      })}
    </div>
  );
}

function PerformancePills({ performance }: { performance: PaperPerformance | null }) {
  return (
    <div className="context-row paper-context-row">
      <InfoPill label="成交笔数" value={String(performance?.total_trades ?? 0)} />
      <InfoPill label="胜率" value={formatPct(performance?.win_rate_pct)} />
      <InfoPill label="平均单笔" value={formatPct(performance?.avg_trade_return_pct)} tone={toneFromChange(performance?.avg_trade_return_pct)} />
      <InfoPill label="最大回撤" value={formatPct(performance?.max_drawdown_pct)} tone={toneFromChange(performance?.max_drawdown_pct)} />
    </div>
  );
}

function TagPerformanceStrip({ items }: { items: PaperTagPerformance[] }) {
  if (!items.length) return null;
  return (
    <div className="paper-tag-performance">
      {items.slice(0, 4).map((item) => (
        <span key={item.tag}>
          {item.tag} {item.trades} 笔 · 均收 <b className={toneFromChange(item.avg_return_pct)}>{formatPct(item.avg_return_pct)}</b>
        </span>
      ))}
    </div>
  );
}

function PositionRow({ item }: { item: PaperPosition }) {
  const tone = item.latest_price == null ? "neutral" : toneFromChange(item.unrealized_pnl_pct);
  return (
    <article className={`paper-row paper-position-row ${tone}`}>
      <div className="paper-stock-name">
        <strong>{item.name || item.symbol}</strong>
        <span>{item.symbol}</span>
      </div>
      <span>持仓 {formatInteger(item.quantity)} / 可卖 {formatInteger(item.available_quantity)}</span>
      <span>成本 {formatPrice(item.cost_basis)} / 现价 {formatPrice(item.latest_price)}</span>
      <strong className={tone}>{formatPct(item.unrealized_pnl_pct)}</strong>
    </article>
  );
}

function OrderRow({ item }: { item: PaperOrder }) {
  const statusTone = ORDER_STATUS_TONE[item.status] ?? "neutral";
  return (
    <article className="paper-row paper-order-row">
      <div className="paper-stock-name">
        <strong>{item.symbol}</strong>
        <span>{item.name || item.strategy_key || "--"}</span>
      </div>
      <span className="status-chip neutral">{item.order_type === "market" ? "市价" : "限价"}</span>
      <span className={`status-chip ${statusTone}`}>{ORDER_STATUS_TEXT[item.status] ?? item.status}</span>
      <span className="cell-number">{formatInteger(item.quantity)} 股</span>
      <span className="cell-number">{formatPrice(item.avg_fill_price)}</span>
      {item.reject_reason ? <span className="warn">{item.reject_reason}</span> : <span className="muted">--</span>}
    </article>
  );
}

function TradeRow({
  item,
  tags,
  onAddTag,
  onDeleteTag,
}: {
  item: PaperTrade;
  tags: PaperTradeTag[];
  onAddTag: (tradeId: number, tag: string) => void;
  onDeleteTag: (tradeId: number, tagId: number) => void;
}) {
  const quickTags = ["止盈", "止损", "做T", "计划外"].filter((tag) => !tags.some((item) => item.tag === tag));
  const reasonText = item.side === "buy" ? item.entry_reason : item.exit_reason;
  return (
    <article className="paper-row paper-trade-row with-tags">
      <div className="paper-stock-name">
        <strong>{item.symbol}</strong>
        <span>{item.strategy_key || "未标注"}</span>
        <span className="paper-trade-reason">{reasonText || (item.side === "buy" ? "买入原因未记录" : "退出原因未记录")}</span>
        {item.commission_warning ? <span className="paper-trade-reason warn">{item.commission_warning}</span> : null}
      </div>
      <span className={`status-chip ${item.side === "buy" ? "up" : "down"}`}>{item.side === "buy" ? "买入" : "卖出"}</span>
      <span className="cell-number">{formatInteger(item.quantity)} 股</span>
      <span className="cell-number">{formatPrice(item.price)}</span>
      <span>{formatPaperDateTime(item.trade_time)}</span>
      <div className="paper-trade-tags">
        {tags.map((tag) => (
          <button
            type="button"
            className="paper-tag-chip"
            key={tag.id}
            onClick={() => onDeleteTag(item.id, tag.id)}
            title="点击删除标签"
          >
            {tag.tag} ×
          </button>
        ))}
        {quickTags.slice(0, tags.length ? 1 : 2).map((tag) => (
          <button type="button" className="paper-tag-add" key={tag} onClick={() => onAddTag(item.id, tag)}>
            +{tag}
          </button>
        ))}
      </div>
    </article>
  );
}

function GroupedPerformanceTable({ items, emptyText }: { items: PaperGroupedPerformance[]; emptyText: string }) {
  if (!items.length) return <EmptyState text={emptyText} />;
  return (
    <div className="paper-performance-table">
      <div className="paper-performance-head">
        <span>分组</span>
        <span>成交</span>
        <span>胜率</span>
        <span>净胜率</span>
        <span>均收</span>
        <span>PF</span>
      </div>
      {items.map((item) => {
        const avgTone = toneFromChange(item.avg_return_pct);
        const pfTone = typeof item.profit_factor === "number" && item.profit_factor > 1 ? "up" : "neutral";
        return (
          <div className="paper-performance-row" key={item.key || "unlabeled"}>
            <strong>{item.key || "未标注"}</strong>
            <span>{formatInteger(item.trades)}</span>
            <span>{formatPct(item.win_rate_pct)}</span>
            <span>{formatPct(item.net_win_rate_pct)}</span>
            <span className={avgTone}>{formatPct(item.avg_return_pct)}</span>
            <span className={pfTone}>{formatNumber(item.profit_factor)}</span>
          </div>
        );
      })}
    </div>
  );
}

function AgentRunList({ items }: { items: PaperAgentRun[] }) {
  if (!items.length) return <EmptyState text="暂无自动交易日志" />;
  return (
    <div className="line-list">
      {items.slice(0, 5).map((item) => {
        const response = item.response || {};
        const executed = Number(response.executed_count ?? (Array.isArray(response.executed) ? response.executed.length : 0));
        const skipped = Number(response.skipped_count ?? (Array.isArray(response.skipped) ? response.skipped.length : 0));
        const summary = String(response.summary || item.error_message || "--");
        return (
          <article className="paper-row paper-agent-run-row" key={item.id}>
            <div className="paper-stock-name">
              <strong>{runStatusText(item.status)}</strong>
              <span>{formatPaperDateTime(item.created_at)}</span>
            </div>
            <span>执行 {executed} / 跳过 {skipped}</span>
            <span>{summary}</span>
          </article>
        );
      })}
    </div>
  );
}

function runStatusText(status: string): string {
  if (status === "succeeded") return "已完成";
  if (status === "failed") return "失败";
  if (status === "skipped") return "跳过";
  if (status === "running") return "运行中";
  return status || "--";
}

function DataBody({ loading, columns, children }: { loading: boolean; columns: number; children: ReactNode }) {
  if (loading) return <SkeletonList columns={columns} />;
  return <>{children}</>;
}

function SkeletonList({ columns }: { columns: number }) {
  return (
    <div className="paper-skeleton-list" aria-label="加载中">
      {Array.from({ length: 4 }).map((_, row) => (
        <div className="paper-skeleton-row" key={row}>
          {Array.from({ length: columns }).map((__, col) => (
            <span className="skeleton-line" key={col} />
          ))}
        </div>
      ))}
    </div>
  );
}
