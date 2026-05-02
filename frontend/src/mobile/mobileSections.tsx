import type { AppLowBuyDetailResponse } from "../types"
import { formatPercent, formatPrice } from "../features/app-preview/components"
import { getPriceToneClass } from "../utils/priceTone"

export function formatTimeLabel(value?: string | null) {
  if (!value) {
    return "--:--:--"
  }
  const match = value.match(/(\d{2}:\d{2}:\d{2})/)
  return match?.[1] ?? value
}

export function formatRatioPercent(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--"
  }
  return `${(value * 100).toFixed(0)}%`
}

export function formatAmount(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--"
  }
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)
}

export function listOrEmpty<T>(items: T[] | null | undefined): T[] {
  return Array.isArray(items) ? items : []
}

export function Icon({
  name
}: {
  name: "refresh" | "search" | "filter" | "close"
}) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.9,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const
  }

  if (name === "refresh") {
    return (
      <svg {...common}>
        <path d="M20 11a8 8 0 0 0-14.9-3" />
        <path d="M4 4v4h4" />
        <path d="M4 13a8 8 0 0 0 14.9 3" />
        <path d="M20 20v-4h-4" />
      </svg>
    )
  }

  if (name === "search") {
    return (
      <svg {...common}>
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20 17 17" />
      </svg>
    )
  }

  if (name === "filter") {
    return (
      <svg {...common}>
        <path d="M4 5h16" />
        <path d="M7 12h10" />
        <path d="M10 19h4" />
      </svg>
    )
  }

  return (
    <svg {...common}>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  )
}

export function StatStrip({
  items
}: {
  items: Array<{ label: string; value: string; change: string; tone?: "positive" | "negative" | "neutral" }>
}) {
  return (
    <section className="mobile-app-market-strip">
      {items.map((item) => (
        <article key={item.label} className="mobile-app-market-cell">
          <small>{item.label}</small>
          <div className="mobile-app-market-main">
            <strong className={`tone-${item.tone ?? "neutral"}`}>{item.value}</strong>
            <span className={`tone-${item.tone ?? "neutral"}`}>{item.change}</span>
          </div>
          <div className="mobile-app-market-line" />
        </article>
      ))}
    </section>
  )
}

export function SegmentTabs({
  items,
  onChange
}: {
  items: Array<{ key: string; label: string; active?: boolean }>
  onChange: (key: string) => void
}) {
  return (
    <div className="mobile-app-segment-tabs" role="tablist" aria-label="分段导航">
      {items.map((item) => (
        <button key={item.key} type="button" className={item.active ? "active" : ""} onClick={() => onChange(item.key)}>
          {item.label}
        </button>
      ))}
    </div>
  )
}

interface MarketPulseBoard {
  market_state_text?: string
  hot_industries?: string[] | null
  stock_up_ratio?: number
  stock_median_change?: number
  limit_up_count?: number
  board_height?: number
  broken_board_ratio?: number
  immediate_count?: number
  focus_count?: number
  track_count?: number
}

export function MarketPulse({
  board
}: {
  board?: MarketPulseBoard | null
}) {
  if (!board) {
    return null
  }

  const hotIndustries = listOrEmpty(board.hot_industries).slice(0, 3)

  return (
    <section className="mobile-app-market-pulse">
      <div className="mobile-app-pulse-head">
        <strong>{board.market_state_text || "市场状态"}</strong>
        <small>
          可执行 {board.immediate_count ?? 0} / 观察 {board.focus_count ?? 0} / 跟踪 {board.track_count ?? 0}
        </small>
      </div>
      <div className="mobile-app-pulse-grid">
        <span>涨家 {formatRatioPercent(board.stock_up_ratio)}</span>
        <span>中位 {formatPercent(board.stock_median_change)}</span>
        <span>涨停 {board.limit_up_count}</span>
        <span>高度 {board.board_height || "--"}板</span>
        <span>炸板 {formatRatioPercent(board.broken_board_ratio)}</span>
        <span>{hotIndustries.length ? hotIndustries.join(" / ") : "热点未确认"}</span>
      </div>
    </section>
  )
}

export function MetricLine({
  label,
  value,
  tone = "neutral"
}: {
  label: string
  value: string
  tone?: "positive" | "negative" | "neutral"
}) {
  return (
    <div className="mobile-app-detail-metric">
      <span>{label}</span>
      <strong className={`tone-${tone}`}>{value}</strong>
    </div>
  )
}

