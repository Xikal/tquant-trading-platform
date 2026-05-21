import { Button } from "antd-mobile"
import type { AppWatchlistCard, LowBuyPriorityBoardItem, WatchlistItem } from "../../types"
import { getPriceToneClass } from "../../utils/priceTone"
import {
  formatPercent,
  formatPrice,
  formatSigned,
  signalTone
} from "./components"

export interface HoldingRowData {
  record: WatchlistItem
  quote: AppWatchlistCard["quote"] | null
  floatingPnL: number | null
  floatingPnLPct: number | null
  marketValue: number | null
  plainActionText?: string
  plainActionReason?: string
  plainExecutionText?: string
  plainInvalidCondition?: string
}

function strategyMarkers(item: LowBuyPriorityBoardItem) {
  const titles = item.strategy_titles.length ? item.strategy_titles : [item.strategy_title]
  const markers = titles
    .map((title) => title.trim().slice(0, 1))
    .filter(Boolean)
    .slice(0, 5)

  return markers.length ? markers : ["策"]
}

export function HoldingCard({
  row,
  onEdit,
  onRemove
}: {
  row: HoldingRowData
  onEdit: (item: WatchlistItem) => void
  onRemove: (item: WatchlistItem) => void | Promise<void>
}) {
  const changePct = row.quote?.change_pct ?? null
  const priceToneClass = getPriceToneClass(changePct)
  const pnlToneClass = getPriceToneClass(row.floatingPnLPct)

  return (
    <article className="mobile-holding-card">
      <div className="mobile-holding-card-head">
        <div className="mobile-holding-title">
          <strong>{row.record.name}</strong>
          <small>{row.record.symbol}</small>
        </div>
        <div className="mobile-holding-card-actions">
          <Button fill="none" className="mobile-inline-action" onClick={() => onEdit(row.record)}>
            编辑
          </Button>
          <Button
            fill="none"
            className="mobile-inline-action mobile-inline-danger"
            aria-label={`删除 ${row.record.name}`}
            onClick={() => void onRemove(row.record)}
          >
            删除
          </Button>
        </div>
      </div>

      <div className="mobile-holding-inline">
        <div className="mobile-holding-inline-item">
          <span>盈亏</span>
          <strong className={pnlToneClass}>{formatSigned(row.floatingPnL)}</strong>
          <small className={pnlToneClass}>{formatPercent(row.floatingPnLPct)}</small>
        </div>
        <div className="mobile-holding-inline-item">
          <span>持仓</span>
          <strong>{row.record.base_position}</strong>
          <small>可用 {row.record.available_position}</small>
        </div>
        <div className="mobile-holding-inline-item">
          <span>成本/现价</span>
          <strong>{formatPrice(row.record.cost_basis)}</strong>
          <small className={priceToneClass}>{formatPrice(row.quote?.last_price)}</small>
        </div>
      </div>
      {row.plainActionText ? (
        <div className="mobile-holding-action-note">
          <strong>{row.plainActionText}</strong>
          <span>{row.plainActionReason || "按触发价处理"}</span>
          {row.plainExecutionText ? <small>{row.plainExecutionText}</small> : null}
          {row.plainInvalidCondition ? <small>{row.plainInvalidCondition}</small> : null}
        </div>
      ) : null}
    </article>
  )
}

export function PriorityBoardCard({
  item,
  rank,
  inWatchlist,
  onOpen,
  onBought
}: {
  item: LowBuyPriorityBoardItem
  rank: number
  inWatchlist: boolean
  onOpen: (symbol: string) => void
  onBought: (item: LowBuyPriorityBoardItem) => void
}) {
  const tone = signalTone(item.buy_signal_state)
  const signalText = item.buy_signal_text || "等待"
  const strategyTags = strategyMarkers(item)
  const contextLabels = [
    item.sector_name,
    item.mainline_tier_text || item.industry_tier_text,
    item.strategy_family_text
  ].filter(Boolean)

  return (
    <article className="mobile-priority-card">
      <Button fill="none" className="mobile-priority-main" onClick={() => onOpen(item.symbol)}>
        <div className="mobile-priority-headline">
          <div className={`app-preview-rank-badge rank-${Math.min(rank, 3)}`}>{rank}</div>
          <div className="mobile-priority-identity">
            <div className="mobile-priority-title-line">
              <strong className="mobile-priority-name">{item.name}</strong>
              <small className="mobile-priority-code">{item.symbol}</small>
            </div>
            {contextLabels.length ? (
              <small className="mobile-priority-meta-line">{contextLabels.slice(0, 3).join(" · ")}</small>
            ) : null}
            <span className={`mobile-priority-price ${getPriceToneClass(item.change_pct)}`}>
              {formatPrice(item.latest_price)}
            </span>
          </div>
          <div className="mobile-priority-score mobile-priority-score-inline">
            <strong>{item.priority_score.toFixed(1)}</strong>
            <small>分</small>
          </div>
        </div>

        <div className="mobile-priority-grid mobile-priority-grid-three">
          <div>
            <span>买点</span>
            <strong>{formatPrice(item.entry_zone_low)}-{formatPrice(item.entry_zone_high)}</strong>
          </div>
          <div>
            <span>止损</span>
            <strong className="tone-negative">{formatPrice(item.stop_loss)}</strong>
          </div>
          <div>
            <span>买入</span>
            <strong className={`tone-${tone}`}>{signalText}</strong>
          </div>
        </div>
        {item.next_action_text ? (
          <p className="mobile-priority-action-text">{item.next_action_text}</p>
        ) : null}
        {item.recommendation_duration_text ? (
          <p className="mobile-priority-note">{item.recommendation_duration_text}</p>
        ) : null}
      </Button>

      <div className="mobile-priority-actions">
        <div className="mobile-priority-strategy-tags" aria-label="策略">
          {strategyTags.map((tag, index) => (
            <span key={`${tag}-${index}`}>{tag}</span>
          ))}
        </div>
        <Button fill="none" className="mobile-inline-action" onClick={() => onBought(item)}>
          {inWatchlist ? "已买入" : "模拟买入"}
        </Button>
      </div>
    </article>
  )
}
