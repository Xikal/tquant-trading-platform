import type {
  PaperAccount,
  PaperGroupedPerformance,
  PaperLedgerRepairResponse,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperAgentRun,
  PaperAutoTradingStatus,
  PaperSectorEtfT0Performance,
  PaperStockPnlItem,
  PaperStockPnlSummary,
  PaperTagPerformance,
  PaperTrade,
  PaperTradeTag,
  RiskEventItem,
} from "../../types";
import { memo, useEffect, useMemo } from "react";
import { Col, Row, Space } from "antd";
import { PixelTraderWorker } from "./PixelTraderWorker";
import { PaperDetailTabs } from "./PaperDetailTabs";
import { PaperTodayActionPanel } from "./PaperTodayActionPanel";
import { PaperTradingSummaryBar } from "./PaperTradingSummaryBar";
import {
  formatPaperDateTime,
  OrderEntryModal,
  PaperPositionsPanel,
} from "./PaperTradingSections";
import type { PaperOrderDraft } from "../workspace-shared/workspaceTypes";
import { usePaperUiStore } from "../../stores/paperUiStore";

export interface PaperTradingPageProps {
  account: PaperAccount | null;
  positions: PaperPosition[];
  orders: PaperOrder[];
  trades: PaperTrade[];
  stockPnl?: PaperStockPnlItem[];
  stockPnlSummary?: PaperStockPnlSummary | null;
  performance: PaperPerformance | null;
  sectorEtfT0Performance?: PaperSectorEtfT0Performance | null;
  strategyPerformance: PaperGroupedPerformance[];
  marketPerformance: PaperGroupedPerformance[];
  tagPerformance: PaperTagPerformance[];
  tradeTags: Record<number, PaperTradeTag[]>;
  riskEvents: RiskEventItem[];
  autoTradingStatus: PaperAutoTradingStatus | null;
  autoTradingRuns: PaperAgentRun[];
  ledgerRepairStatus?: PaperLedgerRepairResponse | null;
  canManageReconcile?: boolean;
  draft: PaperOrderDraft;
  setDraft: (draft: PaperOrderDraft) => void;
  loading: string;
  onRefreshLedgerRepair?: () => void | Promise<void>;
  onApplyLedgerRepair?: () => void | Promise<void>;
  onSubmitOrder: () => void | Promise<void>;
  onTogglePause: () => void | Promise<void>;
  onAddTradeTag: (tradeId: number, tag: string) => void;
  onDeleteTradeTag: (tradeId: number, tagId: number) => void;
}