export function LowBuyDetailSheet({
  detail,
  inWatchlist,
  onClose,
  onMarkBought
}: {
  detail: AppLowBuyDetailResponse | null
  inWatchlist: boolean
  onClose: () => void
  onMarkBought: () => void
}) {
  if (!detail) {
    return null
  }
  const hasEntryZone =
    Number.isFinite(detail.candidate.entry_zone_low) &&
    Number.isFinite(detail.candidate.entry_zone_high) &&
    detail.candidate.entry_zone_low > 0 &&
    detail.candidate.entry_zone_high >= detail.candidate.entry_zone_low
  const isHighRisk = detail.candidate.risk_tier === "block" || detail.candidate.hard_risk?.level === "block"
  const markBoughtDisabled = inWatchlist || isHighRisk || !hasEntryZone

  return (
    <div className="mobile-app-sheet-backdrop" role="presentation" onClick={onClose}>
      <section className="mobile-app-sheet" onClick={(event) => event.stopPropagation()}>
        <div className="mobile-app-sheet-head">
          <div>
            <div className="mobile-app-sheet-title">
              <h2>{detail.candidate.name}</h2>
              <small>{detail.candidate.symbol}</small>
              {inWatchlist ? <span className="mobile-app-sheet-badge">持仓</span> : null}
            </div>
            <div className="mobile-app-sheet-tags">
              {(listOrEmpty(detail.candidate.tags).length
                ? listOrEmpty(detail.candidate.tags)
                : [detail.candidate.sector_name ?? "候选池"])
                .slice(0, 2)
                .map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
            </div>
          </div>
          <div className="mobile-app-sheet-score">
            <strong>{detail.candidate.score.toFixed(1)}</strong>
            <small>信号综合分</small>
            <button type="button" className="mobile-app-icon-button" onClick={onClose}>
              <Icon name="close" />
            </button>
          </div>
        </div>

        <div className="mobile-app-sheet-body">
          <div className="mobile-app-sheet-primary">
            <div className="mobile-app-sheet-price">
              <strong className={getPriceToneClass(detail.candidate.change_pct)}>
                {formatPrice(detail.candidate.latest_price)}
              </strong>
              <span className={getPriceToneClass(detail.candidate.change_pct)}>
                {formatPercent(detail.candidate.change_pct)}
              </span>
            </div>
            <div className="mobile-app-detail-tabs">
              <button type="button" className="active">
                分时
              </button>
              <button type="button">日K</button>
              <button type="button">周K</button>
            </div>
            <div className="mobile-app-detail-chart">
              <div className="mobile-app-detail-curve" />
            </div>
          </div>

          <div className="mobile-app-sheet-side">
            <MetricLine
              label="买点区"
              value={`${formatPrice(detail.candidate.entry_zone_low)} - ${formatPrice(detail.candidate.entry_zone_high)}`}
            />
            <MetricLine label="止损位" value={formatPrice(detail.candidate.stop_loss)} tone="negative" />
            <MetricLine label="仓位建议" value={detail.candidate.suggested_position_text} tone="positive" />
            <MetricLine
              label="推荐天数"
              value={recommendationDaysText(detail.candidate.recommendation_days)}
              tone="neutral"
            />
            <MetricLine
              label="预期价差"
              value={formatPercent(detail.candidate.entry_distance_pct)}
              tone={detail.candidate.entry_distance_pct >= 0 ? "positive" : "negative"}
            />
          </div>
        </div>

        <div className="mobile-app-callout mobile-app-callout-detail">
          <strong>下一步动作</strong>
          <span>{detail.candidate.buy_signal_hint || detail.candidate.execution_note}</span>
        </div>

        <div className="mobile-app-callout mobile-app-callout-detail">
          <strong>退出计划</strong>
          <span>
            {detail.candidate.recommendation_duration_text || "按买点试仓，冲高先减仓，跌破止损先退出。"}
            {detail.candidate.exit_plan?.invalid_condition ? ` ${detail.candidate.exit_plan.invalid_condition}` : ""}
          </span>
        </div>

        <section className="mobile-app-detail-section">
          <h3>触发理由</h3>
          <ul>
            {listOrEmpty(detail.candidate.reasons).slice(0, 3).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </section>

        <section className="mobile-app-detail-section">
          <h3>风险提示</h3>
          <ul>
            {listOrEmpty(detail.candidate.risks).slice(0, 3).map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </section>

        <div className="mobile-app-sheet-actions">
          <button type="button" className="mobile-app-secondary" onClick={onClose}>
            收起
          </button>
          <button
            type="button"
            className="mobile-app-primary"
            onClick={onMarkBought}
            disabled={markBoughtDisabled}
          >
            {inWatchlist ? "已买入 ✓" : "模拟买入"}
          </button>
        </div>
      </section>
    </div>
  )
}

function recommendationDaysText(days?: number) {
  return days && days > 0 ? `${days} 个交易日` : "--";
}
