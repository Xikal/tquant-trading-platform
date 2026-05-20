import type { AuthUser, IntradayConfirmationItem } from "../../types";
import type { MonitorPageProps } from "./MonitorPage";
import type { PaperTradingPageProps } from "./PaperTradingPage";
import type { useAnalysisData } from "./useAnalysisData";
import type { useMonitorData } from "./useMonitorData";
import type { usePaperTrading } from "./usePaperTrading";
import type { Page, StockCardView, WatchDraft } from "./workspaceTypes";

interface UseWorkspacePagePropsParams {
  analysis: ReturnType<typeof useAnalysisData>;
  intradayConfirmations: IntradayConfirmationItem[];
  loading: string;
  monitor: ReturnType<typeof useMonitorData>;
  paper: ReturnType<typeof usePaperTrading>;
  watchDraft: WatchDraft;
  setWatchDraft: (draft: WatchDraft) => void;
  editingWatchSymbol: string;
  currentUser: AuthUser | null;
  onAddWatchlist: () => void;
  onEditWatchlist: (card: StockCardView) => void;
  onNavigatePage: (page: Page) => void;
  onRefreshMonitor: () => void;
  onRemoveWatchlist: (symbol: string) => void;
  onCancelWatchlistEdit: () => void;
  onRunPriorityAi: () => void;
  onSelectStock: (stock: StockCardView | null) => void;
}

export function useWorkspacePageProps({
  analysis,
  intradayConfirmations,
  loading,
  monitor,
  paper,
  watchDraft,
  setWatchDraft,
  editingWatchSymbol,
  currentUser,
  onAddWatchlist,
  onEditWatchlist,
  onNavigatePage,
  onRefreshMonitor,
  onRemoveWatchlist,
  onCancelWatchlistEdit,
  onRunPriorityAi,
  onSelectStock,
}: UseWorkspacePagePropsParams) {
  const monitorPageProps: MonitorPageProps = {
    priorityBoard: monitor.priorityBoard,
    marketBreadth: monitor.marketBreadth,
    sectorRelativeStrength: monitor.sectorRelativeStrength,
    keyLevelAlerts: monitor.keyLevelAlerts,
    sectorEtfT0: monitor.sectorEtfT0,
    pairedHedge: monitor.pairedHedge,
    priorityCards: monitor.priorityCards,
    watchCards: monitor.watchCards,
    runtime: monitor.runtime,
    instrumentSyncStatus: monitor.instrumentSyncStatus,
    watchDraft,
    setWatchDraft,
    editingWatchSymbol,
    loading,
    onRefresh: onRefreshMonitor,
    onSync: () => void monitor.syncInstruments(),
    onAi: onRunPriorityAi,
    onGoPlaybook: () => onNavigatePage("playbook"),
    onSelect: onSelectStock,
    onAnalyze: analysis.analyzeFromCard,
    onEdit: onEditWatchlist,
    onRemove: onRemoveWatchlist,
    onAddWatchlist,
    onCancelEdit: onCancelWatchlistEdit,
  };

  const paperPageProps: PaperTradingPageProps = {
    account: paper.account,
    positions: paper.positions,
    orders: paper.orders,
    trades: paper.trades,
    stockPnl: paper.stockPnl,
    stockPnlSummary: paper.stockPnlSummary,
    performance: paper.performance,
    sectorEtfT0Performance: paper.sectorEtfT0Performance,
    strategyPerformance: paper.strategyPerformance,
    marketPerformance: paper.marketPerformance,
    tagPerformance: paper.tagPerformance,
    tradeTags: paper.tradeTags,
    riskEvents: paper.riskEvents,
    autoTradingStatus: paper.autoTradingStatus,
    autoTradingRuns: paper.autoTradingRuns,
    ledgerRepairStatus: paper.ledgerRepairStatus,
    canManageReconcile: currentUser?.roles.some((role) => {
      const normalized = role.trim().toLowerCase();
      return normalized === "admin" || normalized === "administrator";
    }) ?? false,
    intradayConfirmations,
    draft: paper.draft,
    setDraft: paper.setDraft,
    loading,
    onRefreshLedgerRepair: () => void paper.refreshLedgerRepairStatus(),
    onApplyLedgerRepair: () => void paper.applyLedgerRepair(),
    onSubmitOrder: paper.submitOrder,
    onTogglePause: paper.togglePause,
    onAddTradeTag: (tradeId, tag) => void paper.addTradeTag(tradeId, tag),
    onDeleteTradeTag: (tradeId, tagId) => void paper.deleteTradeTag(tradeId, tagId),
  };

  return {
    monitorPageProps,
    paperPageProps,
  };
}
