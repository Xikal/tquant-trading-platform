import type { ReactNode } from "react"
import type {
  AppWatchlistCard,
  LowBuyCandidate,
  LowBuyPriorityBoardItem,
  LowBuyPriorityBoardResult,
  WatchlistItem
} from "../types"
import { STRATEGY_OPTIONS } from "../constants/strategies"
import { getPriceToneClass } from "../utils/priceTone"

type Tone = "positive" | "negative" | "neutral" | "warning"
export type MobileStrategyTabKey = string
export type MobileLowBuyCardItem = LowBuyPriorityBoardItem | LowBuyCandidate

export interface MobileStrategyTabOption {
  key: string
  label: string
}

const MOBILE_STRATEGY_TABS: MobileStrategyTabOption[] = STRATEGY_OPTIONS.map(([key, label]) => ({ key, label }))

export interface MobileHoldingRowData {
  record: WatchlistItem
  quote: AppWatchlistCard["quote"] | null
  signal: AppWatchlistCard["signal"] | null
  floatingPnL: number | null
  floatingPnLPct: number | null
  marketValue: number | null
  plainActionText?: string
  plainActionReason?: string
  plainExecutionText?: string
  plainInvalidCondition?: string
}

export interface MobileMetricItem {
  label: string
  value: string
  tone?: Tone
}

export function MobileMetricRow({ items }: { items: MobileMetricItem[] }) {
  return (
    <section className="mobile-design-metric-row">
      {items.map((item) => (
        <article key={item.label} className="mobile-design-metric">
          <span>{item.label}</span>
          <strong className={`tone-${item.tone ?? "neutral"}`}>{item.value}</strong>
        </article>
      ))}
    </section>
  )
}

export function MobileMarketPills({ board }: { board: LowBuyPriorityBoardResult | null }) {
  return (
    <div className="mobile-design-pill-row">
      <span className="mobile-design-pill">市场宽度 {formatRatioPercent(board?.stock_up_ratio)}</span>
      <span className="mobile-design-pill tone-positive">
        涨停/跌停 {board?.limit_up_count ?? 0}/{board?.limit_down_count ?? 0}
      </span>
      <span className="mobile-design-pill tone-warning">连板高度 {board?.board_height || "--"}</span>
    </div>
  )
}

export function MobileSectionTitle({
  title,
  hint,
  action
}: {
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="mobile-design-section-title">
      <div>
        <h3>{title}</h3>
        {hint ? <small>{hint}</small> : null}
      </div>
      {action}
    </div>
  )
}

