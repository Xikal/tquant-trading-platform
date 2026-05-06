import { useMemo, useState } from "react"
import type { BacktestRunSummary } from "../api/backtests"
import { formatBacktestStrategies, formatPct } from "../utils/backtestFormatters"
import type { LowBuyPriorityBoardItem, WatchlistItem } from "../types"
import {
  MobileFocusCard,
  type MobileHoldingRowData,
  type MobileLowBuyCardItem,
  MobileMarketPills,
  type MobileMetricItem,
  MobileMetricRow,
  MobilePriorityStockCard,
  MobileHoldingStockCard,
  MobileSectionTitle,
  type MobileStrategyTabOption,
  type MobileStrategyTabKey,
  MobileStrategyTabs,
  splitPriorityItems
} from "./MobileDesignCards"
import type { LowBuyPriorityBoardResult } from "../types"

type Tone = "positive" | "negative" | "neutral" | "warning"
type LowBuyGroups = ReturnType<typeof splitPriorityItems<MobileLowBuyCardItem>>

export function MobileHomeSection({
  metrics,
  priorityBoard,
  priorityBoardItems,
  priorityPulseTime,
  watchlistMap,
  loading,
  onOpenCandidate,
  onSwitchToLowBuy
}: {
  metrics: MobileMetricItem[]
  priorityBoard: LowBuyPriorityBoardResult | null
  priorityBoardItems: LowBuyPriorityBoardItem[]
  priorityPulseTime: string
  watchlistMap: Map<string, WatchlistItem>
  loading: boolean
  onOpenCandidate: (symbol: string) => void | Promise<void>
  onSwitchToLowBuy: () => void
}) {
  return (
    <>
      <MobileMetricRow items={metrics} />
      <MobileMarketPills board={priorityBoard} />

      <MobileSectionTitle
        title="全策略优先级榜"
        hint={`按综合分排序 · ${priorityPulseTime} 刷新`}
        action={
          <button type="button" className="mobile-design-pill tone-gold" onClick={onSwitchToLowBuy}>
            去选股宝典
          </button>
        }
      />
      <section className="mobile-design-priority-scroll">
        {priorityBoardItems.slice(0, 5).map((item, index) => (
          <MobilePriorityStockCard
            key={item.symbol}
            item={item}
            highlight={index === 0}
            inWatchlist={watchlistMap.has(item.symbol)}
            onOpen={onOpenCandidate}
          />
        ))}
        {!loading && !priorityBoardItems.length ? (
          <div className="mobile-app-empty">当前没有榜单数据</div>
        ) : null}
      </section>
    </>
  )
}

export function MobileHoldingsSection({
  metrics,
  holdingRows,
  activeHoldingSignalSymbols,
  loading,
  onCreateHolding,
  onSearchHolding,
  onEditHolding,
  onRemoveHolding
}: {
  metrics: MobileMetricItem[]
  holdingRows: MobileHoldingRowData[]
  activeHoldingSignalSymbols: Set<string>
  loading: boolean
  onCreateHolding: () => void
  onSearchHolding: (symbol: string) => void | Promise<void>
  onEditHolding: (item: WatchlistItem) => void
  onRemoveHolding: (item: WatchlistItem) => void | Promise<void>
}) {
  const [query, setQuery] = useState("")
  const filteredRows = useMemo(() => {
    const normalized = query.trim().toUpperCase()
    if (!normalized) {
      return holdingRows
    }
    return holdingRows.filter((row) => {
      const symbol = row.record.symbol.toUpperCase()
      const name = row.record.name.toUpperCase()
      return symbol.includes(normalized) || name.includes(normalized)
    })
  }, [holdingRows, query])

  function handleSearchSubmit() {
    const normalized = query.trim().toUpperCase()
    if (normalized) {
      void onSearchHolding(normalized)
    }
  }

  return (
    <>
      <MobileMetricRow items={metrics} />

      <MobileSectionTitle
        title={`持仓 (${holdingRows.length})`}
        hint="编辑成本价、持仓数、可用数"
        action={
          <button type="button" className="mobile-design-pill tone-gold" onClick={onCreateHolding}>
            新增持仓
          </button>
        }
      />
      <div className="mobile-holding-search">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              handleSearchSubmit()
            }
          }}
          placeholder="搜索代码/名称，未持仓可自动补全"
        />
        <button type="button" onClick={handleSearchSubmit}>
          搜索
        </button>
      </div>
      <section className="mobile-design-list">
        {filteredRows.map((row) => (
          <MobileHoldingStockCard
            key={row.record.symbol}
            row={row}
            signalActive={activeHoldingSignalSymbols.has(row.record.symbol)}
            onEdit={onEditHolding}
            onRemove={onRemoveHolding}
          />
        ))}
        {!loading && !filteredRows.length ? (
          <div className="mobile-app-empty">暂无持仓，点击右上角添加</div>
        ) : null}
      </section>
    </>
  )
}

