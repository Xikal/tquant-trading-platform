import type { MonitorPageProps } from "../monitor/MonitorPage";
import type { useAnalysisData } from "./useAnalysisData";
import type { useMonitorData } from "./useMonitorData";
import type { Page, StockCardView, WatchDraft } from "../workspace-shared/workspaceTypes";

interface UseWorkspacePagePropsParams {
  analysis: ReturnType<typeof useAnalysisData>;
  loading: string;
  monitor: ReturnType<typeof useMonitorData>;
  watchDraft: WatchDraft;
  setWatchDraft: (draft: WatchDraft) => void;
  editingWatchSymbol: string;
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
  loading,
  monitor,
  watchDraft,
  setWatchDraft,
  editingWatchSymbol,
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
    marketPulse: monitor.marketPulse,
    hourlySnapshotHistory: monitor.hourlySnapshotHistory,
    reviewStatus: monitor.reviewStatus,
    reviewReports: monitor.reviewReports,
    keyLevelAlerts: monitor.keyLevelAlerts,
    sectorEtfT0: monitor.sectorEtfT0,
    sectorRelativeStrength: monitor.sectorRelativeStrength,
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
    onLaneChange: (strategyVariant) => void monitor.loadPriorityLane(strategyVariant),
    onSelect: onSelectStock,
    onAnalyze: analysis.analyzeFromCard,
    onEdit: onEditWatchlist,
    onRemove: onRemoveWatchlist,
    onAddWatchlist,
    onCancelEdit: onCancelWatchlistEdit,
  };

  return {
    monitorPageProps,
  };
}