export function MobileStrategyTabs({
  active,
  onChange,
  strategies
}: {
  active: MobileStrategyTabKey
  onChange: (key: MobileStrategyTabKey) => void
  strategies?: MobileStrategyTabOption[]
}) {
  const tabs = strategies?.length ? strategies : MOBILE_STRATEGY_TABS
  return (
    <div className="mobile-design-tabs" role="tablist" aria-label="策略分类">
      {tabs.map((item) => (
        <button
          key={item.key}
          type="button"
          role="tab"
          aria-selected={active === item.key}
          className={`mobile-design-tab ${active === item.key ? "active" : ""}`}
          onClick={() => onChange(item.key)}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}

export function MobileFocusCard({ item }: { item?: MobileLowBuyCardItem }) {
  if (!item) {
    return (
      <section className="mobile-design-focus-card">
        <span>今日主看</span>
        <strong>暂无明确前排</strong>
        <div>等待榜单刷新。</div>
      </section>
    )
  }

  return (
    <section className="mobile-design-focus-card">
      <span>今日主看</span>
      <strong>{item.name} {item.symbol}</strong>
      <div>{item.buy_signal_text || "等待"} · 买点 {formatPrice(item.entry_zone_low)}-{formatPrice(item.entry_zone_high)}</div>
    </section>
  )
}

export function MobilePriorityStockCard({
  item,
  highlight = false,
  inWatchlist,
  onOpen,
  onBought
}: {
  item: MobileLowBuyCardItem
  highlight?: boolean
  inWatchlist?: boolean
  onOpen: (symbol: string) => void
  onBought?: (item: MobileLowBuyCardItem) => void
}) {
  const tone = signalTone(item.buy_signal_state)
  const strategyTags = strategyMarkers(item)
  const score = priorityScore(item)
  return (
    <article className={`mobile-design-stock-card ${highlight ? "highlight" : ""}`}>
      <button type="button" className="mobile-design-stock-main" onClick={() => onOpen(item.symbol)}>
        <StockHead
          name={item.name}
          symbol={item.symbol}
          price={item.latest_price}
          changePct={item.change_pct}
          tags={[
            { label: actionLabel(item.buy_signal_state), tone },
            ...strategyTags.slice(0, 3).map((tag) => ({ label: tag, tone: "gold" as const }))
          ]}
        />
        <div className="mobile-design-stock-grid">
          <MetricCell label="买点" value={`${formatPrice(item.entry_zone_low)}-${formatPrice(item.entry_zone_high)}`} tone={tone} />
          <MetricCell label="止损" value={formatPrice(item.stop_loss)} tone="negative" />
          <MetricCell label="评分" value={score.toFixed(1)} tone="positive" />
          <MetricCell label="仓位" value={shortPositionHint(item.suggested_position_text)} />
        </div>
      </button>
      <div className="mobile-design-card-actions">
        <small>{lowBuyActionSummary(item)}</small>
        {onBought ? (
          <button type="button" className="mobile-design-action-button" onClick={() => onBought(item)}>
            {inWatchlist ? "已买入" : "已买入"}
          </button>
        ) : null}
      </div>
    </article>
  )
}

export function MobileMonitorStockCard({
  item,
  onRemove
}: {
  item: AppWatchlistCard
  onRemove: (symbol: string) => void | Promise<unknown>
}) {
  const tone = signalTone(item.signal.action)
  return (
    <article className="mobile-design-stock-card">
      <StockHead
        name={item.name}
        symbol={item.symbol}
        price={item.quote.last_price}
        changePct={item.quote.change_pct}
        tags={[
          { label: actionLabel(item.signal.action), tone },
          { label: "持仓", tone: "neutral" }
        ]}
      />
      <div className="mobile-design-stock-grid">
        <MetricCell label="底仓" value={String(item.base_position)} />
        <MetricCell label="可卖" value={String(item.available_position)} />
        <MetricCell label="风险" value={riskLabel(item.signal.risk_level)} tone={tone === "positive" ? "neutral" : tone} />
        <MetricCell label="得分" value={`${Math.round(item.signal.signal_score)}分`} tone={tone} />
      </div>
      <div className="mobile-design-card-actions">
        <small>{buildMonitorNote(item.headline_reason, item.headline_blocker)}</small>
        <button type="button" className="mobile-design-action-button danger" onClick={() => void onRemove(item.symbol)}>
          移除
        </button>
      </div>
    </article>
  )
}

export function MobileHoldingStockCard({
  row,
  signalActive = false,
  onEdit,
  onRemove
}: {
  row: MobileHoldingRowData
  signalActive?: boolean
  onEdit: (item: WatchlistItem) => void
  onRemove: (item: WatchlistItem) => void | Promise<void>
}) {
  const price = row.quote?.last_price ?? null
  const changePct = row.quote?.change_pct ?? null
  const pnlTone = signedTone(row.floatingPnL)
  const actionTone = row.plainActionText?.includes("反") ? "negative" : row.plainActionText?.includes("正") ? "positive" : "neutral"
  return (
    <article className={`mobile-design-stock-card ${signalActive ? "signal-active" : ""}`}>
      <StockHead
        name={row.record.name}
        symbol={row.record.symbol}
        price={price}
        changePct={changePct}
        tags={[
          { label: row.plainActionText || "持仓", tone: actionTone },
          { label: "T+1", tone: "gold" }
        ]}
      />
      <div className="mobile-design-stock-grid">
        <MetricCell label="盈亏" value={formatSigned(row.floatingPnL)} tone={pnlTone} />
        <MetricCell label="持仓" value={String(row.record.base_position)} />
        <MetricCell label="可用" value={String(row.record.available_position)} />
        <MetricCell label="成本" value={formatPrice(row.record.cost_basis)} />
      </div>
      <div className="mobile-design-card-actions">
        <small>{row.plainActionReason || `现价 ${formatPrice(price)}，按持仓规则处理。`}</small>
        <div className="mobile-design-action-group">
          <button type="button" className="mobile-design-action-button" onClick={() => onEdit(row.record)}>
            编辑
          </button>
          <button type="button" className="mobile-design-action-button danger" onClick={() => void onRemove(row.record)}>
            删除
          </button>
        </div>
      </div>
    </article>
  )
}

function StockHead({
  name,
  symbol,
  price,
  changePct,
  tags
}: {
  name: string
  symbol: string
  price?: number | null
  changePct?: number | null
  tags: Array<{ label: string; tone?: Tone | "gold" }>
}) {
  return (
    <div className="mobile-design-stock-head">
      <div>
        <div className="mobile-design-stock-name">
          <strong>{name}</strong>
          <code>{symbol}</code>
        </div>
        <div className="mobile-design-stock-tags">
          {tags.map((tag, index) => (
            <span key={`${tag.label}-${index}`} className={`mobile-design-pill tone-${tag.tone ?? "neutral"}`}>
              {tag.label}
            </span>
          ))}
        </div>
      </div>
      <div className={`mobile-design-stock-price ${getPriceToneClass(changePct)}`}>
        <strong>{formatPrice(price)}</strong>
        <span>{formatPercent(changePct)}</span>
      </div>
    </div>
  )
}

function MetricCell({
  label,
  value,
  tone = "neutral"
}: {
  label: string
  value: string
  tone?: Tone
}) {
  return (
    <div>
      <span>{label}</span>
      <strong className={`tone-${tone}`}>{value}</strong>
    </div>
  )
}

export function splitPriorityItems<T extends MobileLowBuyCardItem>(items: T[]) {
  const buyNow = items.filter((item) => item.buy_signal_state === "buy_now" || item.buy_signal_state === "soft_buy_now")
  const nearEntry = items.filter((item) => item.buy_signal_state === "near_entry")
  const watch = items.filter((item) => !buyNow.includes(item) && !nearEntry.includes(item))
  return { buyNow, nearEntry, watch }
}

export function formatPrice(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--"
  return value >= 100 ? value.toFixed(2) : value.toFixed(3)
}

export function formatAmountCompact(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--"
  return value.toLocaleString("zh-CN", {
    maximumFractionDigits: 0
  })
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--"
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

function formatRatioPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--"
  return `${(value * 100).toFixed(0)}%`
}

function formatSigned(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--"
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`
}

function signedTone(value: number | null | undefined): Tone {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral"
  if (value > 0) return "positive"
  if (value < 0) return "negative"
  return "neutral"
}

function signalTone(action: string): Tone {
  if (action === "positive_t" || action === "buy_now" || action === "soft_buy_now") return "positive"
  if (action === "negative_t" || action === "avoid") return "negative"
  if (action === "near_entry") return "warning"
  return "neutral"
}

function actionLabel(action: string) {
  switch (action) {
    case "positive_t":
      return "正T"
    case "negative_t":
      return "反T"
    case "buy_now":
      return "买入"
    case "soft_buy_now":
      return "低吸"
    case "near_entry":
      return "接近"
    case "watch":
      return "观察"
    case "avoid":
      return "回避"
    case "hold":
      return "观望"
    default:
      return action
  }
}

function riskLabel(level: string) {
  switch (level) {
    case "low":
      return "低"
    case "medium":
      return "中"
    case "high":
      return "高"
    default:
      return level
  }
}

function strategyMarkers(item: MobileLowBuyCardItem) {
  const titles = "strategy_titles" in item && item.strategy_titles?.length ? item.strategy_titles : [item.strategy_title]
  const markers = titles
    .map((title) => title.trim().slice(0, 1))
    .filter(Boolean)
    .slice(0, 4)
  return markers.length ? markers : ["策"]
}

function priorityScore(item: MobileLowBuyCardItem) {
  return "priority_score" in item ? item.priority_score : item.score
}

function lowBuyActionSummary(item: MobileLowBuyCardItem) {
  if ("next_action_text" in item && item.next_action_text) {
    return item.next_action_text
  }
  if (item.recommendation_duration_text) {
    return item.recommendation_duration_text
  }
  if ("action_summary" in item && item.action_summary) {
    return item.action_summary
  }
  if ("buy_signal_hint" in item && item.buy_signal_hint) {
    return item.buy_signal_hint
  }
  if ("execution_note" in item && item.execution_note) {
    return item.execution_note
  }
  if ("summary_reason" in item && item.summary_reason) {
    return item.summary_reason
  }
  return "按策略规则等待确认。"
}

function shortPositionHint(value: string) {
  const percentMatch = value.match(/(\d+%)/)
  if (percentMatch) return percentMatch[1]
  return value.length > 4 ? `${value.slice(0, 4)}…` : value
}

function cleanMonitorReasonText(value: string) {
  return value
    .replace(/^当前场景[^。]*。?\s*/, "")
    .replace(/^·\s*/, "")
    .trim()
}

function buildMonitorNote(reason: string, blocker: string) {
  const cleanedReason = cleanMonitorReasonText(reason)
  if (cleanedReason && blocker) return `${cleanedReason} · ${blocker}`
  return cleanedReason || blocker || "等待信号更新"
}
