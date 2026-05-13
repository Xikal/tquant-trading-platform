import type {
  IntradayConfirmationItem,
  PaperAccount,
  PaperAgentRun,
  PaperAutoTradingStatus,
  PaperGroupedPerformance,
  PaperOrder,
  PaperOrderStatus,
  PaperPerformance,
  PaperPosition,
  PaperSectorEtfT0Performance,
  PaperTagPerformance,
  PaperTrade,
  PaperTradeTag,
  RiskEventItem,
} from "../../types";
import type { ReactNode } from "react";
import { OrderEntryModal } from "./PaperOrderEntryModal";
import { EmptyState, MetricGrid } from "./WorkspaceComponents";
import { formatInteger, formatMoneyPlain, formatNumber, formatPct, formatPctPlain, formatPrice, toneFromChange } from "./workspaceFormatters";
import type { MetricItem } from "./workspaceTypes";
import { AgentRunList, GroupedPerformanceTable, PerformancePills, RiskEventList, SectorEtfT0PerformancePanel, TagPerformanceStrip } from "./PaperTradingPerformance";
export { formatPaperDateTime } from "./paperTradingFormatters";
import { formatPaperDateTime } from "./paperTradingFormatters";

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
  autoTradingStatus,
  loading,
}: {
  account: PaperAccount | null;
  performance: PaperPerformance | null;
  autoTradingStatus: PaperAutoTradingStatus | null;
  loading: boolean;
}) {
  const status = resolveAutoManagedStatus(account, autoTradingStatus);
  const skipNotice = autoTradingSkipNotice(autoTradingStatus);
  const metrics = [
    { label: "总资产", value: formatMoneyPlain(account?.total_assets), tone: "neutral" as const },
    { label: "可用资金", value: formatMoneyPlain(account?.cash_available), tone: "neutral" as const },
    { label: "持仓市值", value: formatMoneyPlain(account?.market_value), tone: "neutral" as const },
    { label: "浮动盈亏", value: formatNumber(account?.unrealized_pnl), tone: toneFromChange(account?.unrealized_pnl) },
    { label: "总收益率", value: formatPct(account?.total_return_pct), tone: toneFromChange(account?.total_return_pct) },
    { label: "净胜率", value: formatPct(performance?.net_win_rate_pct), tone: toneFromChange(performance?.net_win_rate_pct) },
    { label: "状态", value: status.label, tone: status.tone },
  ] satisfies MetricItem[];

  return (
    <section className="paper-metrics-shell">
      <MetricGrid items={metrics} className="paper-metrics" loading={loading} />
      {autoTradingStatus?.sector_etf_t0_auto_enabled ? (
        <div className="context-row paper-context-row">
          <span>
            ETF T+0 自动执行：每轮最多 {autoTradingStatus.sector_etf_t0_max_orders ?? 0} 笔，
            单笔约 {formatPctPlain(autoTradingStatus.sector_etf_t0_cash_pct)} 可用资金
          </span>
          <span>
            门槛：置信度 ≥ {formatNumber(autoTradingStatus.sector_etf_t0_min_confidence)}，
            预期价差 ≥ {formatPctPlain(autoTradingStatus.sector_etf_t0_min_edge_pct)}
          </span>
        </div>
      ) : null}
      {skipNotice ? (
        <div className={`paper-auto-skip-notice ${skipNotice.tone}`}>
          <strong>{skipNotice.title}</strong>
          <span>{skipNotice.text}</span>
          {skipNotice.time ? <em>{formatPaperDateTime(skipNotice.time)}</em> : null}
        </div>
      ) : null}
    </section>
  );
}

function resolveAutoManagedStatus(
  account: PaperAccount | null,
  autoTradingStatus: PaperAutoTradingStatus | null,
): { label: string; tone: MetricItem["tone"] | "warn" } {
  if (!account) return { label: "--", tone: "neutral" };
  if (autoTradingStatus?.circuit_open) return { label: "熔断保护", tone: "warn" };
  if (autoTradingStatus?.trading_time) {
    return autoTradingStatus.running
      ? { label: "自动交易中", tone: "down" }
      : { label: "等待自动启动", tone: "warn" };
  }
  return { label: "非交易时段静默", tone: "neutral" };
}

function autoTradingSkipNotice(
  autoTradingStatus: PaperAutoTradingStatus | null,
): { title: string; text: string; time?: string; tone: "warn" | "neutral" } | null {
  if (!autoTradingStatus) return null;
  const blockingReason = String(autoTradingStatus.blocking_reason || "").trim();
  if (blockingReason) {
    return { title: "未买原因", text: blockingReason, time: autoTradingStatus.last_skip_at, tone: "warn" };
  }
  const skipReason = String(autoTradingStatus.last_skip_reason || "").trim();
  if (!skipReason) return null;
  const symbol = String(autoTradingStatus.last_skip_symbol || "").trim();
  return {
    title: "最近跳过",
    text: symbol ? `${symbol}：${skipReason}` : skipReason,
    time: autoTradingStatus.last_skip_at,
    tone: "neutral",
  };
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
        <span className="hint">{positions.length ? `共 ${positions.length} 只，全部展示` : "暂无持仓"}</span>
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
  sectorEtfT0Performance,
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
  sectorEtfT0Performance: PaperSectorEtfT0Performance | null;
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
          <span className="hint">{orders.length ? `共 ${orders.length} 条，最多显示 5 条 · 可上下滑动` : "暂无委托"}</span>
        </div>
        <DataBody loading={loading} columns={5}>
          <div className="paper-table-head paper-order-head">
            <span>标的</span>
            <span>方向/类型</span>
            <span>状态</span>
            <span>数量</span>
            <span>成交</span>
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

      <section className="panel paper-sector-etf-t0">
        <div className="panel-title">
          <h2>行业 ETF T+0</h2>
          <span className="hint">自动交易执行追踪</span>
        </div>
        <DataBody loading={loading} columns={5}>
          <SectorEtfT0PerformancePanel item={sectorEtfT0Performance} />
        </DataBody>
      </section>
    </div>
  );
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

function IntradayConfirmationStrip({ items }: { items: IntradayConfirmationItem[] }) {
  if (!items.length) return null;
  return (
    <div className="context-row paper-context-row">
      {items.slice(0, 3).map((item) => {
        const confirmed = item.confirmed || item.late_confirmed;
        return (
          <span key={item.symbol}>
            {item.symbol}：{confirmed ? "承接确认" : "等待确认"} · 分时均价 {formatPrice(item.vwap)}
          </span>
        );
      })}
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
  const sideText = item.side === "buy" ? "买入" : "卖出";
  const orderTypeText = item.order_type === "market" ? "市价" : "限价";
  return (
    <article className={`paper-row paper-order-row${item.reject_reason ? " has-note" : ""}`}>
      <div className="paper-stock-name">
        <strong>{item.symbol}</strong>
        <span>{item.name || item.strategy_key || "--"}</span>
      </div>
      <span className={`status-chip ${item.side === "buy" ? "up" : "down"}`}>{sideText} · {orderTypeText}</span>
      <span className={`status-chip ${statusTone}`}>{ORDER_STATUS_TEXT[item.status] ?? item.status}</span>
      <span className="cell-number">{formatInteger(item.quantity)} 股</span>
      <span className="cell-number">{formatPrice(item.avg_fill_price)}</span>
      {item.reject_reason ? <span className="paper-order-reason warn">原因：{item.reject_reason}</span> : null}
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
