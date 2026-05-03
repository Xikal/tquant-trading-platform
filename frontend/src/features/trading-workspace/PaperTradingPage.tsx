import type {
  PaperAccount,
  PaperAgentRun,
  PaperAutoTradingStatus,
  PaperGroupedPerformance,
  PaperOrder,
  PaperOrderStatus,
  PaperPerformance,
  PaperPosition,
  PaperTagPerformance,
  PaperTrade,
  PaperTradeTag,
  IntradayConfirmationItem,
  RiskEventItem,
} from "../../types";
import { memo, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { PixelTraderWorker } from "./PixelTraderWorker";
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
  tagPerformance: PaperTagPerformance[];
  tradeTags: Record<number, PaperTradeTag[]>;
  riskEvents: RiskEventItem[];
  autoTradingStatus: PaperAutoTradingStatus | null;
  autoTradingRuns: PaperAgentRun[];
  intradayConfirmations: IntradayConfirmationItem[];
  draft: PaperOrderDraft;
  setDraft: (draft: PaperOrderDraft) => void;
  loading: string;
  onSubmitOrder: () => void | Promise<void>;
  onAddTradeTag: (tradeId: number, tag: string) => void;
  onDeleteTradeTag: (tradeId: number, tagId: number) => void;
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
  tagPerformance,
  tradeTags,
  riskEvents,
  autoTradingStatus,
  autoTradingRuns,
  intradayConfirmations,
  draft,
  setDraft,
  loading,
  onSubmitOrder,
  onAddTradeTag,
  onDeleteTradeTag,
}: PaperTradingPageProps) {
  const paused = account?.status === "paused";
  const paperLoading = loading === "paper";
  const orderLoading = loading === "paper-order";
  const autoTradingRunning = Boolean(autoTradingStatus?.running);
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [lastOrderAction, setLastOrderAction] = useState<{ type: "buy" | "sell"; symbol: string; timestamp: number } | null>(null);
  const recentTrades = useMemo(() => trades.slice(0, 3).map((item) => ({
    type: item.side,
    symbol: item.symbol,
    name: item.strategy_key,
    time: formatDateTime(item.trade_time).slice(11, 16),
  })), [trades]);
  const marketState = resolvePaperMarketState();

  async function submitOrderFromModal() {
    const action = { type: draft.side, symbol: draft.symbol.trim(), timestamp: Date.now() };
    await Promise.resolve(onSubmitOrder());
    if (action.symbol) {
      setLastOrderAction(action);
    }
    setOrderModalOpen(false);
  }

  return (
    <section className="page-grid paper-grid">
      <MetricGrid account={account} performance={performance} loading={paperLoading} />

          <PixelTraderWorker
            marketState={marketState}
            paused={paused}
            autoTradingRunning={autoTradingRunning}
            lastOrderAction={lastOrderAction}
            loading={orderLoading}
            onOpenOrderEntry={() => setOrderModalOpen(true)}
            recentTrades={recentTrades}
          />

          {orderModalOpen ? (
            <OrderEntryModal
              draft={draft}
              setDraft={setDraft}
              paused={paused}
              autoTradingRunning={autoTradingRunning}
              loading={orderLoading}
              onClose={() => setOrderModalOpen(false)}
              onSubmitOrder={submitOrderFromModal}
            />
          ) : null}

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
                  )) : <Empty text="暂无成交" />}
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

            <section className="panel paper-agent-runs">
              <div className="panel-title">
                <h2>自动交易日志</h2>
                <span className="hint">最近 20 次</span>
              </div>
              <DataBody loading={paperLoading} columns={4}>
                <AgentRunList items={autoTradingRuns} />
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
    { label: "净胜率", value: formatPct(performance?.net_win_rate_pct), tone: accountTone(performance?.net_win_rate_pct) },
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

