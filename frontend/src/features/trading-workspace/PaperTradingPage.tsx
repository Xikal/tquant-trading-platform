import type {
  PaperAccount,
  PaperGroupedPerformance,
  PaperOrder,
  PaperOrderStatus,
  PaperPerformance,
  PaperPosition,
  PaperTrade,
  IntradayConfirmationItem,
  RiskEventItem,
} from "../../types";
import { memo } from "react";
import type { ReactNode } from "react";
import { formatAmount, formatNumber, formatPct, formatPrice } from "./workspaceFormatters";
import type { PaperOrderDraft } from "./workspaceTypes";

interface PaperTradingPageProps {
  account: PaperAccount | null;
  positions: PaperPosition[];
  orders: PaperOrder[];
  trades: PaperTrade[];
  performance: PaperPerformance | null;
  strategyPerformance: PaperGroupedPerformance[];
  marketPerformance: PaperGroupedPerformance[];
  riskEvents: RiskEventItem[];
  intradayConfirmations: IntradayConfirmationItem[];
  draft: PaperOrderDraft;
  setDraft: (draft: PaperOrderDraft) => void;
  loading: string;
  onRefresh: () => void;
  onRefreshQuotes: () => void;
  onSubmitOrder: () => void;
  onTogglePause: () => void;
}

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

export const PaperTradingPage = memo(function PaperTradingPage({
  account,
  positions,
  orders,
  trades,
  performance,
  strategyPerformance,
  marketPerformance,
  riskEvents,
  intradayConfirmations,
  draft,
  setDraft,
  loading,
  onRefresh,
  onRefreshQuotes,
  onSubmitOrder,
  onTogglePause,
}: PaperTradingPageProps) {
  const paused = account?.status === "paused";
  const paperLoading = loading === "paper";
  const orderLoading = loading === "paper-order";
  const quoteLoading = loading === "paper-quotes";
  const statusLoading = loading === "paper-status";
  const anyLoading = Boolean(loading);

  return (
    <section className="page-grid paper-grid">
      <section className="panel paper-hero">
        <div className="paper-hero-bar">
          <div className="paper-hero-copy">
            <h2>模拟交易</h2>
            <span>记录策略执行效果，不代表真实交易指令。</span>
          </div>
          <div className="actions">
            <button type="button" className="ghost-button" onClick={onRefresh} disabled={anyLoading}>
              {paperLoading ? "刷新中..." : "刷新"}
            </button>
            <button type="button" className="ghost-button" onClick={onTogglePause} disabled={anyLoading}>
              {statusLoading ? "处理中..." : paused ? "恢复模拟" : "暂停模拟"}
            </button>
            <button type="button" className="ghost-button gold" onClick={onRefreshQuotes} disabled={anyLoading}>
              {quoteLoading ? "刷新中..." : "刷新持仓价格"}
            </button>
          </div>
        </div>
      </section>

      <MetricGrid account={account} performance={performance} loading={paperLoading} />

          <OrderEntryPanel
            draft={draft}
            setDraft={setDraft}
            paused={paused}
            loading={orderLoading}
            onSubmitOrder={onSubmitOrder}
          />

          <section className="panel paper-positions">
            <div className="panel-title">
              <h2>模拟持仓</h2>
              <span className="hint">{positions.length ? `${Math.min(positions.length, 10)} / ${positions.length} 只 · 可滑动` : "暂无持仓"}</span>
            </div>
            <DataBody loading={paperLoading} columns={4}>
              <IntradayConfirmationStrip items={intradayConfirmations} />
              <div className="stock-list compact">
                {positions.length ? positions.map((item) => <PositionRow key={item.id} item={item} />) : <Empty text="暂无模拟持仓" />}
              </div>
            </DataBody>
          </section>

          <div className="paper-bottom-grid">
            <section className="panel paper-orders">
              <div className="panel-title">
                <h2>委托记录</h2>
                <span className="hint">最多显示 3 条 · 可上下滑动</span>
              </div>
              <DataBody loading={paperLoading} columns={5}>
                <div className="paper-table-head paper-order-head">
                  <span>标的</span>
                  <span>类型</span>
                  <span>状态</span>
                  <span>数量</span>
                  <span>成交</span>
                  <span>备注</span>
                </div>
                <div className="line-list">
                  {orders.length ? orders.map((item) => <OrderRow key={item.id} item={item} />) : <Empty text="暂无委托" />}
                </div>
              </DataBody>
            </section>

            <section className="panel paper-trades">
              <div className="panel-title">
                <h2>成交与绩效</h2>
                <span className="hint">最多显示 3 条 · 可上下滑动</span>
              </div>
              <DataBody loading={paperLoading} columns={4}>
                <PerformancePills performance={performance} />
                <RiskEventList items={riskEvents} />
                <div className="paper-table-head paper-trade-head">
                  <span>标的</span>
                  <span>方向</span>
                  <span>数量</span>
                  <span>价格</span>
                  <span>时间</span>
                </div>
                <div className="line-list">
                  {trades.length ? trades.map((item) => <TradeRow key={item.id} item={item} />) : <Empty text="暂无成交" />}
                </div>
              </DataBody>
            </section>

            <section className="panel paper-performance">
              <div className="panel-title">
                <h2>策略绩效</h2>
              </div>
              <DataBody loading={paperLoading} columns={6}>
                <GroupedPerformanceTable items={strategyPerformance} emptyText="暂无策略绩效" />
              </DataBody>
            </section>

            <section className="panel paper-market-performance">
              <div className="panel-title">
                <h2>市场状态绩效</h2>
              </div>
              <DataBody loading={paperLoading} columns={6}>
                <GroupedPerformanceTable items={marketPerformance} emptyText="暂无市场状态绩效" />
              </DataBody>
            </section>
          </div>
    </section>
  );
});

