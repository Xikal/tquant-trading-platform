import { startTransition, useEffect, useState } from "react"
import { PullToRefresh } from "antd-mobile"
import {
  HoldingEditorSheet,
  type HoldingEditorSeed
} from "../features/app-preview/holdingEditor"
import { appApi } from "../api/appClient"
import { useAppPreviewData } from "../features/app-preview/hooks"
import type { LowBuyPriorityBoardItem, WatchlistItem } from "../types"
import { MobileAppHeader, MobileStatusBanners, MobileTabBar } from "./MobileAppLayout"
import { MobileAuthScreen } from "./MobileAuthScreen"
import type { MobileLowBuyCardItem } from "./MobileDesignCards"
import { AiDecisionSheet, AppUpdateSheet, PriorityActionSheet } from "./MobileSheets"
import { MobileSectorSettingsSheet } from "./MobileSectorSettingsSheet"
import { MobileTabContent } from "./MobileTabContent"
import { LowBuyDetailSheet } from "./mobileSections"
import type { MobileTab } from "./mobileTypes"
import { useAppUpdate } from "./useAppUpdate"
import { useMobileAppViewModels } from "./useMobileAppViewModels"
import { useMobileAuth } from "./useMobileAuth"
import { useMobileHoldingSignals } from "./useMobileHoldingSignals"
import { useMobilePlaybook } from "./useMobilePlaybook"
import { useMobileSectorSettings } from "./useMobileSectorSettings"
import { useNativeRuntime } from "./useNativeRuntime"
import {
  createSeedFromDetail,
  createSeedFromLowBuyItem,
  createSeedFromWatchlist
} from "./mobileViewModels"

interface HoldingEditorState { mode: "create" | "buy" | "edit"; seed: HoldingEditorSeed }

const EMPTY_HOLDING_SEED: HoldingEditorSeed = {
  symbol: "",
  name: "",
  base_position: 0,
  available_position: 0,
  cost_basis: null,
  memo: ""
}

