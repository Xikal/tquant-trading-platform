import type { CSSProperties } from "react";
import { memo, useMemo } from "react";
import { Button, Collapse, Grid, Space } from "antd";
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
import { NumberField, SearchField, TextField } from "../../components/shared/FormFields";
import { InstrumentSyncProgress } from "./InstrumentSyncProgress";
import {
  buildMonitorMetrics,
  buildPriorityEmptyText,
  buildPriorityNotice,
  dataQualityTone,
  formatRatioPct,
  resolveTodayAction,
} from "./MonitorPage.helpers";
import {
  HourlyAllMarketPulse,
  IntradayPulseCard,
  KeyLevelAlerts,
  MarketBreadthStrip,
  MonitorInputSideRail,
  MonitorPriorityStockCard,
  MonitorReviewPanel,
  MonitorWatchStockCard,
  SectorEtfOpportunityCard,
} from "./MonitorPage.panels";
import { MarketStateGatePanel } from "./MarketStateGatePanel";
import { MonitorHoldingWizard } from "./MonitorHoldingWizard";
import { RiskFilterBadges } from "./RiskFilterBadges";
import { SectorLeaderGatePanel } from "./SectorLeaderGatePanel";
import { Callout, ContextRow, EmptyState, FamilyStrip, InfoPill, MetricGrid, PanelTitle } from "../workspace-shared/WorkspaceComponents";
import { WorkspacePageIntro } from "../workspace-shared/WorkspacePageIntro";
import { RitualFortuneStrip } from "../ritual-ui";
import { formatPct, riskLevelText, shortTime } from "../workspace-shared/workspaceFormatters";
import type { MetricItem, StockCardView, WatchDraft } from "../workspace-shared/workspaceTypes";
import {
  MONITOR_ETF_STYLE,
  MONITOR_INPUT_STYLE,
  MONITOR_PRIORITY_STYLE,
  MONITOR_SUMMARY_STYLE,
  monitorGridStyle,
} from "../trading-workspace/workspaceShellStyles";
import { StrategyLaneStatusCard } from "../low-buy/StrategyLaneStatusCard";
import { StrategyLaneTabs } from "../low-buy/StrategyLaneTabs";
import { useWorkspaceMonitorStore } from "../../stores/workspaceMonitorStore";
import { VirtualCardList } from "../../ui/list/VirtualCardList";

const MONITOR_METRIC_DETAILS_STYLE: CSSProperties = {
  marginTop: 8,
  border: "1px solid rgba(148, 163, 184, 0.2)",
  borderRadius: 8,
  background: "#fff",
  padding: "6px 8px",
};

const MONITOR_METRIC_SUMMARY_STYLE: CSSProperties = {
  cursor: "pointer",
  color: "var(--text-2)",
  fontSize: 12,
  fontWeight: 700,
};

const MONITOR_METRIC_GRID_STYLE: CSSProperties = {
  marginTop: 6,
};
const MONITOR_COLLAPSE_STYLE: CSSProperties = {
  marginTop: 8,
  border: "1px solid rgba(148, 163, 184, 0.2)",
  borderRadius: 8,
  background: "#fff",
};
const MONITOR_COLLAPSE_BODY_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
  padding: 8,
};
const MONITOR_HOLDING_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  alignItems: "start",
};
const MONITOR_HOLDING_SEARCH_STYLE: CSSProperties = {
  gridColumn: "1 / -1",
};

const MONITOR_HOLDING_SPAN_STYLE: CSSProperties = {
  gridColumn: "1 / -1",
};

const MONITOR_FULL_ACTION_STYLE: CSSProperties = {
  width: "100%",
};

const MONITOR_GOLD_ACTION_STYLE: CSSProperties = {
  borderColor: "#ecd59a",
  background: "#fbf4e6",
  color: "var(--accent)",
};

