import type {
  IntradayConfirmationItem,
  PaperAccount,
  PaperAgentRun,
  PaperAutoTradingStatus,
  PaperGroupedPerformance,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperSectorEtfT0Performance,
  PaperTagPerformance,
  PaperTrade,
  PaperTradeTag,
  RiskEventItem,
} from "../../types";
import { memo, useMemo, useState } from "react";
import { PixelTraderWorker } from "./PixelTraderWorker";
import {
  formatPaperDateTime,
  OrderEntryModal,
  PaperBottomPanels,
  PaperMetricGrid,
  PaperPositionsPanel,
  resolvePaperMarketState,
} from "./PaperTradingSections";
import type { PaperOrderDraft } from "./workspaceTypes";

export interface PaperTradingPageProps {
  account: PaperAccount | null;
  positions: PaperPosition[];
  orders: PaperOrder[];
  trades: PaperTrade[];
  performance: PaperPerformance | null;
  sectorEtfT0Performance?: PaperSectorEtfT0Performance | null;
  strategyPerformance: PaperGroupedPerformance[];
  marketPerformance: PaperGroupedPerformance[];
  tagPerformance: PaperTagPerformance[];
  tradeTags: Record<number, PaperTradeTag[]>;
  riskEvents: RiskEventItem[];
  autoTradingStatus: PaperAutoTradingStatus | null;
  autoTradingRuns: PaperAgentRun[];
  intradayConfirmations: IntradayConfirmationItem[];
  draft: PaperOrderDraft;
  setDraft: (draft: PaperOrderDraft) => void;
  loading: string;
  onSubmitOrder: () => void | Promise<void>;
  onAddTradeTag: (tradeId: number, tag: string) => void;
  onDeleteTradeTag: (tradeId: number, tagId: number) => void;
}

export const PaperTradingPage = memo(function PaperTradingPage({
  account,
  positions,
  orders,
  trades,
  performance,
  sectorEtfT0Performance = null,
  strategyPerformance,
  marketPerformance,
  tagPerformance,
  tradeTags,
  riskEvents,
  autoTradingStatus,
  autoTradingRuns,
  intradayConfirmations,
  draft,
  setDraft,
  loading,
  onSubmitOrder,
  onAddTradeTag,
  onDeleteTradeTag,
}: PaperTradingPageProps) {
  const autoManaged = Boolean(autoTradingStatus?.engine_running || autoTradingStatus?.trading_time);
  const paused = account?.status === "paused" && !autoManaged;
  const paperLoading = loading === "paper";
  const orderLoading = loading === "paper-order";
  const autoTradingRunning = Boolean(autoTradingStatus?.running);
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [lastOrderAction, setLastOrderAction] = useState<{ type: "buy" | "sell"; symbol: string; timestamp: number } | null>(null);
  const recentTrades = useMemo(() => trades.slice(0, 3).map((item) => ({
    type: item.side,
    symbol: item.symbol,
    name: item.strategy_key,
    time: formatPaperDateTime(item.trade_time).slice(11, 16),
  })), [trades]);
  const marketState = resolvePaperMarketState();

  async function submitOrderFromModal() {
    const action = { type: draft.side, symbol: draft.symbol.trim(), timestamp: Date.now() };
    await Promise.resolve(onSubmitOrder());
    if (action.symbol) {
      setLastOrderAction(action);
    }
    setOrderModalOpen(false);
  }

  return (
    <section className="page-grid paper-grid">
      <PaperMetricGrid account={account} performance={performance} autoTradingStatus={autoTradingStatus} loading={paperLoading} />
      <PixelTraderWorker
        marketState={marketState}
        paused={paused}
        autoTradingRunning={autoTradingRunning}
        lastOrderAction={lastOrderAction}
        loading={orderLoading}
        onOpenOrderEntry={() => setOrderModalOpen(true)}
        recentTrades={recentTrades}
      />
      {orderModalOpen ? (
        <OrderEntryModal
          draft={draft}
          setDraft={setDraft}
          paused={paused}
          autoTradingRunning={autoTradingRunning}
          loading={orderLoading}
          positions={positions}
          onClose={() => setOrderModalOpen(false)}
          onSubmitOrder={submitOrderFromModal}
        />
      ) : null}
      <PaperPositionsPanel
        positions={positions}
        intradayConfirmations={intradayConfirmations}
        loading={paperLoading}
      />
      <PaperBottomPanels
        loading={paperLoading}
        orders={orders}
        trades={trades}
        performance={performance}
        sectorEtfT0Performance={sectorEtfT0Performance}
        strategyPerformance={strategyPerformance}
        marketPerformance={marketPerformance}
        tagPerformance={tagPerformance}
        tradeTags={tradeTags}
        riskEvents={riskEvents}
        autoTradingRuns={autoTradingRuns}
        onAddTradeTag={onAddTradeTag}
        onDeleteTradeTag={onDeleteTradeTag}
      />
    </section>
  );
});