export const PaperTradingPage = memo(function PaperTradingPage({
  account,
  positions,
  orders,
  trades,
  stockPnl = [],
  stockPnlSummary = null,
  performance,
  sectorEtfT0Performance = null,
  strategyPerformance,
  marketPerformance,
  tagPerformance,
  tradeTags,
  riskEvents,
  autoTradingStatus,
  autoTradingRuns,
  ledgerRepairStatus = null,
  canManageReconcile = false,
  draft,
  setDraft,
  loading,
  onRefreshLedgerRepair,
  onApplyLedgerRepair,
  onSubmitOrder,
  onTogglePause,
  onAddTradeTag,
  onDeleteTradeTag,
}: PaperTradingPageProps) {
  const autoManaged = Boolean(autoTradingStatus?.engine_running || autoTradingStatus?.trading_time);
  const paused = account?.status === "paused" && !autoManaged;
  const paperLoading = loading === "paper";
  const orderLoading = loading === "paper-order";
  const autoTradingRunning = Boolean(autoTradingStatus?.running);
  const clockMs = usePaperUiStore((state) => state.clockMs);
  const setClockMs = usePaperUiStore((state) => state.setClockMs);
  const orderModalOpen = usePaperUiStore((state) => state.orderModalOpen);
  const setOrderModalOpen = usePaperUiStore((state) => state.setOrderModalOpen);
  const cockpitMarketState = useMemo(() => (
    resolveCockpitMarketState(autoTradingStatus, clockMs)
  ), [autoTradingStatus, clockMs]);
  const cockpitRecentTrades = useMemo(() => (
    trades.slice(0, 3).map((item) => ({
      type: item.side === "sell" ? "sell" as const : "buy" as const,
      symbol: item.symbol,
      name: item.symbol,
      time: formatPaperDateTime(item.trade_time).slice(11, 16),
    }))
  ), [trades]);
  const lastOrderAction = useMemo(() => {
    const latestTrade = trades[0];
    if (!latestTrade) return null;
    const timestamp = latestTrade.trade_time;
    return {
      type: latestTrade.side === "sell" ? "sell" as const : "buy" as const,
      symbol: latestTrade.symbol,
      timestamp: Date.parse(timestamp),
    };
  }, [trades]);

  useEffect(() => {
    const timer = window.setInterval(() => setClockMs(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  async function submitOrderFromModal() {
    await Promise.resolve(onSubmitOrder());
    setOrderModalOpen(false);
  }

  return (
    <Space orientation="vertical" size={12} style={{ display: "flex", width: "100%" }}>
      <PaperTradingSummaryBar
        account={account}
        performance={performance}
        autoTradingStatus={autoTradingStatus}
        loading={paperLoading || orderLoading}
        canOpenOrder={!paused && !autoTradingRunning}
        onOpenOrderEntry={() => setOrderModalOpen(true)}
        onTogglePause={onTogglePause}
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
      <Row gutter={[12, 12]} align="top" style={{ marginInline: 0 }}>
        <Col xs={24} xl={15}>
          <PaperPositionsPanel
            positions={positions}
            loading={paperLoading}
          />
        </Col>
        <Col xs={24} xl={9}>
          <Space orientation="vertical" size={12} style={{ display: "flex" }}>
            <PixelTraderWorker
              marketState={cockpitMarketState}
              paused={paused}
              autoTradingRunning={autoTradingRunning}
              lastOrderAction={Number.isFinite(lastOrderAction?.timestamp) ? lastOrderAction : null}
              loading={paperLoading || orderLoading}
              onOpenOrderEntry={() => setOrderModalOpen(true)}
              recentTrades={cockpitRecentTrades}
            />
            <PaperTodayActionPanel
              autoTradingStatus={autoTradingStatus}
              riskEvents={riskEvents}
              autoTradingRuns={autoTradingRuns}
            />
          </Space>
        </Col>
      </Row>
      <PaperDetailTabs
        positions={positions}
        orders={orders}
        trades={trades}
        stockPnl={stockPnl}
        stockPnlSummary={stockPnlSummary}
        performance={performance}
        sectorEtfT0Performance={sectorEtfT0Performance}
        strategyPerformance={strategyPerformance}
        marketPerformance={marketPerformance}
        tagPerformance={tagPerformance}
        tradeTags={tradeTags}
        riskEvents={riskEvents}
        autoTradingRuns={autoTradingRuns}
        ledgerRepairStatus={ledgerRepairStatus}
        canManageReconcile={canManageReconcile}
        loading={paperLoading || loading === "paper-ledger-repair"}
        onRefreshLedgerRepair={onRefreshLedgerRepair}
        onApplyLedgerRepair={onApplyLedgerRepair}
        onAddTradeTag={onAddTradeTag}
        onDeleteTradeTag={onDeleteTradeTag}
      />
    </Space>
  );
});

function resolveCockpitMarketState(
  autoTradingStatus: PaperAutoTradingStatus | null,
  clockMs: number,
) {
  if (autoTradingStatus?.engine_running || autoTradingStatus?.running) return "open";
  if (autoTradingStatus?.trading_time === false) return "closed";
  const now = new Date(clockMs);
  const day = now.getDay();
  if (day === 0 || day === 6) return "closed";
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (minutes >= 570 && minutes < 690) return "open";
  if (minutes >= 690 && minutes < 780) return "lunch_break";
  if (minutes >= 780 && minutes < 900) return "open";
  return "closed";
}
