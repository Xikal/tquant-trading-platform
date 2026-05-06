import type { IntradayConfirmationItem } from "../../types";
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
    priorityCards: monitor.priorityCards,
    watchCards: monitor.watchCards,
    runtime: monitor.runtime,
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
    performance: paper.performance,
    strategyPerformance: paper.strategyPerformance,
    marketPerformance: paper.marketPerformance,
    tagPerformance: paper.tagPerformance,
    tradeTags: paper.tradeTags,
    riskEvents: paper.riskEvents,
    autoTradingStatus: paper.autoTradingStatus,
    autoTradingRuns: paper.autoTradingRuns,
    intradayConfirmations,
    draft: paper.draft,
    setDraft: paper.setDraft,
    loading,
    onSubmitOrder: paper.submitOrder,
    onAddTradeTag: (tradeId, tag) => void paper.addTradeTag(tradeId, tag),
    onDeleteTradeTag: (tradeId, tagId) => void paper.deleteTradeTag(tradeId, tagId),
  };

  return {
    monitorPageProps,
    paperPageProps,
  };
}