function OrderEntryModal({
  draft,
  setDraft,
  paused,
  autoTradingRunning,
  loading,
  onClose,
  onSubmitOrder,
}: {
  draft: PaperOrderDraft;
  setDraft: (draft: PaperOrderDraft) => void;
  paused: boolean;
  autoTradingRunning: boolean;
  loading: boolean;
  onClose: () => void;
  onSubmitOrder: () => void | Promise<void>;
}) {
  const locked = autoTradingRunning || paused;
  const feeWarning = estimateCommissionWarning(draft);
  return (
    <div className="order-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className={`order-modal${paused ? " paused" : ""}${autoTradingRunning ? " auto-running" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="paper-order-modal-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="order-modal-title">
          <div>
            <span>MECHA ORDER</span>
            <h2 id="paper-order-modal-title">录入模拟委托</h2>
          </div>
          <button type="button" className="order-modal-close" onClick={onClose} aria-label="关闭委托弹窗">×</button>
        </div>
        {autoTradingRunning ? <p className="muted">自动交易正在运行，手动委托已临时锁定。停止自动交易后可继续录入。</p> : null}
        {paused ? <p className="muted">模拟账户已暂停，恢复后可继续提交。</p> : null}
        <div className="form-grid order-modal-grid">
          <OrderInput label="代码" value={draft.symbol} disabled={locked} onChange={(value) => setDraft({ ...draft, symbol: value })} />
          <OrderInput label="名称" value={draft.name} disabled={locked} onChange={(value) => setDraft({ ...draft, name: value })} />
          <label>
            <span>方向</span>
            <select value={draft.side} disabled={locked} onChange={(event) => setDraft({ ...draft, side: event.target.value as "buy" | "sell" })}>
              <option value="buy">买入</option>
              <option value="sell">卖出</option>
            </select>
          </label>
          <label>
            <span>委托类型</span>
            <select value={draft.order_type} disabled={locked} onChange={(event) => setDraft({ ...draft, order_type: event.target.value as "market" | "limit" })}>
              <option value="market">市价</option>
              <option value="limit">限价</option>
            </select>
          </label>
          <OrderInput label="数量" value={draft.quantity} placeholder="100 股整数倍" inputMode="numeric" disabled={locked} onChange={(value) => setDraft({ ...draft, quantity: value })} />
          <OrderInput label="限价" value={draft.price} placeholder="限价单必填" inputMode="decimal" disabled={locked} onChange={(value) => setDraft({ ...draft, price: value })} />
          <OrderInput label="撮合现价" value={draft.current_price} inputMode="decimal" disabled={locked} onChange={(value) => setDraft({ ...draft, current_price: value })} />
          <OrderInput label="策略来源" value={draft.strategy_key} placeholder="如 first_board" disabled={locked} onChange={(value) => setDraft({ ...draft, strategy_key: value })} />
        </div>
        <label className="select-field paper-reason">
          <span>执行理由</span>
          <input value={draft.reason} disabled={locked} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} />
        </label>
        <label className="select-field paper-reason">
          <span>盘中确认</span>
          <select
            value={draft.require_intraday_confirmation ? "yes" : "no"}
            disabled={locked}
            onChange={(event) => setDraft({ ...draft, require_intraday_confirmation: event.target.value === "yes" })}
          >
            <option value="no">不强制确认</option>
            <option value="yes">买入前必须承接确认</option>
          </select>
        </label>
        {feeWarning ? <p className="warn paper-fee-warning">{feeWarning}</p> : null}
        <div className="order-modal-actions">
          <button type="button" className="ghost-button" onClick={onClose}>取消</button>
          <button type="button" className="primary-button primary" onClick={onSubmitOrder} disabled={loading || locked}>
            {autoTradingRunning ? "自动交易中" : loading ? "提交中..." : "提交模拟委托"}
          </button>
        </div>
      </section>
    </div>
  );
}

function OrderInput({
  label,
  value,
  placeholder,
  inputMode,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  placeholder?: string;
  inputMode?: "numeric" | "decimal";
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <input
        value={value}
        placeholder={placeholder}
        inputMode={inputMode}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function estimateCommissionWarning(draft: PaperOrderDraft): string {
  const quantity = Number(draft.quantity || 0);
  const price = Number(draft.price || draft.current_price || 0);
  const amount = quantity * price;
  if (!Number.isFinite(amount) || amount <= 0) return "";
  const commission = Math.max(amount * 0.00025, 5);
  const stampTax = draft.side === "sell" ? amount * 0.0005 : 0;
  const transferFee = amount * 0.00001;
  const rate = (commission + stampTax + transferFee) / amount;
  if (rate >= 0.01) return "手续费占比超过 1%，单笔金额偏小，容易吞噬收益。";
  if (rate >= 0.005) return "手续费占比超过 0.5%，建议合并小额委托。";
  return "";
}

function resolvePaperMarketState(): "open" | "closed" | "lunch_break" {
  const now = new Date();
  const day = now.getDay();
  if (day === 0 || day === 6) return "closed";
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (minutes >= 9 * 60 + 30 && minutes < 11 * 60 + 30) return "open";
  if (minutes >= 13 * 60 && minutes < 15 * 60) return "open";
  if (minutes >= 11 * 60 + 30 && minutes < 13 * 60) return "lunch_break";
  return "closed";
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

function TagPerformanceStrip({ items }: { items: PaperTagPerformance[] }) {
  if (!items.length) {
    return null;
  }
  return (
    <div className="paper-tag-performance">
      {items.slice(0, 4).map((item) => (
        <span key={item.tag}>
          {item.tag} {item.trades} 笔 · 均收 <b className={accountTone(item.avg_return_pct)}>{formatPct(item.avg_return_pct)}</b>
        </span>
      ))}
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
      <span className="cell-number">{formatShare(item.quantity)} 股</span>
      <span className="cell-number">{formatPrice(item.price)}</span>
      <span>{formatDateTime(item.trade_time)}</span>
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

function AgentRunList({ items }: { items: PaperAgentRun[] }) {
  if (!items.length) {
    return <Empty text="暂无自动交易日志" />;
  }
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
              <span>{formatDateTime(item.created_at)}</span>
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