function MetricGrid({
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
    { label: "浮动盈亏", value: formatNumber(account?.unrealized_pnl), tone: accountTone(account?.unrealized_pnl) },
    { label: "总收益率", value: formatPct(performance?.total_return_pct), tone: accountTone(performance?.total_return_pct) },
    { label: "净胜率", value: formatPct(performance?.net_win_rate_pct), tone: "neutral" as const },
    { label: "状态", value: account ? (paused ? "已暂停" : "运行中") : "--", tone: paused ? ("warn" as const) : ("down" as const) },
  ];

  return (
    <section className="metric-grid paper-metrics">
      {metrics.map((metric) => (
        <Metric key={metric.label} {...metric} loading={loading} />
      ))}
    </section>
  );
}

function RiskEventList({ items }: { items: RiskEventItem[] }) {
  if (!items.length) {
    return null;
  }
  return (
    <div className="context-row paper-context-row">
      {items.slice(0, 2).map((item) => (
        <span key={item.id}>{item.severity === "high" ? "高风险" : "提醒"}：{item.message}</span>
      ))}
    </div>
  );
}

function IntradayConfirmationStrip({ items }: { items: IntradayConfirmationItem[] }) {
  if (!items.length) {
    return null;
  }
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

function Metric({
  label,
  value,
  tone = "neutral",
  loading,
}: {
  label: string;
  value: string;
  tone?: StatusTone;
  loading?: boolean;
}) {
  return (
    <div className={`metric ${tone}`}>
      <span>{label}</span>
      {loading ? <span className="skeleton-line strong" /> : <strong>{value}</strong>}
    </div>
  );
}

function OrderEntryPanel({
  draft,
  setDraft,
  paused,
  loading,
  onSubmitOrder,
}: {
  draft: PaperOrderDraft;
  setDraft: (draft: PaperOrderDraft) => void;
  paused: boolean;
  loading: boolean;
  onSubmitOrder: () => void;
}) {
  return (
    <section className={`panel paper-order${paused ? " paused" : ""}`}>
      <div className="panel-title">
        <h2>录入模拟委托</h2>
        {paused ? <span className="status-chip warn">已暂停</span> : null}
      </div>
      {paused ? <p className="muted">模拟账户已暂停，录入区置灰显示。恢复后可继续提交。</p> : null}
      <div className="form-grid">
        <label>
          <span>代码</span>
          <input value={draft.symbol} onChange={(event) => setDraft({ ...draft, symbol: event.target.value })} />
        </label>
        <label>
          <span>名称</span>
          <input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
        </label>
        <label>
          <span>方向</span>
          <select value={draft.side} onChange={(event) => setDraft({ ...draft, side: event.target.value as "buy" | "sell" })}>
            <option value="buy">买入</option>
            <option value="sell">卖出</option>
          </select>
        </label>
        <label>
          <span>委托类型</span>
          <select value={draft.order_type} onChange={(event) => setDraft({ ...draft, order_type: event.target.value as "market" | "limit" })}>
            <option value="market">市价</option>
            <option value="limit">限价</option>
          </select>
        </label>
        <label>
          <span>数量</span>
          <input
            value={draft.quantity}
            placeholder="100 股整数倍"
            inputMode="numeric"
            onChange={(event) => setDraft({ ...draft, quantity: event.target.value })}
          />
        </label>
        <label>
          <span>限价</span>
          <input
            value={draft.price}
            placeholder="限价单必填"
            inputMode="decimal"
            onChange={(event) => setDraft({ ...draft, price: event.target.value })}
          />
        </label>
        <label>
          <span>撮合现价</span>
          <input
            value={draft.current_price}
            inputMode="decimal"
            onChange={(event) => setDraft({ ...draft, current_price: event.target.value })}
          />
        </label>
        <label>
          <span>策略来源</span>
          <input
            value={draft.strategy_key}
            placeholder="如 first_board"
            onChange={(event) => setDraft({ ...draft, strategy_key: event.target.value })}
          />
        </label>
      </div>
      <label className="select-field paper-reason">
        <span>执行理由</span>
        <input value={draft.reason} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} />
      </label>
      <label className="select-field paper-reason">
        <span>盘中确认</span>
        <select
          value={draft.require_intraday_confirmation ? "yes" : "no"}
          onChange={(event) => setDraft({ ...draft, require_intraday_confirmation: event.target.value === "yes" })}
        >
          <option value="no">不强制确认</option>
          <option value="yes">买入前必须承接确认</option>
        </select>
      </label>
      <button type="button" className="primary-button primary full" onClick={onSubmitOrder} disabled={loading}>
        {loading ? "提交中..." : "提交模拟委托"}
      </button>
    </section>
  );
}

