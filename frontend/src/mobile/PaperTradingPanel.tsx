import type { ReactNode } from "react"
import mechaAvatarUrl from "../assets/mecha-trading-avatar.png"
import {
  formatInteger,
  formatMoneyPlain,
  formatNumber,
  formatPct,
  formatPrice
} from "../features/trading-workspace/workspaceFormatters"
import type {
  PaperAccount,
  PaperGroupedPerformance,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperTrade
} from "../types"

export function PaperTradingPanel({
  account,
  positions,
  orders,
  trades,
  performance,
  strategyPerformance,
  marketPerformance,
  onCreateOrder
}: {
  account: PaperAccount | null
  positions: PaperPosition[]
  orders: PaperOrder[]
  trades: PaperTrade[]
  performance: PaperPerformance | null
  strategyPerformance: PaperGroupedPerformance[]
  marketPerformance: PaperGroupedPerformance[]
  onCreateOrder: () => void
}) {
  const latestAction = orders[0] ?? null
  const metrics = [
    { label: "总资产", value: formatMoneyPlain(account?.total_assets), tone: "neutral" as const },
    { label: "可用", value: formatMoneyPlain(account?.cash_available), tone: "neutral" as const },
    { label: "持仓", value: formatMoneyPlain(account?.market_value), tone: "neutral" as const },
    { label: "收益", value: formatPct(account?.total_return_pct), tone: paperTone(account?.total_return_pct) }
  ]

  return (
    <>
      <section className="mobile-paper-metrics mobile-paper-metrics-primary">
        {metrics.map((item) => (
          <article key={item.label} className={`mobile-paper-metric tone-${item.tone}`}>
            <small>{item.label}</small>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>

      <PaperMechaCockpit latestAction={latestAction} onCreateOrder={onCreateOrder} />

      <section className="mobile-paper-card">
        <div className="mobile-paper-section-head">
          <strong>当前持仓</strong>
          <small>{positions.length} 只 · 模拟账户</small>
        </div>
        <div className="mobile-paper-scroll mobile-paper-position-scroll">
          {positions.length ? positions.map((item) => <MobilePaperPosition key={item.id} item={item} />) : <div className="mobile-app-empty">暂无模拟持仓</div>}
        </div>
      </section>

      <MobilePaperList title="委托 / 成交" hint="最近 3 笔">
        {orders.length ? orders.slice(0, 3).map((item) => <MobilePaperOrder key={item.id} item={item} />) : <div className="mobile-app-empty">暂无委托</div>}
      </MobilePaperList>

      <MobilePaperList title="绩效概览" hint="最近成交" lead={<MobilePaperPerformancePills performance={performance} />}>
        {trades.length ? trades.slice(0, 3).map((item) => <MobilePaperTrade key={item.id} item={item} />) : <div className="mobile-app-empty">暂无成交</div>}
      </MobilePaperList>

      <MobilePaperPerformanceTable title="策略绩效" items={strategyPerformance} emptyText="暂无策略绩效" />
      <MobilePaperPerformanceTable title="市场状态绩效" items={marketPerformance} emptyText="暂无市场状态绩效" />
    </>
  )
}

function PaperMechaCockpit({ latestAction, onCreateOrder }: { latestAction: PaperOrder | null; onCreateOrder: () => void }) {
  const actionSide = latestAction?.side === "sell" ? "sell" : "buy"
  const actionLabel = latestAction
    ? `${latestAction.side === "sell" ? "卖出" : "买入"} ${latestAction.symbol}`
    : "等待策略委托"

  return (
    <section className={`mobile-paper-cockpit action-${actionSide}`}>
      <div className="mobile-paper-cockpit-head">
        <strong>机甲指挥舱</strong>
        <button type="button" onClick={onCreateOrder}>+ 委托</button>
      </div>
      <div className="mobile-paper-mecha">
        <img src={mechaAvatarUrl} alt="像素交易机甲" />
        <i className="mobile-paper-scan-line" />
      </div>
      <div className="mobile-paper-cockpit-foot">
        <span>最近动作：{actionLabel}</span>
        <b>{latestAction?.status === "rejected" ? "风控拒绝" : "风控通过"}</b>
      </div>
    </section>
  )
}

function MobilePaperPosition({ item }: { item: PaperPosition }) {
  const tone = item.latest_price == null ? "neutral" : paperTone(item.unrealized_pnl_pct)
  return (
    <article className={`mobile-paper-position tone-${tone}`}>
      <div>
        <strong>{item.name || item.symbol}</strong>
        <small>{item.symbol}</small>
      </div>
      <div className="mobile-paper-position-grid">
        <span>持仓 <b>{formatInteger(item.quantity)}</b></span>
        <span>可卖 <b>{formatInteger(item.available_quantity)}</b></span>
        <span>成本 <b>{formatPrice(item.cost_basis)}</b></span>
        <span>现价 <b>{formatPrice(item.latest_price)}</b></span>
      </div>
      <strong className={`mobile-paper-pnl tone-${tone}`}>{formatPct(item.unrealized_pnl_pct)}</strong>
    </article>
  )
}

function MobilePaperList({
  title,
  hint,
  lead,
  children
}: {
  title: string
  hint: string
  lead?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="mobile-paper-card">
      <div className="mobile-paper-section-head">
        <strong>{title}</strong>
        <small>{hint}</small>
      </div>
      {lead}
      <div className="mobile-paper-scroll mobile-paper-three-scroll">{children}</div>
    </section>
  )
}

function MobilePaperOrder({ item }: { item: PaperOrder }) {
  return (
    <article className="mobile-paper-line mobile-paper-order-line">
      <strong>{item.symbol}</strong>
      <span className={`tone-${item.side === "buy" ? "positive" : "negative"}`}>{item.side === "buy" ? "买入" : "卖出"}</span>
      <span>{paperOrderStatusText(item.status)}</span>
      <b>{formatInteger(item.quantity)} 股</b>
      <b>{formatPrice(item.avg_fill_price)}</b>
    </article>
  )
}

function MobilePaperTrade({ item }: { item: PaperTrade }) {
  return (
    <article className="mobile-paper-line mobile-paper-trade-line">
      <strong>{item.symbol}</strong>
      <span className={`tone-${item.side === "buy" ? "positive" : "negative"}`}>{item.side === "buy" ? "买入" : "卖出"}</span>
      <b>{formatInteger(item.quantity)} 股</b>
      <b>{formatPrice(item.price)}</b>
      <span>{formatMobileDateTime(item.trade_time)}</span>
    </article>
  )
}

function MobilePaperPerformancePills({ performance }: { performance: PaperPerformance | null }) {
  return (
    <div className="mobile-paper-pills">
      <span>成交 <b>{performance?.total_trades ?? 0}</b></span>
      <span>胜率 <b>{formatPct(performance?.win_rate_pct)}</b></span>
      <span>均收 <b className={`tone-${paperTone(performance?.avg_trade_return_pct)}`}>{formatPct(performance?.avg_trade_return_pct)}</b></span>
      <span>回撤 <b className={`tone-${paperTone(performance?.max_drawdown_pct)}`}>{formatPct(performance?.max_drawdown_pct)}</b></span>
    </div>
  )
}

function MobilePaperPerformanceTable({
  title,
  items,
  emptyText
}: {
  title: string
  items: PaperGroupedPerformance[]
  emptyText: string
}) {
  return (
    <section className="mobile-paper-card">
      <div className="mobile-paper-section-head">
        <strong>{title}</strong>
        <small>最多显示 3 条</small>
      </div>
      <div className="mobile-paper-performance-head">
        <span>分组</span>
        <span>成交</span>
        <span>胜率</span>
        <span>均收</span>
        <span>PF</span>
      </div>
      <div className="mobile-paper-scroll mobile-paper-three-scroll">
        {items.length ? items.slice(0, 3).map((item) => (
          <article className="mobile-paper-performance-row" key={item.key || "未标注"}>
            <strong>{item.key || "未标注"}</strong>
            <span>{formatInteger(item.trades)}</span>
            <span>{formatPct(item.win_rate_pct)}</span>
            <span className={`tone-${paperTone(item.avg_return_pct)}`}>{formatPct(item.avg_return_pct)}</span>
            <span>{formatNumber(item.profit_factor)}</span>
          </article>
        )) : <div className="mobile-app-empty">{emptyText}</div>}
      </div>
    </section>
  )
}

function paperTone(value?: number | null): "positive" | "negative" | "neutral" | "warning" {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral"
  if (value > 0) return "positive"
  if (value < 0) return "negative"
  return "neutral"
}

function paperOrderStatusText(status: PaperOrder["status"]) {
  const map: Record<PaperOrder["status"], string> = {
    pending: "待成交",
    filled: "已成交",
    partial: "部分",
    rejected: "拒绝",
    cancelled: "撤销"
  }
  return map[status] ?? status
}

function formatMobileDateTime(value?: string | null) {
  if (!value) return "--"
  const match = value.replace("T", " ").match(/\d{2}:\d{2}:\d{2}/)
  return match?.[0] ?? value.slice(0, 16).replace("T", " ")
}
