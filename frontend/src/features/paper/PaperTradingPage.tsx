import type {
  IntradayConfirmationItem,
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
import { memo, useEffect, useMemo, useState } from "react";
import { Button } from "antd";
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
  intradayConfirmations: IntradayConfirmationItem[];
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
  intradayConfirmations,
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
  const [clockMs, setClockMs] = useState(() => Date.now());
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [dismissedConfirmationKey, setDismissedConfirmationKey] = useState("");
  const pendingConfirmation = useMemo(() => (
    intradayConfirmations.find((item) => item.confirmed || item.late_confirmed) ?? intradayConfirmations[0] ?? null
  ), [intradayConfirmations]);
  const pendingConfirmationKey = pendingConfirmation
    ? `${pendingConfirmation.symbol}-${pendingConfirmation.updated_at ?? pendingConfirmation.trade_date}-${pendingConfirmation.confirmed}-${pendingConfirmation.late_confirmed}`
    : "";
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
  const shouldShowConfirmationDialog = Boolean(
    pendingConfirmation
      && pendingConfirmationKey !== dismissedConfirmationKey
      && !autoTradingStatus?.engine_running
      && !autoTradingRunning
  );

  useEffect(() => {
    const timer = window.setInterval(() => setClockMs(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  async function submitOrderFromModal() {
    await Promise.resolve(onSubmitOrder());
    setOrderModalOpen(false);
  }

  function confirmIntradayBuy(item: IntradayConfirmationItem) {
    setDraft({
      ...draft,
      symbol: item.symbol,
      name: item.name || draft.name,
      side: "buy",
      order_type: "limit",
      price: item.latest_price ? String(item.latest_price) : draft.price,
      current_price: item.latest_price ? String(item.latest_price) : draft.current_price,
      reason: item.reason || "分时确认后小仓模拟买入",
      require_intraday_confirmation: false,
    });
    setDismissedConfirmationKey(pendingConfirmationKey);
    setOrderModalOpen(true);
  }

  return (
    <section className="page-grid paper-grid">
      {shouldShowConfirmationDialog && pendingConfirmation ? (
        <IntradayConfirmationDialog
          item={pendingConfirmation}
          disabled={paused || autoTradingRunning}
          onConfirm={() => confirmIntradayBuy(pendingConfirmation)}
          onDismiss={() => setDismissedConfirmationKey(pendingConfirmationKey)}
        />
      ) : null}
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
      <PaperPositionsPanel
        positions={positions}
        loading={paperLoading}
      />
      <div className="paper-right-column">
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
          intradayConfirmations={intradayConfirmations}
          autoTradingRuns={autoTradingRuns}
        />
      </div>
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
    </section>
  );
});

function IntradayConfirmationDialog({
  item,
  disabled,
  onConfirm,
  onDismiss,
}: {
  item: IntradayConfirmationItem;
  disabled: boolean;
  onConfirm: () => void;
  onDismiss: () => void;
}) {
  const passed = item.confirmed || item.late_confirmed;
  return (
    <div className="paper-confirmation-backdrop" role="presentation">
      <section className={`paper-confirmation-card ${passed ? "ok" : "watch"}`} role="dialog" aria-modal="false" aria-label="盘中确认提醒">
        <span>{passed ? "盘中确认已通过" : "盘中确认待观察"}</span>
        <strong>{item.name || item.symbol} {passed ? "可以进入委托确认" : "暂不自动下单"}</strong>
        <p>
          参考价 {formatPriceValue(item.latest_price)}，VWAP {formatPriceValue(item.vwap)}，
          分数 {Number.isFinite(item.score) ? item.score.toFixed(0) : "--"}。
        </p>
        <small>{item.reason || "系统正在等待分时承接确认。"}</small>
        <div>
          <Button type="primary" onClick={onConfirm} disabled={disabled || !passed}>
            确认买入
          </Button>
          <Button type="default" onClick={onDismiss}>暂不买</Button>
        </div>
      </section>
    </div>
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

function formatPriceValue(value?: number | null): string {
  return typeof value === "number" && Number.isFinite(value) ? `¥${value.toFixed(3)}` : "--";
}