const MONITOR_REVIEW_DRAFT_STYLE: CSSProperties = {
  borderColor: "rgba(59, 130, 246, 0.24)",
  background: "#f8fbff",
};
const MONITOR_EMBEDDED_HOLDING_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  marginTop: 10,
  paddingTop: 10,
  borderTop: "1px solid rgba(148, 163, 184, 0.18)",
};
const MONITOR_VIRTUAL_CARD_INSET_STYLE: CSSProperties = {
  paddingRight: 2,
};

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
  const activeLane = useWorkspaceMonitorStore((state) => state.activeStrategyLane);
  const setActiveLane = useWorkspaceMonitorStore((state) => state.setActiveStrategyLane);
  const screens = Grid.useBreakpoint();
  const isEditing = Boolean(editingWatchSymbol);
  const primaryAction = useMemo(() => resolveTodayAction(watchCards, priorityCards, priorityBoard), [watchCards, priorityCards, priorityBoard]);
  const priorityNotice = useMemo(() => buildPriorityNotice(priorityBoard, priorityCards.length), [priorityBoard, priorityCards.length]);
  const metrics: MetricItem[] = useMemo(
    () => buildMonitorMetrics({ priorityBoard, priorityCards, watchCards }),
    [priorityBoard, priorityCards, watchCards]
  );
  const ritualTone = marketPulse?.pulse_level === "weak" || marketPulse?.pulse_level === "defensive" || marketPulse?.pulse_level === "risk_off"
    ? "weak"
    : marketPulse?.pulse_level === "strong" || marketPulse?.pulse_level === "repair" || marketPulse?.pulse_level === "risk_on"
      ? "strong"
      : "neutral";
  const instrumentSyncActive =
    loading === "sync" || instrumentSyncStatus?.status === "queued" || instrumentSyncStatus?.status === "running";
  const wideLayout = screens.xl ?? true;
  const handleLaneChange = (next: StrategyVariant) => {
    setActiveLane(next);
    onLaneChange?.(next);
  };
  return (
    <section style={monitorGridStyle(!wideLayout)}>
      <div className="panel" style={MONITOR_SUMMARY_STYLE}>
        <WorkspacePageIntro
          title="实时监控"
          summary={reviewStatus?.status_text || marketPulse?.pulse_text || "今日复盘、Pulse 和风险动作。"}
          tone={marketPulse?.data_quality === "fresh" ? "up" : marketPulse?.data_quality === "unavailable" ? "down" : marketPulse?.data_quality ? "warn" : "neutral"}
          actions={
            <>
              <Button
                onClick={onSync}
                disabled={instrumentSyncActive}
                title="从数据源更新股票基础信息，通常只在股票名称、行业或代码库异常时使用，可能耗时较久。"
              >
                {instrumentSyncActive ? "股票库更新中" : "更新股票库（较慢）"}
              </Button>
              <Button onClick={onRefresh} loading={loading === "monitor"}>手动刷新</Button>
            </>
          }
          style={MONITOR_REVIEW_DRAFT_STYLE}
        />
        <RitualFortuneStrip marketTone={ritualTone} showCalendarHint />
        <Callout
          label="今天最重要的 1 件事"
          title={primaryAction.title}
          detail={primaryAction.detail}
          tone={primaryAction.tone}
          primary
          action={(
            <Button type="primary" size="small" onClick={primaryAction.source === "holding" ? onRefresh : onGoPlaybook}>
              {primaryAction.source === "holding" ? "刷新确认" : "查看候选"}
            </Button>
          )}
        />
        <IntradayPulseCard pulse={marketPulse} />
        <MonitorReviewPanel reviewStatus={reviewStatus} reviewReports={reviewReports} marketPulse={marketPulse} />
        <Collapse
          size="small"
          style={MONITOR_COLLAPSE_STYLE}
          items={[{
            key: "market-detail",
            label: "盘面细节、小时快照与维护状态",
            styles: { body: MONITOR_COLLAPSE_BODY_STYLE },
            children: (
              <>
                <details style={MONITOR_METRIC_DETAILS_STYLE}>
                  <summary style={MONITOR_METRIC_SUMMARY_STYLE}>盘面数字摘要</summary>
                  <MetricGrid items={metrics} compact style={MONITOR_METRIC_GRID_STYLE} />
                </details>
                <MarketBreadthStrip marketBreadth={marketBreadth} />
                <HourlyAllMarketPulse marketBreadth={marketBreadth} history={hourlySnapshotHistory} />
                <InstrumentSyncProgress status={instrumentSyncStatus} loading={loading === "sync"} />
              </>
            ),
          }]}
        />
        <KeyLevelAlerts alerts={keyLevelAlerts} />
      </div>

      <aside className="panel monitor-input" style={MONITOR_INPUT_STYLE}>
        <PanelTitle
          title={isEditing ? "编辑持仓约束" : "录入底仓约束"}
          actions={isEditing ? <Button htmlType="button" onClick={onCancelEdit}>取消编辑</Button> : null}
        />
        <p className="hint">{isEditing ? `正在编辑 ${editingWatchSymbol}。` : "填写底仓、可卖和成本价，系统按 T+1 判断做T信号。"}</p>
        <MonitorHoldingWizard draft={watchDraft} editing={isEditing} />
        <div style={MONITOR_HOLDING_GRID_STYLE}>
          <div style={MONITOR_HOLDING_SEARCH_STYLE}>
            <SearchField
              label="证券代码"
              value={watchDraft.symbol}
              placeholder="代码或名称"
              disabled={isEditing}
              onChange={(value) => setWatchDraft({ ...watchDraft, symbol: value })}
            />
          </div>
          <NumberField label="底仓数量" value={watchDraft.base_position} onChange={(event) => setWatchDraft({ ...watchDraft, base_position: event.target.value })} />
          <NumberField label="可卖数量" value={watchDraft.available_position} onChange={(event) => setWatchDraft({ ...watchDraft, available_position: event.target.value })} />
          <NumberField label="成本价" value={watchDraft.cost_basis} onChange={(event) => setWatchDraft({ ...watchDraft, cost_basis: event.target.value })} />
          <TextField label="名称" value={watchDraft.name} onChange={(event) => setWatchDraft({ ...watchDraft, name: event.target.value })} />
          <div style={MONITOR_HOLDING_SPAN_STYLE}>
            <TextField label="备注" value={watchDraft.memo} onChange={(event) => setWatchDraft({ ...watchDraft, memo: event.target.value })} />
          </div>
        </div>
        <Button type="primary" style={MONITOR_FULL_ACTION_STYLE} onClick={onAddWatchlist} loading={loading === "watchlist"}>
          {loading === "watchlist" ? "保存中..." : isEditing ? "更新持仓" : watchDraft.symbol.trim() ? "保存持仓" : "加入自选监控"}
        </Button>
        <MonitorInputSideRail
          marketPulse={marketPulse}
          primaryAction={primaryAction}
          priorityCards={priorityCards}
          reviewStatus={reviewStatus}
          watchCards={watchCards}
          onAnalyze={onAnalyze}
          onGoPlaybook={onGoPlaybook}
          onRefresh={onRefresh}
          onSelect={onSelect}
        />
        <div style={MONITOR_EMBEDDED_HOLDING_STYLE}>
          <PanelTitle title="已录入底仓" actions={<span className="muted">{watchCards.length} 个自选 / {runtime?.database_backend ?? "runtime"} </span>} />
          <VirtualCardList
            items={watchCards}
            empty={<EmptyState text="暂无自选持仓。录入底仓后会显示做T信号。" />}
            estimateSize={170}
            maxHeight={460}
            style={MONITOR_VIRTUAL_CARD_INSET_STYLE}
            getItemKey={(stock) => stock.symbol}
            renderItem={(stock) => (
              <MonitorWatchStockCard
                stock={stock}
                onAnalyze={onAnalyze}
                onEdit={onEdit}
                onRemove={onRemove}
                onSelect={onSelect}
              />
            )}
          />
        </div>
      </aside>

      <div className="panel" style={MONITOR_PRIORITY_STYLE}>
        <PanelTitle
          title={priorityBoard?.display_lane_title || "生产优先榜"}
          actions={
            <>
              <Button style={MONITOR_GOLD_ACTION_STYLE} onClick={onAi} loading={loading === "ai"}>{loading === "ai" ? "解读中..." : "解读榜单"}</Button>
              <Button onClick={onGoPlaybook}>去选股宝典</Button>
            </>
          }
        />
        <Space direction="vertical" size={8} style={MONITOR_FULL_ACTION_STYLE}>
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
          style={MONITOR_VIRTUAL_CARD_INSET_STYLE}
          getItemKey={(stock) => `${stock.symbol}-${stock.actionText}`}
          renderItem={(stock) => (
            <MonitorPriorityStockCard stock={stock} onAnalyze={onAnalyze} onSelect={onSelect} />
          )}
        />
      </div>

      <div className="panel" style={MONITOR_ETF_STYLE}>
        <PanelTitle title="行业 ETF 做T替代" actions={<span className="muted">利用 ETF T+0 特性，降低个股隔夜风险</span>} />
        {pairedHedge?.disclaimer ? <Callout title={pairedHedge.disclaimer} tone="down" compact /> : null}
        <VirtualCardList
          items={sectorEtfT0?.opportunities ?? []}
          empty={<EmptyState text="暂无 ETF 做T替代信号。只有板块低吸/热点信号明确时才展示。" />}
          estimateSize={155}
          maxHeight={520}
          style={MONITOR_VIRTUAL_CARD_INSET_STYLE}
          getItemKey={(item) => `${item.etf_symbol}-${item.source_signal_symbol}`}
          renderItem={(item) => <SectorEtfOpportunityCard item={item} />}
        />
        {sectorEtfT0?.notes?.length ? <p className="hint">{sectorEtfT0.notes[0]}</p> : null}
      </div>
    </section>
  );
});
