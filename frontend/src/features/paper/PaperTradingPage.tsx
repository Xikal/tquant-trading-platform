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
import { memo, useMemo } from "react";
import { Col, Row, Space } from "antd";
import { PaperDetailTabs, reviewReportCount } from "./PaperDetailTabs";
import { HoldingDisciplinePanel } from "./HoldingDisciplinePanel";
import { PaperConclusionBar } from "./PaperConclusionBar";
import { PaperMechaActionPanel } from "./PaperMechaActionPanel";
import { PaperTodayActionPanel } from "./PaperTodayActionPanel";
import { TTradeAttributionPanel } from "./TTradeAttributionPanel";
import { paperAccountNeedsResume } from "./paperTradingStatus";
import { useHoldingDiscipline, useTTradeAttribution } from "./queries";
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
  tradingExperienceFlags?: Record<string, boolean>;
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
  tradingExperienceFlags = {},
}: PaperTradingPageProps) {
  const needsResumeOrder = paperAccountNeedsResume(account, autoTradingStatus);
  const paused = needsResumeOrder;
  const paperLoading = loading === "paper";
  const orderLoading = loading === "paper-order";
  const autoTradingRunning = Boolean(autoTradingStatus?.running);
  const orderModalOpen = usePaperUiStore((state) => state.orderModalOpen);
  const setOrderModalOpen = usePaperUiStore((state) => state.setOrderModalOpen);
  const setDetailGroup = usePaperUiStore((state) => state.setDetailGroup);
  const setDetailTab = usePaperUiStore((state) => state.setDetailTab);
  const flags = tradingExperienceFlags;
  const holdingEnabled = Boolean(flags.trading_experience_suite_enabled && flags.holding_discipline_assistant_enabled);
  const tTradeEnabled = Boolean(flags.trading_experience_suite_enabled && flags.t_trade_discipline_enabled);
  const paperReviewReportCount = reviewReportCount(performanceDashboard);
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

  async function submitOrderFromModal() {
    await Promise.resolve(onSubmitOrder());
    setOrderModalOpen(false);
  }

  function openReviewHistory() {
    setDetailGroup("details");
    setDetailTab("review-history");
  }

  return (
    <Space direction="vertical" size={8} style={PAPER_PAGE_STACK_STYLE}>
      <Row className="paper-hero-grid" gutter={[8, 8]} align="stretch" style={PAPER_ROW_STYLE}>
        <Col xs={24} xl={16} className="paper-hero-grid__left">
          <PaperConclusionBar
            account={account}
            performance={performance}
            autoTradingStatus={autoTradingStatus}
            loading={paperLoading || orderLoading}
            canResumeOrder={needsResumeOrder}
            reviewReportCount={paperReviewReportCount}
            onTogglePause={onTogglePause}
            onOpenReviewHistory={openReviewHistory}
            positions={(
              <PaperPositionsPanel
                positions={positions}
                loading={paperLoading}
                embedded
              />
            )}
          />
        </Col>
        <Col xs={24} xl={8} className="paper-hero-grid__right">
          <div className="paper-side-stack">
            <PaperMechaActionPanel
              autoTradingStatus={autoTradingStatus}
              autoTradingRuns={autoTradingRuns}
              riskEvents={riskEvents}
              paused={paused}
              lastOrderAction={Number.isFinite(lastOrderAction?.timestamp) ? lastOrderAction : null}
              monitor={(
                <PaperTodayActionPanel
                  autoTradingStatus={autoTradingStatus}
                  autoTradingRuns={autoTradingRuns}
                  riskEvents={riskEvents}
                  embedded
                />
              )}
            />
          </div>
        </Col>
      </Row>
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
      {holdingEnabled || tTradeEnabled ? (
        <PaperTradingExperiencePanels accountId={account?.id} holdingEnabled={holdingEnabled} tTradeEnabled={tTradeEnabled} />
      ) : null}
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

function PaperTradingExperiencePanels({
  accountId,
  holdingEnabled,
  tTradeEnabled,
}: {
  accountId?: number | null;
  holdingEnabled: boolean;
  tTradeEnabled: boolean;
}) {
  const holdingQuery = useHoldingDiscipline(accountId, holdingEnabled);
  const tTradeQuery = useTTradeAttribution(accountId, tTradeEnabled);
  return (
    <Row className="paper-main-grid" gutter={[8, 8]} align="stretch" style={PAPER_ROW_STYLE}>
      {holdingEnabled ? (
        <Col xs={24} xl={12}>
          <section className="panel">
            <h3>持仓纪律</h3>
            <HoldingDisciplinePanel data={holdingQuery.data} loading={holdingQuery.isFetching} />
          </section>
        </Col>
      ) : null}
      {tTradeEnabled ? (
        <Col xs={24} xl={12}>
          <section className="panel">
            <h3>T 归因</h3>
            <TTradeAttributionPanel data={tTradeQuery.data} loading={tTradeQuery.isFetching} />
          </section>
        </Col>
      ) : null}
    </Row>
  );
}
