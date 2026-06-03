import { memo, useCallback, useMemo } from "react";
import { Button, Grid, Space } from "antd";
import { useShallow } from "zustand/react/shallow";
import type {
  IntradayKeyLevelResponse,
  IntradayMarketPulse,
  LowBuyPriorityBoardResult,
  MarketBreadth,
  MarketHourlySnapshotHistoryItem,
  MarketReviewReport,
  MarketReviewStatus,
  PairedHedgeResearchResponse,
  SectorRelativeStrengthResponse,
  RuntimeStatus,
  SectorEtfT0Response,
  StrategyVariant,
} from "../../types";
import type { InstrumentSyncStatus } from "../../types";
import {
  buildPriorityEmptyText,
  buildPriorityNotice,
  dataQualityTone,
  resolveTodayAction,
} from "./MonitorPage.helpers";
import {
  KeyLevelAlerts,
  MonitorPriorityStockCard,
  MonitorWatchStockCard,
} from "./MonitorPage.panels";
import { MarketStateGatePanel } from "./MarketStateGatePanel";
import { RiskFilterBadges } from "./RiskFilterBadges";
import { SectorLeaderGatePanel } from "./SectorLeaderGatePanel";
import { Callout, ContextRow, EmptyState, FamilyStrip, InfoPill, PanelTitle } from "../workspace-shared/WorkspaceComponents";
import { formatPct, riskLevelText, shortTime } from "../workspace-shared/workspaceFormatters";
import type { StockCardView, WatchDraft } from "../workspace-shared/workspaceTypes";
import {
  MONITOR_INPUT_STYLE,
  MONITOR_PRIORITY_STYLE,
  MONITOR_SUMMARY_STYLE,
  monitorGridStyle,
} from "../trading-workspace/workspaceShellStyles";
import { StrategyLaneStatusCard } from "../low-buy/StrategyLaneStatusCard";
import { StrategyLaneTabs } from "../low-buy/StrategyLaneTabs";
import { useWorkspaceMonitorStore } from "../../stores/workspaceMonitorStore";
import { VirtualCardList } from "../../ui/list/VirtualCardList";
import { MonitorConclusionBar } from "./MonitorConclusionBar";
import { HoldingEntryDrawer } from "./HoldingEntryDrawer";
import { MonitorMoreTabs } from "./MonitorMoreTabs";
import { KeyLevelPanel } from "../key-levels/KeyLevelPanel";
import { useMarketKeyLevels, useStockKeyLevels } from "../key-levels/queries";
import { VolumePositionTagStrip } from "../trading-experience/VolumePositionTagStrip";
import { useTradingExperienceReadiness, useVolumePositionTags } from "../strategy-tracking/queries";

export interface MonitorPageProps {
  priorityBoard: LowBuyPriorityBoardResult | null;
  marketBreadth: MarketBreadth | null;
  marketPulse: IntradayMarketPulse | null;
  hourlySnapshotHistory: MarketHourlySnapshotHistoryItem[];
  reviewStatus: MarketReviewStatus | null;
  reviewReports: MarketReviewReport[];
  keyLevelAlerts: IntradayKeyLevelResponse[];
  sectorEtfT0: SectorEtfT0Response | null;
  sectorRelativeStrength?: SectorRelativeStrengthResponse | null;
  pairedHedge: PairedHedgeResearchResponse | null;
  priorityCards: StockCardView[];
  watchCards: StockCardView[];
  runtime: RuntimeStatus | null;
  instrumentSyncStatus: InstrumentSyncStatus | null;
  watchDraft: WatchDraft;
  setWatchDraft: (draft: WatchDraft) => void;
  editingWatchSymbol: string;
  loading: string;
  onRefresh: () => void;
  onSync: () => void;
  onAi: () => void;
  onGoPlaybook: () => void;
  onLaneChange?: (strategyVariant: StrategyVariant) => void;
  onSelect: (stock: StockCardView) => void;
  onAnalyze: (stock: StockCardView) => void;
  onEdit: (stock: StockCardView) => void;
  onRemove: (symbol: string) => void;
  onAddWatchlist: () => void;
  onCancelEdit: () => void;
}