export function MobileLowBuySection({
  strategyFilter,
  strategyTabs,
  metrics,
  playbookItems,
  playbookGroups,
  watchlistMap,
  loading,
  playbookLoading,
  onStrategyChange,
  onOpenAi,
  onOpenCandidate,
  onBought,
  recentBacktests
}: {
  strategyFilter: MobileStrategyTabKey
  strategyTabs?: MobileStrategyTabOption[]
  metrics: MobileMetricItem[]
  playbookItems: MobileLowBuyCardItem[]
  playbookGroups: LowBuyGroups
  watchlistMap: Map<string, WatchlistItem>
  loading: boolean
  playbookLoading: boolean
  onStrategyChange: (nextStrategy: MobileStrategyTabKey) => void
  onOpenAi: () => void
  onOpenCandidate: (symbol: string, strategy: MobileStrategyTabKey) => void | Promise<void>
  onBought: (item: MobileLowBuyCardItem) => void
  recentBacktests?: BacktestRunSummary[]
}) {
  return (
    <>
      <MobileStrategyTabs active={strategyFilter} onChange={onStrategyChange} strategies={strategyTabs} />
      <MobileMetricRow items={metrics} />
      <MobileFocusCard item={playbookItems[0]} />
      <MobileRecentBacktests runs={recentBacktests ?? []} />

      <MobileSectionTitle
        title="确定买入"
        hint="优先执行"
        action={
          <button type="button" className="mobile-design-pill tone-gold" onClick={onOpenAi}>
            解读榜单
          </button>
        }
      />
      <section className="mobile-design-list">
        {playbookGroups.buyNow.slice(0, 4).map((item, index) => (
          <MobilePriorityStockCard
            key={item.symbol}
            item={item}
            highlight={index === 0}
            inWatchlist={watchlistMap.has(item.symbol)}
            onOpen={(symbol) => void onOpenCandidate(symbol, strategyFilter)}
            onBought={onBought}
          />
        ))}
        {!loading && !playbookLoading && !playbookGroups.buyNow.length ? (
          <div className="mobile-app-empty">当前策略暂无确定买入</div>
        ) : null}
      </section>

      <MobileSectionTitle title="接近买点" hint="等待确认" />
      <section className="mobile-design-list">
        {playbookGroups.nearEntry.slice(0, 4).map((item) => (
          <MobilePriorityStockCard
            key={item.symbol}
            item={item}
            inWatchlist={watchlistMap.has(item.symbol)}
            onOpen={(symbol) => void onOpenCandidate(symbol, strategyFilter)}
            onBought={onBought}
          />
        ))}
        {!loading && !playbookLoading && !playbookGroups.nearEntry.length ? (
          <div className="mobile-app-empty">当前策略暂无接近买点</div>
        ) : null}
      </section>

      <MobileSectionTitle title="继续观察" hint="不急执行" />
      <section className="mobile-design-list">
        {playbookGroups.watch.slice(0, 4).map((item) => (
          <MobilePriorityStockCard
            key={item.symbol}
            item={item}
            inWatchlist={watchlistMap.has(item.symbol)}
            onOpen={(symbol) => void onOpenCandidate(symbol, strategyFilter)}
            onBought={onBought}
          />
        ))}
        {!loading && !playbookLoading && !playbookGroups.watch.length ? (
          <div className="mobile-app-empty">当前策略暂无观察票</div>
        ) : null}
      </section>
    </>
  )
}

function MobileRecentBacktests({ runs }: { runs: BacktestRunSummary[] }) {
  return (
    <>
      <MobileSectionTitle title="最近回测" hint="最近 5 条任务摘要" />
      <section className="mobile-design-list mobile-recent-backtests">
        {runs.slice(0, 5).map((run) => (
          <article className="mobile-design-stock-card mobile-backtest-card" key={run.id}>
            <div className="mobile-design-stock-head">
              <div className="mobile-design-stock-name">
                <strong>{run.name || `回测 #${run.id}`}</strong>
                <span>{formatBacktestStrategies(run.strategies)}</span>
              </div>
              <div className={`mobile-design-pill tone-${run.status === "succeeded" ? "positive" : run.status === "failed" ? "negative" : "warning"}`}>
                {statusText(run.status)}
              </div>
            </div>
            <div className="mobile-design-stock-grid">
              <MobileBacktestMetric label="收益" value={formatPct(run.summary?.total_return_pct)} tone={signedTone(run.summary?.total_return_pct)} />
              <MobileBacktestMetric label="胜率" value={formatPct(run.summary?.win_rate_pct)} />
              <MobileBacktestMetric label="进度" value={`${Math.round(run.progress_pct ?? run.progress ?? 0)}%`} />
              <MobileBacktestMetric label="资产" value={formatBacktestMoney(run.final_equity)} />
            </div>
          </article>
        ))}
        {!runs.length ? <div className="mobile-app-empty">暂无最近回测任务</div> : null}
      </section>
    </>
  )
}

function MobileBacktestMetric({
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

function signedTone(value: number | null | undefined): Tone {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral"
  if (value > 0) return "positive"
  if (value < 0) return "negative"
  return "neutral"
}

function statusText(status?: string) {
  if (status === "succeeded") return "完成"
  if (status === "failed") return "失败"
  if (status === "running") return "运行中"
  if (status === "queued") return "排队"
  if (status === "cancelled") return "已取消"
  return status || "--"
}

function formatBacktestMoney(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--"
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 })
}
