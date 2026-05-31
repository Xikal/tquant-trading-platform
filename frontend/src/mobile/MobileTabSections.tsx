import { useMemo } from "react"
import { Button, Input } from "antd-mobile"
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
  formatPrice,
  splitPriorityItems
} from "./MobileDesignCards"
import type { LowBuyPriorityBoardResult } from "../types"
import { useMobileUiStore } from "../stores/mobileUiStore"
import { VirtualCardList } from "../ui/list/VirtualCardList"

type Tone = "positive" | "negative" | "neutral" | "warning"
type LowBuyGroups = ReturnType<typeof splitPriorityItems<MobileLowBuyCardItem>>

export function MobileHomeSection({
  metrics,
  priorityBoard,
  priorityBoardItems,
  priorityPulseTime,
  todayActionTitle,
  todayActionNote,
  watchlistMap,
  loading,
  onOpenCandidate,
  onSwitchToLowBuy
}: {
  metrics: MobileMetricItem[]
  priorityBoard: LowBuyPriorityBoardResult | null
  priorityBoardItems: LowBuyPriorityBoardItem[]
  priorityPulseTime: string
  todayActionTitle?: string
  todayActionNote?: string
  watchlistMap: Map<string, WatchlistItem>
  loading: boolean
  onOpenCandidate: (symbol: string) => void | Promise<void>
  onSwitchToLowBuy: () => void
}) {
  const top = priorityBoardItems[0]
  return (
    <>
      <MobileMetricRow items={metrics} />
      <MobileMarketPills board={priorityBoard} />
      <section className="mobile-today-one-thing">
        <span>今天最重要一件事</span>
        <strong>{todayActionTitle || (top ? `${top.name}：${top.buy_signal_text || "等待确认"}` : "暂无明确可执行信号")}</strong>
        <small>{todayActionNote || (top ? `买点 ${formatPrice(top.entry_zone_low)}-${formatPrice(top.entry_zone_high)}，止损 ${formatPrice(top.stop_loss)}` : "先等榜单刷新，不强行交易。")}</small>
      </section>

      <MobileSectionTitle
        title="选股宝典优先榜"
        hint={`按当前策略综合分排序 · ${priorityPulseTime} 刷新`}
        action={
          <Button fill="outline" className="mobile-design-pill tone-gold" onClick={onSwitchToLowBuy}>
            去选股宝典
          </Button>
        }
      />
      <VirtualCardList
        className="mobile-design-priority-scroll"
        items={priorityBoardItems}
        empty={!loading ? <div className="mobile-app-empty">当前没有榜单数据</div> : null}
        estimateSize={178}
        maxHeight={466}
        getItemKey={(item) => item.symbol}
        renderItem={(item, index) => (
          <MobilePriorityStockCard
            item={item}
            highlight={index === 0}
            inWatchlist={watchlistMap.has(item.symbol)}
            onOpen={onOpenCandidate}
          />
        )}
      />
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
  const query = useMobileUiStore((state) => state.holdingQuery)
  const setQuery = useMobileUiStore((state) => state.setHoldingQuery)
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
          <Button fill="outline" className="mobile-design-pill tone-gold" onClick={onCreateHolding}>
            新增持仓
          </Button>
        }
      />
      <div className="mobile-holding-search">
        <Input
          value={query}
          onChange={setQuery}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              handleSearchSubmit()
            }
          }}
          placeholder="搜索代码/名称，未持仓可自动补全"
        />
        <Button onClick={handleSearchSubmit}>
          搜索
        </Button>
      </div>
      <VirtualCardList
        className="mobile-design-list"
        items={filteredRows}
        empty={!loading ? <div className="mobile-app-empty">暂无持仓，点击右上角添加</div> : null}
        estimateSize={176}
        maxHeight={520}
        getItemKey={(row) => row.record.symbol}
        renderItem={(row) => (
          <MobileHoldingStockCard
            row={row}
            signalActive={activeHoldingSignalSymbols.has(row.record.symbol)}
            onEdit={onEditHolding}
            onRemove={onRemoveHolding}
          />
        )}
      />
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
        title="现在可买"
        hint="只显示最需要处理的候选"
        action={
          <Button fill="outline" className="mobile-design-pill tone-gold" onClick={onOpenAi}>
            解读榜单
          </Button>
        }
      />
      <VirtualCardList
        className="mobile-design-list"
        items={playbookGroups.buyNow}
        empty={!loading && !playbookLoading ? <div className="mobile-app-empty">当前策略暂无现在可买的候选</div> : null}
        estimateSize={176}
        maxHeight={520}
        getItemKey={(item) => item.symbol}
        renderItem={(item, index) => (
          <MobilePriorityStockCard
            item={item}
            highlight={index === 0}
            inWatchlist={watchlistMap.has(item.symbol)}
            onOpen={(symbol) => void onOpenCandidate(symbol, strategyFilter)}
            onBought={onBought}
          />
        )}
      />

      <MobileSectionTitle title="等确认" hint="到价但还缺承接" />
      <VirtualCardList
        className="mobile-design-list"
        items={playbookGroups.nearEntry}
        empty={!loading && !playbookLoading ? <div className="mobile-app-empty">当前策略暂无接近买点</div> : null}
        estimateSize={176}
        maxHeight={520}
        getItemKey={(item) => item.symbol}
        renderItem={(item) => (
          <MobilePriorityStockCard
            item={item}
            inWatchlist={watchlistMap.has(item.symbol)}
            onOpen={(symbol) => void onOpenCandidate(symbol, strategyFilter)}
            onBought={onBought}
          />
        )}
      />

      <MobileSectionTitle title="更多观察" hint="不急执行，展开后再看" />
      <VirtualCardList
        className="mobile-design-list"
        items={playbookGroups.watch}
        empty={!loading && !playbookLoading ? <div className="mobile-app-empty">当前策略暂无观察票</div> : null}
        estimateSize={176}
        maxHeight={520}
        getItemKey={(item) => item.symbol}
        renderItem={(item) => (
          <MobilePriorityStockCard
            item={item}
            inWatchlist={watchlistMap.has(item.symbol)}
            onOpen={(symbol) => void onOpenCandidate(symbol, strategyFilter)}
            onBought={onBought}
          />
        )}
      />
    </>
  )
}

function signedTone(value: number | null | undefined): Tone {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral"
  if (value > 0) return "positive"
  if (value < 0) return "negative"
  return "neutral"
}
