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
  onTogglePause: () => void | Promise<void>;
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
  const [lastOrderAction, setLastOrderAction] = useState<{ type: "buy" | "sell"; symbol: string; timestamp: number } | null>(null);
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
      <PaperMetricGrid
        account={account}
        performance={performance}
        autoTradingStatus={autoTradingStatus}
        loading={paperLoading}
        onTogglePause={onTogglePause}
      />
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
      <PaperActionBrief
        autoTradingStatus={autoTradingStatus}
        riskEvents={riskEvents}
        intradayConfirmations={intradayConfirmations}
        autoTradingRuns={autoTradingRuns}
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

function PaperActionBrief({
  autoTradingStatus,
  riskEvents,
  intradayConfirmations,
  autoTradingRuns,
}: {
  autoTradingStatus: PaperAutoTradingStatus | null;
  riskEvents: RiskEventItem[];
  intradayConfirmations: IntradayConfirmationItem[];
  autoTradingRuns: PaperAgentRun[];
}) {
  const latestRun = autoTradingRuns[0];
  const openRisk = riskEvents.find((item) => item.status !== "resolved");
  const confirmation = intradayConfirmations[0];
  return (
    <section className="panel paper-action-brief">
      <div className="panel-title">
        <h2>系统今日动作日志</h2>
        <span className="hint">{autoTradingStatus?.running ? "自动交易中" : "等待交易时段"}</span>
      </div>
      <div className="paper-action-brief-grid">
        <div className="paper-action-card">
          <span>最近执行</span>
          <strong>{autoTradingStatus?.last_cycle_summary || latestRun?.status || "暂无执行记录"}</strong>
          <small>{autoTradingStatus?.last_cycle_at ? formatPaperDateTime(autoTradingStatus.last_cycle_at) : "交易时间会自动刷新并执行"}</small>
        </div>
        <div className={`paper-action-card ${openRisk ? "warn" : "ok"}`}>
          <span>需要您处理</span>
          <strong>{openRisk ? openRisk.message : "暂无未处理风险"}</strong>
          <small>{openRisk ? `${openRisk.symbol || "账户"} · ${openRisk.severity}` : "触发熔断、止损或异常时会在这里显示"}</small>
        </div>
        <div className="paper-action-card">
          <span>分时确认</span>
          <strong>{confirmation ? `${confirmation.symbol} ${confirmation.confirmed || confirmation.late_confirmed ? "已确认" : "等待确认"}` : "暂无待确认标的"}</strong>
          <small>{confirmation ? confirmation.reason : "需要分时承接时，系统会先确认再模拟下单"}</small>
        </div>
      </div>
    </section>
  );
}