export default function MobileApp() {
  const {
    authUser,
    authLoading,
    authError,
    handleAuthSubmit,
    handleLogout
  } = useMobileAuth()
  const [activeTab, setActiveTab] = useState<MobileTab>("home")
  const appUpdate = useAppUpdate()
  const {
    home,
    watchlist,
    priorityBoard,
    loading,
    actionLoading,
    detail,
    error,
    message,
    pulseTime,
    priorityPulseTime,
    setActiveTab: setPreviewTab,
    setDetail,
    refreshActiveTab,
    openCandidate,
    saveHolding,
    removeWatchItem
  } = useAppPreviewData("first_board", Boolean(authUser))
  const {
    strategyFilter,
    strategyTabs,
    playbook,
    playbookLoading,
    playbookError,
    setStrategyFilter,
    loadMobilePlaybook
  } = useMobilePlaybook(Boolean(authUser) && activeTab === "low_buy")
  const [holdingEditor, setHoldingEditor] = useState<HoldingEditorState | null>(null)
  const [priorityActionItem, setPriorityActionItem] = useState<LowBuyPriorityBoardItem | null>(null)
  const [aiOpen, setAiOpen] = useState(false)
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)
  const [offline, setOffline] = useState(() => {
    if (typeof navigator === "undefined") {
      return false
    }
    return !navigator.onLine
  })

  useNativeRuntime(() => {
    startTransition(() => {
      void refreshActiveTab()
      void appUpdate.checkForUpdate()
    })
  })

  useEffect(() => {
    if (typeof window === "undefined") {
      return
    }
    const handleOnline = () => {
      setOffline(false)
      void refreshActiveTab()
      if (activeTab === "low_buy") {
        void loadMobilePlaybook(strategyFilter, true)
      }
    }
    const handleOffline = () => setOffline(true)
    window.addEventListener("online", handleOnline)
    window.addEventListener("offline", handleOffline)
    return () => {
      window.removeEventListener("online", handleOnline)
      window.removeEventListener("offline", handleOffline)
    }
  }, [activeTab, loadMobilePlaybook, refreshActiveTab, strategyFilter])

  const {
    watchlistMap,
    holdingRows,
    priorityBoardItems,
    playbookItems,
    playbookGroups,
    monitorMetrics,
    holdingsMetrics,
    lowBuyMetrics
  } = useMobileAppViewModels({
    home,
    watchlist,
    priorityBoard,
    playbook
  })
  const {
    activeHoldingSignalSymbols,
    signalToastVisible,
    hideSignalToast
  } = useMobileHoldingSignals(activeTab, holdingRows)
  const sectorSettings = useMobileSectorSettings({
    activeTab,
    refreshActiveTab,
    loadMobilePlaybook,
    strategyFilter
  })

  function openCreateHolding() {
    setHoldingEditor({
      mode: "create",
      seed: {
        symbol: "",
        name: "",
        base_position: 100,
        available_position: 0,
        cost_basis: null,
        memo: ""
      }
    })
  }

  function findLatestPrice(symbol: string) {
    const normalizedSymbol = symbol.trim().toUpperCase()
    const homeItem = home?.items.find((item) => item.symbol.toUpperCase() === normalizedSymbol)
    if (homeItem?.quote.last_price) {
      return homeItem.quote.last_price
    }
    const boardItem = priorityBoardItems.find((item) => item.symbol.toUpperCase() === normalizedSymbol)
    return boardItem?.latest_price ?? null
  }

  async function openSearchHolding(rawSymbol: string) {
    const normalizedSymbol = rawSymbol.trim().toUpperCase()
    if (!normalizedSymbol) {
      return
    }
    const existing = watchlistMap.get(normalizedSymbol)
    if (existing) {
      openEditHolding(existing)
      return
    }
    const boardItem = priorityBoardItems.find((item) => item.symbol.toUpperCase() === normalizedSymbol)
    if (boardItem) {
      setHoldingEditor({
        mode: "buy",
        seed: createSeedFromLowBuyItem(boardItem)
      })
      return
    }
    try {
      const result = await appApi.searchInstruments(normalizedSymbol, "all")
      const instrument = result.items.find((item) => item.symbol.toUpperCase() === normalizedSymbol) ?? result.items[0]
      setHoldingEditor({
        mode: "create",
        seed: {
          symbol: instrument?.symbol ?? normalizedSymbol,
          name: instrument?.name ?? normalizedSymbol,
          base_position: 100,
          available_position: 0,
          cost_basis: findLatestPrice(instrument?.symbol ?? normalizedSymbol),
          memo: "App 搜索补录"
        }
      })
    } catch {
      setHoldingEditor({
        mode: "create",
        seed: {
          symbol: normalizedSymbol,
          name: normalizedSymbol,
          base_position: 100,
          available_position: 0,
          cost_basis: findLatestPrice(normalizedSymbol),
          memo: "App 搜索补录"
        }
      })
    }
  }

  function openEditHolding(item: WatchlistItem) {
    setHoldingEditor({
      mode: "edit",
      seed: createSeedFromWatchlist(item)
    })
  }

  function openBoughtEditor(item: MobileLowBuyCardItem) {
    setHoldingEditor({
      mode: watchlistMap.has(item.symbol) ? "edit" : "buy",
      seed: createSeedFromLowBuyItem(item, watchlistMap.get(item.symbol))
    })
  }

  function openPriorityAction(symbol: string) {
    const item = priorityBoardItems.find((candidate) => candidate.symbol === symbol) ?? null
    if (item) {
      setPriorityActionItem(item)
      return
    }
    void openCandidate(symbol)
  }

  function openDetailHoldingEditor() {
    if (!detail) {
      return
    }
    setHoldingEditor({
      mode: watchlistMap.has(detail.candidate.symbol) ? "edit" : "buy",
      seed: createSeedFromDetail(
        detail.candidate.symbol,
        detail.candidate.name,
        detail.candidate.latest_price,
        watchlistMap.get(detail.candidate.symbol)
      )
    })
    setDetail(null)
  }

  async function handleSubmitHolding(payload: Omit<WatchlistItem, "created_at">) {
    const mode = holdingEditor?.mode ?? "edit"
    const success = await saveHolding(
      payload,
      mode === "buy" ? `${payload.symbol} 已入持仓` : "持仓已更新"
    )
    if (success) {
      setHoldingEditor(null)
    }
  }

  async function handleRemoveHolding(item: WatchlistItem) {
    const success = await removeWatchItem(item.symbol)
    if (success) {
      setHoldingEditor(null)
    }
  }

  function handleSwitchTab(nextTab: MobileTab) {
    setHoldingEditor(null)
    setDetail(null)
    setPriorityActionItem(null)
    setAccountMenuOpen(false)
    sectorSettings.closeSectorSettings()
    hideSignalToast()
    setActiveTab(nextTab)
    setPreviewTab("home")
  }

  const isDetailInWatchlist = detail ? watchlistMap.has(detail.candidate.symbol) : false

  async function handlePullRefresh() {
    if (activeTab === "low_buy") {
      await loadMobilePlaybook(strategyFilter, true)
      return
    }
    await refreshActiveTab()
  }

  if (!authUser) {
    return (
      <MobileAuthScreen
        loading={authLoading}
        error={authError}
        onSubmit={handleAuthSubmit}
      />
    )
  }

  return (
    <div className="mobile-app-shell">
      <MobileAppHeader
        activeTab={activeTab}
        pulseTime={pulseTime}
        user={authUser}
        accountMenuOpen={accountMenuOpen}
        onRefreshHome={() => void refreshActiveTab()}
        onRefreshHoldings={() => void refreshActiveTab()}
        onRefreshLowBuy={() => void loadMobilePlaybook(strategyFilter, true)}
        onToggleAccountMenu={() => setAccountMenuOpen((value) => !value)}
        onOpenPreferences={() => {
          setAccountMenuOpen(false)
          void sectorSettings.openSectorSettings()
        }}
        onLogout={() => void handleLogout()}
      />

      <MobileStatusBanners
        activeTab={activeTab}
        signalToastVisible={signalToastVisible}
        offline={offline}
        message={message}
        error={error}
        playbookError={playbookError}
      />

      <main className="mobile-app-body">
        <PullToRefresh onRefresh={handlePullRefresh}>
          <MobileTabContent
            activeTab={activeTab}
            home={{
              metrics: monitorMetrics,
              priorityBoard,
              priorityBoardItems,
              priorityPulseTime,
              todayActionTitle: home?.today_action_title ?? "",
              todayActionNote: home?.today_action_note ?? "",
              watchlistMap,
              loading,
              onOpenCandidate: openPriorityAction,
              onSwitchToLowBuy: () => handleSwitchTab("low_buy"),
            }}
            holdings={{
              metrics: holdingsMetrics,
              holdingRows,
              activeHoldingSignalSymbols,
              loading,
              onCreateHolding: openCreateHolding,
              onSearchHolding: openSearchHolding,
              onEditHolding: openEditHolding,
              onRemoveHolding: handleRemoveHolding,
            }}
            lowBuy={{
              strategyFilter,
              strategyTabs,
              metrics: lowBuyMetrics,
              playbookItems,
              playbookGroups,
              watchlistMap,
              loading,
              playbookLoading,
              onStrategyChange: setStrategyFilter,
              onOpenAi: () => setAiOpen(true),
              onOpenCandidate: openCandidate,
              onBought: openBoughtEditor,
            }}
          />
        </PullToRefresh>
      </main>

      <MobileTabBar activeTab={activeTab} onSwitchTab={handleSwitchTab} />

      <LowBuyDetailSheet
        detail={detail}
        inWatchlist={isDetailInWatchlist}
        onClose={() => setDetail(null)}
        onMarkBought={openDetailHoldingEditor}
      />

      <HoldingEditorSheet
        open={Boolean(holdingEditor)}
        seed={holdingEditor?.seed ?? EMPTY_HOLDING_SEED}
        mode={holdingEditor?.mode ?? "create"}
        saving={actionLoading}
        onClose={() => setHoldingEditor(null)}
        onSubmit={handleSubmitHolding}
      />

      <PriorityActionSheet
        item={priorityActionItem}
        onClose={() => setPriorityActionItem(null)}
        onOpenDetail={openCandidate}
        onMarkBought={openBoughtEditor}
      />

      <AppUpdateSheet
        updateInfo={appUpdate.updateInfo}
        updateError={appUpdate.updateError}
        verifying={appUpdate.verifying}
        onClose={appUpdate.dismissUpdate}
        onUpdate={appUpdate.openUpdate}
      />

      <AiDecisionSheet
        open={aiOpen}
        board={priorityBoard}
        onClose={() => setAiOpen(false)}
      />

      <MobileSectorSettingsSheet
        open={sectorSettings.open}
        availableSectors={sectorSettings.availableSectors}
        excludedSectors={sectorSettings.excludedSectors}
        saving={sectorSettings.saving}
        onClose={sectorSettings.closeSectorSettings}
        onSave={sectorSettings.saveSectorSettings}
      />
    </div>
  )
}
