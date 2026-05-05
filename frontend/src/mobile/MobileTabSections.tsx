import { useMemo, useState } from "react"
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
  onBought
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
}) {
  return (
    <>
      <MobileStrategyTabs active={strategyFilter} onChange={onStrategyChange} strategies={strategyTabs} />
      <MobileMetricRow items={metrics} />
      <MobileFocusCard item={playbookItems[0]} />

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
