import type {
  IntradayConfirmationItem,
  PaperAccount,
  PaperAgentRun,
  PaperAutoTradingStatus,
  PaperGroupedPerformance,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
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
  const paused = account?.status === "paused";
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
      <PaperMetricGrid account={account} performance={performance} loading={paperLoading} />
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