export const MonitorPage = memo(function MonitorPage({
  priorityBoard,
  marketBreadth,
  marketPulse,
  hourlySnapshotHistory,
  reviewStatus,
  reviewReports,
  keyLevelAlerts,
  sectorEtfT0,
  sectorRelativeStrength = null,
  pairedHedge,
  priorityCards,
  watchCards,
  runtime,
  instrumentSyncStatus,
  watchDraft,
  setWatchDraft,
  editingWatchSymbol,
  loading,
  onRefresh,
  onSync,
  onAi,
  onGoPlaybook,
  onLaneChange,
  onSelect,
  onAnalyze,
  onEdit,
  onRemove,
  onAddWatchlist,
  onCancelEdit,
}: MonitorPageProps) {
  const {
    activeLane,
    holdingDrawerOpen,
    moreTab,
    setActiveLane,
    setHoldingDrawerOpen,
    setMoreTab,
  } = useWorkspaceMonitorStore(useShallow((state) => ({
    activeLane: state.activeStrategyLane,
    holdingDrawerOpen: state.holdingDrawerOpen,
    moreTab: state.moreTab,
    setActiveLane: state.setActiveStrategyLane,
    setHoldingDrawerOpen: state.setHoldingDrawerOpen,
    setMoreTab: state.setMoreTab,
  })));
  const screens = Grid.useBreakpoint();
  const primaryAction = useMemo(() => resolveTodayAction(watchCards, priorityCards, priorityBoard), [watchCards, priorityCards, priorityBoard]);
  const priorityNotice = useMemo(() => buildPriorityNotice(priorityBoard, priorityCards.length), [priorityBoard, priorityCards.length]);
  const wideLayout = screens.xl ?? true;
  const primaryKeyLevelSymbol = priorityCards[0]?.symbol ?? watchCards[0]?.symbol ?? "";
  const marketKeyLevels = useMarketKeyLevels();
  const stockKeyLevels = useStockKeyLevels(primaryKeyLevelSymbol, true);
  const tradingExperienceReadiness = useTradingExperienceReadiness();
  const vpEnabled = Boolean(
    tradingExperienceReadiness.data?.flags?.trading_experience_suite_enabled &&
    tradingExperienceReadiness.data?.flags?.vp_position_tags_enabled,
  );
  const volumeTags = useVolumePositionTags(primaryKeyLevelSymbol, vpEnabled);
  const openHoldingDrawer = useCallback(() => setHoldingDrawerOpen(true), [setHoldingDrawerOpen]);
  const closeHoldingDrawer = useCallback(() => setHoldingDrawerOpen(false), [setHoldingDrawerOpen]);
  const primaryActionClick = primaryAction.source === "holding" ? onRefresh : onGoPlaybook;
  const watchListKey = useCallback((stock: StockCardView) => stock.symbol, []);
  const priorityListKey = useCallback((stock: StockCardView) => `${stock.symbol}-${stock.actionText}`, []);
  const renderWatchCard = useCallback((stock: StockCardView) => (
    <MonitorWatchStockCard
      stock={stock}
      onAnalyze={onAnalyze}
      onEdit={onEdit}
      onRemove={onRemove}
      onSelect={onSelect}
    />
  ), [onAnalyze, onEdit, onRemove, onSelect]);
  const renderPriorityCard = useCallback((stock: StockCardView) => (
    <MonitorPriorityStockCard stock={stock} onAnalyze={onAnalyze} onSelect={onSelect} />
  ), [onAnalyze, onSelect]);
  const handleLaneChange = useCallback((next: StrategyVariant) => {
    setActiveLane(next);
    onLaneChange?.(next);
  }, [onLaneChange, setActiveLane]);
  return (
    <section style={monitorGridStyle(!wideLayout)}>
      <div style={MONITOR_SUMMARY_STYLE}>
        <MonitorConclusionBar
          marketBreadthState={marketBreadth?.state_text ?? null}
          marketPulse={marketPulse}
          priorityBoard={priorityBoard}
          priorityCards={priorityCards}
          reviewStatus={reviewStatus}
          watchCards={watchCards}
          onRefresh={onRefresh}
          onSync={onSync}
        />
        <KeyLevelAlerts alerts={keyLevelAlerts} />
        <div className="monitor-key-level-grid">
          <KeyLevelPanel title="大盘关键位观察" result={marketKeyLevels.data} loading={marketKeyLevels.isFetching} compact={!wideLayout} />
          <KeyLevelPanel
            title="个股关键位观察"
            result={stockKeyLevels.data}
            loading={stockKeyLevels.isFetching}
            compact={!wideLayout}
            extra={<VolumePositionTagStrip items={volumeTags.data?.items ?? []} />}
          />
        </div>
      </div>

      <aside className="panel monitor-holdings" style={MONITOR_INPUT_STYLE}>
        <PanelTitle
          title="我的持仓"
          actions={(
            <>
              <span className="muted">{watchCards.length} 个自选 / {runtime?.database_backend ?? "runtime"} </span>
              <Button type="primary" size="small" onClick={openHoldingDrawer}>+ 录入持仓</Button>
            </>
          )}
        />
        <div className="monitor-holdings__body">
          <Callout
            title={primaryAction.title}
            detail={primaryAction.detail}
            tone={primaryAction.tone}
            compact
            action={(
              <Button type="primary" size="small" onClick={primaryActionClick}>
                {primaryAction.source === "holding" ? "刷新确认" : "查看候选"}
              </Button>
            )}
          />
          <VirtualCardList
            items={watchCards}
            empty={<EmptyState text="暂无自选持仓。点击右上角“录入持仓”后会显示做T信号。" />}
            estimateSize={170}
            maxHeight={620}
            className="monitor-card-list--inset"
            getItemKey={watchListKey}
            renderItem={renderWatchCard}
          />
        </div>
      </aside>

      <div className="panel" style={MONITOR_PRIORITY_STYLE}>
        <PanelTitle
          title={priorityBoard?.display_lane_title || "生产优先榜"}
          actions={
            <>
              <Button className="monitor-gold-action" onClick={onAi} loading={loading === "ai"}>{loading === "ai" ? "解读中..." : "解读榜单"}</Button>
              <Button onClick={onGoPlaybook}>去选股宝典</Button>
            </>
          }
        />
        <Space direction="vertical" size={8} className="monitor-full-action">
          <StrategyLaneTabs value={activeLane} onChange={handleLaneChange} />
          <StrategyLaneStatusCard board={priorityBoard} activeLane={activeLane} />
        </Space>
        <ContextRow>
          <InfoPill compact label="今日方向" value={priorityBoard?.directional_bias_text ?? "--"} />
          <InfoPill compact label="市场状态" value={priorityBoard?.market_state_text ?? "--"} />
          <InfoPill compact label="热点板块" value={(priorityBoard?.hot_industries ?? []).slice(0, 4).join(" / ") || "--"} />
          <InfoPill compact label="宽度情绪" value={`上涨 ${formatPct(priorityBoard?.stock_up_ratio, 0)} / 涨停 ${priorityBoard?.limit_up_count ?? "--"}`} />
          <InfoPill compact label="组合风险" value={priorityBoard?.portfolio_risk?.risk_level ? riskLevelText(priorityBoard.portfolio_risk.risk_level) : "--"} />
          <InfoPill compact label="快照日期" value={`${priorityBoard?.latest_trade_date ?? "--"} / 更新 ${shortTime(priorityBoard?.updated_at) || "--"}`} />
          <InfoPill compact label="数据状态" value={priorityBoard?.data_quality_text ?? "--"} tone={dataQualityTone(priorityBoard?.data_quality)} />
          <InfoPill compact label="市场总闸" value={`${priorityBoard?.market_gate_decision ?? "--"} / ${Math.round((priorityBoard?.market_firepower_multiplier ?? 1) * 100)}%`} tone={priorityBoard?.market_gate_decision === "block" ? "down" : priorityBoard?.market_gate_decision === "reduce" ? "warn" : "up"} />
          <InfoPill compact label="今日分层" value={`确认 ${priorityBoard?.immediate_count ?? 0} / 观察 ${(priorityBoard?.focus_count ?? 0) + (priorityBoard?.track_count ?? 0)} / 榜单 ${priorityBoard?.total_candidates ?? 0}`} tone={(priorityBoard?.immediate_count ?? 0) ? "up" : "warn"} />
        </ContextRow>
        <MarketStateGatePanel board={priorityBoard} />
        <SectorLeaderGatePanel sectorRelativeStrength={sectorRelativeStrength} />
        <RiskFilterBadges board={priorityBoard} />
        {priorityNotice ? (
          <Callout title={priorityNotice.title} detail={priorityNotice.detail} tone={priorityNotice.tone === "danger" ? "down" : "warn"} compact />
        ) : null}
        {priorityBoard?.snapshot_warning ? <Callout title={priorityBoard.snapshot_warning} tone="warn" compact /> : null}
        <FamilyStrip priorityBoard={priorityBoard} />
        <VirtualCardList
          items={priorityCards}
          empty={<EmptyState text={buildPriorityEmptyText(priorityBoard)} />}
          estimateSize={164}
          maxHeight={620}
          className="monitor-card-list--inset"
          getItemKey={priorityListKey}
          renderItem={renderPriorityCard}
        />
      </div>

      <div className="monitor-secondary-region">
        <MonitorMoreTabs
          activeKey={moreTab}
          instrumentSyncStatus={instrumentSyncStatus}
          loading={loading}
          marketBreadth={marketBreadth}
          marketPulse={marketPulse}
          hourlySnapshotHistory={hourlySnapshotHistory}
          pairedHedge={pairedHedge}
          priorityBoard={priorityBoard}
          priorityCards={priorityCards}
          reviewReports={reviewReports}
          reviewStatus={reviewStatus}
          runtime={runtime}
          sectorEtfT0={sectorEtfT0}
          watchCards={watchCards}
          onChange={setMoreTab}
        />
      </div>
      <HoldingEntryDrawer
        draft={watchDraft}
        editingSymbol={editingWatchSymbol}
        loading={loading}
        open={holdingDrawerOpen}
        setDraft={setWatchDraft}
        onAddWatchlist={onAddWatchlist}
        onCancelEdit={onCancelEdit}
        onClose={closeHoldingDrawer}
      />
    </section>
  );
});
