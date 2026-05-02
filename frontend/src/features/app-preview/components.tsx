import type { AppWatchlistCard, LowBuyCandidate } from "../../types"
import { getPriceTone, getPriceToneClass } from "../../utils/priceTone"

type Tone = "positive" | "negative" | "neutral"

export function formatPrice(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--"
  }
  return value >= 100 ? value.toFixed(2) : value.toFixed(3)
}

export function formatPercent(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
    : "--"
}

export function formatSigned(value: number | null | undefined, digits = 2) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`
    : "--"
}

export function signalTone(action: string): Tone {
  if (action === "positive_t" || action === "buy_now" || action === "soft_buy_now") {
    return "positive"
  }
  if (action === "negative_t" || action === "avoid") {
    return "negative"
  }
  return "neutral"
}

export function actionLabel(action: string) {
  switch (action) {
    case "positive_t":
      return "正T"
    case "negative_t":
      return "反T"
    case "hold":
      return "观望"
    case "buy_now":
      return "介入"
    case "soft_buy_now":
      return "低吸"
    case "near_entry":
      return "临界"
    case "watch":
      return "观察"
    case "avoid":
      return "回避"
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

function scoreBand(score: number) {
  if (score >= 80) {
    return "较高"
  }
  if (score >= 65) {
    return "中高"
  }
  return "中等"
}

function shortPositionHint(value: string) {
  const percentMatch = value.match(/(\d+%)/)
  if (percentMatch) {
    if (value.includes("试仓")) {
      return `试仓${percentMatch[1]}`
    }
    if (value.includes("加仓")) {
      return `加仓${percentMatch[1]}`
    }
    return percentMatch[1]
  }

  return value.length > 6 ? `${value.slice(0, 6)}…` : value
}

function listOrEmpty<T>(items: T[] | null | undefined): T[] {
  return Array.isArray(items) ? items : []
}

function cleanMonitorReasonText(value: string) {
  return value
    .replace(/^当前场景[^。]*。?\s*/, "")
    .replace(/^·\s*/, "")
    .trim()
}

function buildMonitorNote(reason: string, blocker: string) {
  const cleanedReason = cleanMonitorReasonText(reason)
  if (cleanedReason && blocker) {
    return `${cleanedReason} · ${blocker}`
  }
  return cleanedReason || blocker || "等待信号更新"
}

function trendPath(tone: Tone) {
  if (tone === "positive") {
    return "M2 30 C14 26,16 10,24 12 C31 14,34 6,42 7 C47 8,51 15,58 12 C66 9,70 4,78 6"
  }
  if (tone === "negative") {
    return "M2 8 C12 10,14 19,22 18 C30 17,32 9,40 12 C48 15,53 22,60 20 C66 18,71 12,78 6"
  }
  return "M2 18 C12 16,16 20,24 18 C31 16,36 15,42 17 C49 19,53 14,60 15 C66 16,72 12,78 14"
}

function MiniTrend({ tone }: { tone: Tone }) {
  return (
    <svg viewBox="0 0 80 32" className={`app-preview-mini-chart tone-${tone}`} aria-hidden="true">
      <path d={trendPath(tone)} pathLength={1} />
    </svg>
  )
}

function Metric({
  label,
  value,
  tone = "neutral"
}: {
  label: string
  value: string
  tone?: Tone
}) {
  return (
    <div className="app-preview-metric">
      <span>{label}</span>
      <strong className={`tone-${tone}`}>{value}</strong>
    </div>
  )
}

export function CandidateCard({
  candidate,
  onOpen,
  compact = false,
  rank
}: {
  candidate: LowBuyCandidate
  onOpen: (symbol: string) => void
  compact?: boolean
  rank?: number
}) {
  if (!compact) {
    return (
      <button type="button" className="app-preview-candidate" onClick={() => onOpen(candidate.symbol)}>
        <div className="app-preview-row">
          <div>
            <strong>
              {candidate.symbol} {candidate.name}
            </strong>
            <small>{candidate.sector_name ?? "未分类"}</small>
          </div>
          <span className={`app-preview-pill tone-${signalTone(candidate.buy_signal_state)}`}>
            {candidate.buy_signal_text}
          </span>
        </div>
        <div className="app-preview-candidate-metrics">
          <span>
            现价 <strong className={getPriceToneClass(candidate.change_pct)}>{formatPrice(candidate.latest_price)}</strong>
          </span>
          <span>
            涨跌 <strong className={getPriceToneClass(candidate.change_pct)}>{formatPercent(candidate.change_pct)}</strong>
          </span>
          <span>分数 {candidate.score.toFixed(1)}</span>
        </div>
        <p>{candidate.summary_reason}</p>
      </button>
    )
  }

  const tone = signalTone(candidate.buy_signal_state)
  const candidateTags = listOrEmpty(candidate.tags)
  return (
    <button
      type="button"
      className="app-preview-candidate app-preview-candidate-compact"
      onClick={() => onOpen(candidate.symbol)}
    >
      <div className="app-preview-card-top app-preview-card-top-candidate">
        <div className={`app-preview-rank-badge rank-${Math.min(rank ?? 9, 3)}`}>{rank ?? "-"}</div>
        <div className="app-preview-card-identity">
          <div className="app-preview-card-title">
            <strong>{candidate.name}</strong>
            <div className="app-preview-card-inline-meta">
              <span className={`app-preview-inline-price ${getPriceToneClass(candidate.change_pct)}`}>
                {formatPrice(candidate.latest_price)}
              </span>
              <small>{candidate.symbol}</small>
            </div>
          </div>
          <div className="app-preview-tag-row">
            {(candidateTags.length ? candidateTags : [candidate.sector_name ?? "候选池"]).slice(0, 2).map((tag) => (
              <span key={tag} className="app-preview-tag">
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div className="app-preview-score-box">
          <strong>{candidate.score.toFixed(1)}</strong>
          <small>分</small>
        </div>
      </div>

      <div className="app-preview-card-metrics app-preview-card-metrics-candidate">
        <Metric
          label="买点"
          value={`${formatPrice(candidate.entry_zone_low)}-${formatPrice(candidate.entry_zone_high)}`}
          tone={tone}
        />
        <Metric label="量比" value={`${candidate.volume_burst_ratio.toFixed(1)}x`} tone="positive" />
        <Metric label="回撤" value={`${candidate.retracement_days}天`} tone="neutral" />
        <Metric label="仓位" value={shortPositionHint(candidate.suggested_position_text)} tone={tone} />
      </div>

      <div className="app-preview-card-footer">
        <div className="app-preview-card-foot-meta">
          <span className={`app-preview-pill tone-${tone}`}>{actionLabel(candidate.buy_signal_state)}</span>
          <span>止损 {formatPrice(candidate.stop_loss)}</span>
          <span>{candidate.execution_ready ? "可执行" : "待观察"}</span>
        </div>
        <MiniTrend tone={tone} />
      </div>
    </button>
  )
}

export function HomeCard({
  item,
  compact = false,
  onRemove
}: {
  item: AppWatchlistCard
  compact?: boolean
  onRemove?: (item: AppWatchlistCard) => void | Promise<unknown>
}) {
  const monitorNote = buildMonitorNote(item.headline_reason, item.headline_blocker)

  if (!compact) {
    return (
      <article className="app-preview-monitor-card">
        <div className="app-preview-row">
          <div>
            <strong>
              {item.symbol} {item.name}
            </strong>
            <small>
              底仓 {item.base_position} / 可卖 {item.available_position}
            </small>
          </div>
          <span className={`app-preview-pill tone-${signalTone(item.signal.action)}`}>
            {item.signal.action}
          </span>
        </div>
        <div className="app-preview-monitor-price">
          <strong className={getPriceToneClass(item.quote.change_pct)}>{formatPrice(item.quote.last_price)}</strong>
          <span className={getPriceToneClass(item.quote.change_pct)}>{formatPercent(item.quote.change_pct)}</span>
        </div>
        <p>{monitorNote}</p>
      </article>
    )
  }

  const tone = signalTone(item.signal.action)
  return (
    <article className="app-preview-monitor-card app-preview-monitor-card-compact">
      <div className="app-preview-card-top app-preview-card-top-watchlist">
        <div className="app-preview-card-identity">
          <div className="app-preview-card-title">
            <strong>{item.name}</strong>
            <small>{item.symbol}</small>
          </div>
          <div className="app-preview-position-row">
            <span>底仓 {item.base_position}</span>
            <span>可卖 {item.available_position}</span>
            <span>成本 {formatPrice(item.cost_basis)}</span>
          </div>
        </div>
        <div className="app-preview-price-box">
          <strong className={getPriceToneClass(item.quote.change_pct)}>
            {formatPrice(item.quote.last_price)}
          </strong>
          <small className={getPriceToneClass(item.quote.change_pct)}>
            {formatSigned(item.quote.change_amount)} / {formatPercent(item.quote.change_pct)}
          </small>
        </div>
      </div>

      <div className="app-preview-card-metrics app-preview-card-metrics-watchlist">
        <Metric label="信号" value={actionLabel(item.signal.action)} tone={tone} />
        <Metric label="风险" value={riskLabel(item.signal.risk_level)} tone={tone === "positive" ? "neutral" : tone} />
        <Metric label="可操" value={`${Math.round(item.signal.tradability_score)}分`} tone="positive" />
        <Metric label="得分" value={`${Math.round(item.signal.signal_score)}分`} tone={tone} />
      </div>

      <div className="app-preview-card-footer">
        <div className="app-preview-card-foot-meta">
          <span className={`app-preview-pill tone-${tone}`}>{actionLabel(item.signal.action)}</span>
          <span>{scoreBand(item.signal.signal_score)}</span>
          <span>{item.rules.same_day_sell_allowed ? "可日内" : "T+1"}</span>
        </div>
        <MiniTrend tone={getPriceTone(item.quote.change_pct)} />
      </div>

      <div className="app-preview-card-bottom-row">
        <p className="app-preview-card-note">
          {monitorNote}
        </p>
        {onRemove ? (
          <button
            type="button"
            className="app-preview-remove-button"
            aria-label={`移除 ${item.name}`}
            onClick={() => void onRemove(item)}
          >
            移除
          </button>
        ) : null}
      </div>
    </article>
  )
}
