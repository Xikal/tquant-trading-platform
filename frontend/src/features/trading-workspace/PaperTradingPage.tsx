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
import { memo, useMemo, useState } from "react";
import { PaperDetailTabs } from "./PaperDetailTabs";
import { PaperTodayActionPanel } from "./PaperTodayActionPanel";
import { PaperTradingSummaryBar } from "./PaperTradingSummaryBar";
import {
  formatPaperDateTime,
  OrderEntryModal,
  PaperPositionsPanel,
} from "./PaperTradingSections";
import type { PaperOrderDraft } from "./workspaceTypes";

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
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [dismissedConfirmationKey, setDismissedConfirmationKey] = useState("");
  const pendingConfirmation = useMemo(() => (
    intradayConfirmations.find((item) => item.confirmed || item.late_confirmed) ?? intradayConfirmations[0] ?? null
  ), [intradayConfirmations]);
  const pendingConfirmationKey = pendingConfirmation
    ? `${pendingConfirmation.symbol}-${pendingConfirmation.updated_at ?? pendingConfirmation.trade_date}-${pendingConfirmation.confirmed}-${pendingConfirmation.late_confirmed}`
    : "";
  const shouldShowConfirmationDialog = Boolean(
    pendingConfirmation
      && pendingConfirmationKey !== dismissedConfirmationKey
      && !autoTradingStatus?.engine_running
      && !autoTradingRunning
  );

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
      <PaperTodayActionPanel
        autoTradingStatus={autoTradingStatus}
        riskEvents={riskEvents}
        intradayConfirmations={intradayConfirmations}
        autoTradingRuns={autoTradingRuns}
      />
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
          <button type="button" className="primary-button primary" onClick={onConfirm} disabled={disabled || !passed}>
            确认买入
          </button>
          <button type="button" className="ghost-button" onClick={onDismiss}>暂不买</button>
        </div>
      </section>
    </div>
  );
}

function formatPriceValue(value?: number | null): string {
  return typeof value === "number" && Number.isFinite(value) ? `¥${value.toFixed(3)}` : "--";
}
