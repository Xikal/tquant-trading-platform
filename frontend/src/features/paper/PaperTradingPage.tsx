import type {
  PaperAccount,
  PaperGroupedPerformance,
  PaperLedgerRepairResponse,
  PaperOrder,
  PaperPerformance,
  PaperPerformanceDashboard,
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
import type { CSSProperties } from "react";
import { memo, useEffect, useMemo } from "react";
import { Card, Col, Row, Space } from "antd";
import { PixelTraderAvatar } from "./PixelTraderWorker";
import { PaperDetailTabs } from "./PaperDetailTabs";
import { PaperConclusionBar } from "./PaperConclusionBar";
import { PaperTodayActionPanel } from "./PaperTodayActionPanel";
import { paperAccountNeedsResume } from "./paperTradingStatus";
import {
  OrderEntryModal,
  PaperPositionsPanel,
} from "./PaperTradingSections";
import type { PaperOrderDraft } from "../workspace-shared/workspaceTypes";
import { usePaperUiStore } from "../../stores/paperUiStore";

const PAPER_PAGE_STACK_STYLE: CSSProperties = {
  display: "flex",
  fontSize: 12,
  lineHeight: 1.32,
  maxWidth: "100%",
  minWidth: 0,
  overflowX: "hidden",
  width: "100%",
};
const PAPER_ROW_STYLE: CSSProperties = {
  marginLeft: 0,
  marginInline: 0,
  marginRight: 0,
  maxWidth: "100%",
  minWidth: 0,
  overflowX: "hidden",
};
const PAPER_SIDE_STACK_STYLE: CSSProperties = {
  display: "flex",
  fontSize: 12,
};

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
  performanceDashboard?: PaperPerformanceDashboard | null;
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
  performanceDashboard = null,
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
  const needsResumeOrder = paperAccountNeedsResume(account, autoTradingStatus);
  const paused = needsResumeOrder;
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
    <Space direction="vertical" size={8} style={PAPER_PAGE_STACK_STYLE}>
      <PaperConclusionBar
        account={account}
        performance={performance}
        autoTradingStatus={autoTradingStatus}
        loading={paperLoading || orderLoading}
        canResumeOrder={needsResumeOrder}
        pixel={(
          <PixelTraderAvatar
            marketState={cockpitMarketState}
            paused={paused}
            autoTradingRunning={autoTradingRunning}
            lastOrderAction={Number.isFinite(lastOrderAction?.timestamp) ? lastOrderAction : null}
          />
        )}
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
      <Row className="paper-main-grid" gutter={[8, 8]} align="top" style={PAPER_ROW_STYLE}>
        <Col xs={24}>
          <Card size="small" title="主区：持仓与今日动作" styles={{ body: { display: "none" } }} />
        </Col>
        <Col xs={24} xl={15}>
          <PaperPositionsPanel
            positions={positions}
            loading={paperLoading}
          />
        </Col>
        <Col xs={24} xl={9}>
          <Space direction="vertical" size={8} style={PAPER_SIDE_STACK_STYLE}>
            <Card size="small" title="今日动作 / 自动交易状态">
              <PaperTodayActionPanel
                autoTradingStatus={autoTradingStatus}
                autoTradingRuns={autoTradingRuns}
                riskEvents={riskEvents}
              />
            </Card>
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
        performanceDashboard={performanceDashboard}
        autoTradingStatus={autoTradingStatus}
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
