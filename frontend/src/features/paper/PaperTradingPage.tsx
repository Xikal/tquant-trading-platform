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
import { Card, Col, Collapse, Row, Space, Typography } from "antd";
import { PixelTraderWorker } from "./PixelTraderWorker";
import { PaperDetailTabs } from "./PaperDetailTabs";
import { PaperTradingSummaryBar } from "./PaperTradingSummaryBar";
import {
  formatPaperDateTime,
  OrderEntryModal,
  PaperPositionsPanel,
} from "./PaperTradingSections";
import type { PaperOrderDraft } from "../workspace-shared/workspaceTypes";
import { usePaperUiStore } from "../../stores/paperUiStore";

const PAPER_PAGE_STACK_STYLE: CSSProperties = {
  display: "flex",
  fontSize: 11,
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
  fontSize: 11,
};
const PAPER_REVIEW_SUMMARY_BODY_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  padding: 10,
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
    <Space direction="vertical" size={8} style={PAPER_PAGE_STACK_STYLE}>
      <PaperTradingSummaryBar
        account={account}
        performance={performance}
        autoTradingStatus={autoTradingStatus}
        loading={paperLoading || orderLoading}
        canOpenOrder={!paused && !autoTradingRunning}
        onOpenOrderEntry={() => setOrderModalOpen(true)}
        onTogglePause={onTogglePause}
      />
      <PaperReviewOverview dashboard={performanceDashboard} />
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
      <Row gutter={[8, 8]} align="top" style={PAPER_ROW_STYLE}>
        <Col xs={24} xl={15}>
          <PaperPositionsPanel
            positions={positions}
            loading={paperLoading}
          />
        </Col>
        <Col xs={24} xl={9}>
          <Space direction="vertical" size={8} style={PAPER_SIDE_STACK_STYLE}>
            <PixelTraderWorker
              marketState={cockpitMarketState}
              paused={paused}
              autoTradingRunning={autoTradingRunning}
              lastOrderAction={Number.isFinite(lastOrderAction?.timestamp) ? lastOrderAction : null}
              loading={paperLoading || orderLoading}
              onOpenOrderEntry={() => setOrderModalOpen(true)}
              recentTrades={cockpitRecentTrades}
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

function PaperReviewOverview({ dashboard }: { dashboard: PaperPerformanceDashboard | null }) {
  if (!dashboard) {
    return null;
  }
  const reports = dashboard.review_reports ?? [];
  return (
    <Row gutter={[12, 12]} align="stretch" style={PAPER_ROW_STYLE}>
      <Col xs={24}>
        <Collapse
          size="small"
          items={[{
            key: "review-history",
            label: `复盘历史入口 · ${reports.length} 条`,
            children: (
              <Card
                size="small"
                extra={<Typography.Text type="secondary">{dashboard.updated_at || "--"}</Typography.Text>}
                styles={{ body: PAPER_REVIEW_SUMMARY_BODY_STYLE }}
              >
                <Typography.Text type="secondary">全市场复盘主入口在实时监控页。</Typography.Text>
              </Card>
            ),
          }]}
        />
      </Col>
    </Row>
  );
}

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
