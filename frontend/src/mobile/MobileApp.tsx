import { startTransition, useState } from "react"
import {
  HoldingEditorSheet,
  type HoldingEditorSeed
} from "../features/app-preview/holdingEditor"
import { useAppPreviewData } from "../features/app-preview/hooks"
import type { WatchlistItem } from "../types"
import { MobileAppHeader, MobileStatusBanners, MobileTabBar } from "./MobileAppLayout"
import { MobileAuthScreen } from "./MobileAuthScreen"
import type { MobileLowBuyCardItem } from "./MobileDesignCards"
import { AiDecisionSheet, AppUpdateSheet } from "./MobileSheets"
import { MobileTabContent } from "./MobileTabContent"
import { LowBuyDetailSheet } from "./mobileSections"
import type { MobileTab } from "./mobileTypes"
import { useAppUpdate } from "./useAppUpdate"
import { useMobileAppViewModels } from "./useMobileAppViewModels"
import { useMobileAuth } from "./useMobileAuth"
import { useMobileHoldingSignals } from "./useMobileHoldingSignals"
import { useMobilePaperTrading } from "./useMobilePaperTrading"
import { useMobilePlaybook } from "./useMobilePlaybook"
import { useNativeRuntime } from "./useNativeRuntime"
import {
  createSeedFromDetail,
  createSeedFromLowBuyItem,
  createSeedFromWatchlist
} from "./mobileViewModels"

interface HoldingEditorState {
  mode: "create" | "buy" | "edit"
  seed: HoldingEditorSeed
}

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
    playbook,
    playbookLoading,
    playbookError,
    setStrategyFilter,
    loadMobilePlaybook
  } = useMobilePlaybook(Boolean(authUser) && activeTab === "low_buy")
  const paperTrading = useMobilePaperTrading(Boolean(authUser) && activeTab === "paper")
  const [holdingEditor, setHoldingEditor] = useState<HoldingEditorState | null>(null)
  const [aiOpen, setAiOpen] = useState(false)
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)

  useNativeRuntime(() => {
    startTransition(() => {
      void refreshActiveTab()
      void appUpdate.checkForUpdate()
    })
  })

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
    setAccountMenuOpen(false)
    hideSignalToast()
    setActiveTab(nextTab)
    if (nextTab !== "paper") {
      setPreviewTab("home")
    }
  }

  const isDetailInWatchlist = detail ? watchlistMap.has(detail.candidate.symbol) : false

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
        onRefreshPaper={() => void paperTrading.loadPaper()}
        onRefreshLowBuy={() => void loadMobilePlaybook(strategyFilter, true)}
        onToggleAccountMenu={() => setAccountMenuOpen((value) => !value)}
        onLogout={() => void handleLogout()}
      />

      <MobileStatusBanners
        activeTab={activeTab}
        signalToastVisible={signalToastVisible}
        message={message}
        error={error}
        playbookError={playbookError}
        paperMessage={paperTrading.paperMessage}
        paperError={paperTrading.paperError}
      />

      <main className="mobile-app-body">
        <MobileTabContent
          activeTab={activeTab}
          home={{
            metrics: monitorMetrics,
            priorityBoard,
            priorityBoardItems,
            priorityPulseTime,
            watchlistMap,
            loading,
            onOpenCandidate: openCandidate,
            onSwitchToLowBuy: () => handleSwitchTab("low_buy"),
          }}
          holdings={{
            metrics: holdingsMetrics,
            holdingRows,
            activeHoldingSignalSymbols,
            loading,
            onCreateHolding: openCreateHolding,
            onEditHolding: openEditHolding,
            onRemoveHolding: handleRemoveHolding,
          }}
          lowBuy={{
            strategyFilter,
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
          paper={{
            account: paperTrading.paperAccount,
            positions: paperTrading.paperPositions,
            orders: paperTrading.paperOrders,
            trades: paperTrading.paperTrades,
            performance: paperTrading.paperPerformance,
            strategyPerformance: paperTrading.paperStrategyPerformance,
            marketPerformance: paperTrading.paperMarketPerformance,
          }}
        />
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

      <AppUpdateSheet
        updateInfo={appUpdate.updateInfo}
        onClose={appUpdate.dismissUpdate}
        onUpdate={appUpdate.openUpdate}
      />

      <AiDecisionSheet
        open={aiOpen}
        board={priorityBoard}
        onClose={() => setAiOpen(false)}
      />
    </div>
  )
}