function PerformancePills({ performance }: { performance: PaperPerformance | null }) {
  return (
    <div className="context-row paper-context-row">
      <Info label="成交笔数" value={String(performance?.total_trades ?? 0)} />
      <Info label="胜率" value={formatPct(performance?.win_rate_pct)} />
      <Info label="平均单笔" value={formatPct(performance?.avg_trade_return_pct)} tone={accountTone(performance?.avg_trade_return_pct)} />
      <Info label="最大回撤" value={formatPct(performance?.max_drawdown_pct)} tone={accountTone(performance?.max_drawdown_pct)} />
    </div>
  );
}

function Info({ label, value, tone = "neutral" }: { label: string; value: string; tone?: Tone }) {
  return (
    <div className={`info-pill ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PositionRow({ item }: { item: PaperPosition }) {
  const tone = item.latest_price == null ? "neutral" : accountTone(item.unrealized_pnl_pct);
  return (
    <article className={`paper-row paper-position-row ${tone}`}>
      <div className="paper-stock-name">
        <strong>{item.name || item.symbol}</strong>
        <span>{item.symbol}</span>
      </div>
      <span>持仓 {formatShare(item.quantity)} / 可卖 {formatShare(item.available_quantity)}</span>
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
      <span className="cell-number">{formatShare(item.quantity)} 股</span>
      <span className="cell-number">{formatPrice(item.avg_fill_price)}</span>
      {item.reject_reason ? <span className="warn">{item.reject_reason}</span> : <span className="muted">--</span>}
    </article>
  );
}

function TradeRow({ item }: { item: PaperTrade }) {
  return (
    <article className="paper-row paper-trade-row">
      <div className="paper-stock-name">
        <strong>{item.symbol}</strong>
        <span>{item.strategy_key || "未标注"}</span>
      </div>
      <span className={`status-chip ${item.side === "buy" ? "up" : "down"}`}>{item.side === "buy" ? "买入" : "卖出"}</span>
      <span className="cell-number">{formatShare(item.quantity)} 股</span>
      <span className="cell-number">{formatPrice(item.price)}</span>
      <span>{formatDateTime(item.trade_time)}</span>
    </article>
  );
}

function GroupedPerformanceTable({ items, emptyText }: { items: PaperGroupedPerformance[]; emptyText: string }) {
  if (!items.length) {
    return <Empty text={emptyText} />;
  }
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
        const avgTone = accountTone(item.avg_return_pct);
        const pfTone = typeof item.profit_factor === "number" && item.profit_factor > 1 ? "up" : "neutral";
        return (
          <div className="paper-performance-row" key={item.key || "unlabeled"}>
            <strong>{item.key || "未标注"}</strong>
            <span>{formatShare(item.trades)}</span>
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

function DataBody({ loading, columns, children }: { loading: boolean; columns: number; children: ReactNode }) {
  if (loading) {
    return <SkeletonList columns={columns} />;
  }
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

function Empty({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}

function accountTone(value?: number | null): Tone {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral";
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "neutral";
}

function formatShare(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function formatDateTime(value?: string | null): string {
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

function formatMoneyPlain(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
