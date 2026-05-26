import type { CSSProperties } from "react";
import { memo, useMemo } from "react";
import { Alert, Button, Card, Col, Collapse, Flex, Grid, Row, Space, Tag, Typography } from "antd";
import type {
  IntradayKeyLevelResponse,
  IntradayMarketPulse,
  LowBuyPriorityBoardResult,
  MarketBreadth,
  MarketHourlySnapshotHistoryItem,
  MarketReviewReport,
  MarketReviewStatus,
  PairedHedgeResearchResponse,
  RuntimeStatus,
  SectorEtfT0Response,
  SectorRelativeStrengthResponse,
} from "../../types";
import type { InstrumentSyncStatus } from "../../types";
import { NumberField, SearchField, TextField } from "../../components/shared/FormFields";
import { InstrumentSyncProgress } from "./InstrumentSyncProgress";
import {
  buildBoardDistribution,
  buildMonitorMetrics,
  buildPriorityNotice,
  dataQualityTone,
  formatRatioPct,
  resolveTodayAction,
} from "./MonitorPage.helpers";
import { MonitorHoldingWizard } from "./MonitorHoldingWizard";
import { Callout, ContextRow, EmptyState, FamilyStrip, InfoPill, MetricGrid, PanelTitle, StockCard, StockCardList } from "../workspace-shared/WorkspaceComponents";
import { WorkspacePageIntro } from "../workspace-shared/WorkspacePageIntro";
import { formatPct, formatPrice, riskLevelText, shortTime } from "../workspace-shared/workspaceFormatters";
import type { MetricItem, StockCardView, WatchDraft } from "../workspace-shared/workspaceTypes";
import {
  MONITOR_ETF_STYLE,
  MONITOR_INPUT_STYLE,
  MONITOR_PRIORITY_STYLE,
  MONITOR_SUMMARY_STYLE,
  monitorGridStyle,
} from "../trading-workspace/workspaceShellStyles";

const MONITOR_METRIC_DETAILS_STYLE: CSSProperties = {
  marginTop: 8,
  border: "1px solid rgba(148, 163, 184, 0.2)",
  borderRadius: 8,
  background: "#fff",
  padding: "6px 8px",
};

const MONITOR_METRIC_SUMMARY_STYLE: CSSProperties = {
  cursor: "pointer",
  color: "#475569",
  fontSize: 12,
  fontWeight: 900,
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
const MONITOR_EMOTION_CARD_STYLE: CSSProperties = {
  background: "#f8fbff",
  borderColor: "#d9eaf7",
  marginTop: 10,
};
const MONITOR_BAR_STAGE_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "stretch",
  gap: 6,
  minHeight: 164,
  height: 196,
  padding: "2px 4px 0",
};
const MONITOR_BAR_COLUMN_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  justifyContent: "flex-end",
  alignItems: "center",
  flex: 1,
  minWidth: 0,
  height: "100%",
};
const MONITOR_BAR_FILL_STYLE: CSSProperties = {
  width: "100%",
  minHeight: 16,
  borderRadius: "8px 8px 3px 3px",
};
const MONITOR_BAR_LABEL_STYLE: CSSProperties = {
  marginTop: 4,
  fontSize: 10,
  lineHeight: 1.1,
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

const MONITOR_ETF_CARD_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  padding: 9,
  border: "1px solid var(--line)",
  borderRadius: 8,
  background: "#fff",
};

const MONITOR_ETF_CARD_HEAD_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 8,
};

const MONITOR_ETF_CARD_HEAD_TEXT_STYLE: CSSProperties = {
  display: "grid",
  gap: 2,
};

const MONITOR_ETF_CARD_META_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
  color: "#64748b",
  fontSize: 11,
};

const MONITOR_ETF_CARD_HINT_STYLE: CSSProperties = {
  color: "#64748b",
  fontSize: 11,
  lineHeight: 1.4,
};
const MONITOR_BREADTH_ROW_STYLE: CSSProperties = {
  marginTop: 10,
};
const MONITOR_HOURLY_CARD_STYLE: CSSProperties = {
  marginTop: 10,
  borderColor: "rgba(59, 130, 246, 0.22)",
};
const MONITOR_HOURLY_BODY_STYLE: CSSProperties = {
  padding: 8,
};
const MONITOR_HOURLY_NOTE_STYLE: CSSProperties = {
  display: "block",
  marginTop: 6,
};
const MONITOR_FULL_WIDTH_STYLE: CSSProperties = {
  width: "100%",
};
const MONITOR_ALERT_SPACING_STYLE: CSSProperties = {
  marginBottom: 8,
};
const MONITOR_TREND_STRIP_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  marginTop: 8,
};
const MONITOR_TREND_BAR_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  alignItems: "end",
  minHeight: 72,
};
const MONITOR_TREND_BAR_ITEM_STYLE: CSSProperties = {
  display: "grid",
  gap: 3,
  alignItems: "end",
  minWidth: 0,
};
const MONITOR_TREND_LABEL_STYLE: CSSProperties = {
  fontSize: 10,
  textAlign: "center",
};
const MONITOR_EMOTION_COLUMN_STYLE: CSSProperties = {
  display: "flex",
};
const MONITOR_EMOTION_HEADER_STYLE: CSSProperties = {
  minHeight: 34,
  padding: "0 10px",
};
const MONITOR_EMOTION_BODY_STYLE: CSSProperties = {
  padding: 8,
};
const MONITOR_LEADER_ROW_STYLE: CSSProperties = {
  background: "#fff",
  borderRadius: 6,
  padding: "3px 6px",
};
const MONITOR_LEADER_NAME_STYLE: CSSProperties = {
  fontSize: 11.5,
};
const MONITOR_LEADER_META_STYLE: CSSProperties = {
  fontSize: 10.5,
};
const MONITOR_KEY_ALERT_WRAP_STYLE: CSSProperties = {
  bottom: 10,
  maxWidth: "min(300px, calc(100vw - 20px))",
  position: "fixed",
  right: 10,
  zIndex: 60,
};
const MONITOR_KEY_ALERT_STYLE: CSSProperties = {
  padding: "6px 8px",
};
const MONITOR_KEY_ALERT_TITLE_STYLE: CSSProperties = {
  fontSize: 12,
};
const MONITOR_KEY_ALERT_DESC_STYLE: CSSProperties = {
  fontSize: 11,
};
const MONITOR_REVIEW_DRAFT_STYLE: CSSProperties = {
  borderColor: "rgba(59, 130, 246, 0.24)",
  background: "#f8fbff",
};
const MONITOR_SIDE_RAIL_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
  marginTop: 10,
  paddingTop: 10,
  borderTop: "1px solid rgba(148, 163, 184, 0.18)",
};
const MONITOR_SIDE_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
};
const MONITOR_SIDE_LIST_STYLE: CSSProperties = {
  display: "grid",
  gap: 5,
};
const MONITOR_SIDE_ROW_STYLE: CSSProperties = {
  display: "grid",
  gap: 3,
  border: "1px solid rgba(148, 163, 184, 0.16)",
  borderRadius: 7,
  background: "#fff",
  padding: "6px 7px",
};
const MONITOR_SIDE_ROW_HEAD_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 8,
  minWidth: 0,
};
const MONITOR_SIDE_ROW_TEXT_STYLE: CSSProperties = {
  fontSize: 11,
  minWidth: 0,
};
const MONITOR_SIDE_ROW_META_STYLE: CSSProperties = {
  color: "#64748b",
  fontSize: 10.5,
  minWidth: 0,
};
const MONITOR_EMBEDDED_HOLDING_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  marginTop: 10,
  paddingTop: 10,
  borderTop: "1px solid rgba(148, 163, 184, 0.18)",
};

export interface MonitorPageProps {
  priorityBoard: LowBuyPriorityBoardResult | null;
  marketBreadth: MarketBreadth | null;
  marketPulse: IntradayMarketPulse | null;
  hourlySnapshotHistory: MarketHourlySnapshotHistoryItem[];
  reviewStatus: MarketReviewStatus | null;
  reviewReports: MarketReviewReport[];
  sectorRelativeStrength: SectorRelativeStrengthResponse | null;
  keyLevelAlerts: IntradayKeyLevelResponse[];
  sectorEtfT0: SectorEtfT0Response | null;
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
  sectorRelativeStrength,
  keyLevelAlerts,
  sectorEtfT0,
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
  onSelect,
  onAnalyze,
  onEdit,
  onRemove,
  onAddWatchlist,
  onCancelEdit,
}: MonitorPageProps) {
  const screens = Grid.useBreakpoint();
  const isEditing = Boolean(editingWatchSymbol);
  const primaryAction = useMemo(() => resolveTodayAction(watchCards, priorityCards, priorityBoard), [watchCards, priorityCards, priorityBoard]);
  const priorityNotice = useMemo(() => buildPriorityNotice(priorityBoard, priorityCards.length), [priorityBoard, priorityCards.length]);
  const metrics: MetricItem[] = useMemo(
    () => buildMonitorMetrics({ priorityBoard, priorityCards, watchCards }),
    [priorityBoard, priorityCards, watchCards]
  );
  const instrumentSyncActive =
    loading === "sync" || instrumentSyncStatus?.status === "queued" || instrumentSyncStatus?.status === "running";
  const wideLayout = screens.xl ?? true;
  return (
    <section style={monitorGridStyle(!wideLayout)}>
      <div className="panel" style={MONITOR_SUMMARY_STYLE}>
        <WorkspacePageIntro
          title="实时监控"
          summary={reviewStatus?.status_text || marketPulse?.pulse_text || "今日复盘、Pulse 和风险动作。"}
          more="全市场午盘/收盘复盘以实时监控为主入口；模拟盘只保留历史入口。"
          moreLabel="页面说明"
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
          pills={[
            { label: "今日复盘", value: reviewStatus?.status_text || "--", tone: reviewStatus?.has_midday || reviewStatus?.has_close ? "up" : "warn" },
            { label: "下一次触发", value: shortTime(reviewStatus?.next_trigger_at) || "--" },
            { label: "Pulse", value: marketPulse?.data_quality_text || "--", tone: marketPulse?.data_quality === "fresh" ? "up" : marketPulse?.data_quality === "unavailable" ? "down" : marketPulse?.data_quality ? "warn" : "neutral" },
            { label: "风险提示", value: String(reviewStatus?.risk_alert_count ?? 0), tone: (reviewStatus?.risk_alert_count ?? 0) > 0 ? "warn" : "neutral" },
          ]}
          style={MONITOR_REVIEW_DRAFT_STYLE}
        />
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
                <MarketEmotionDashboard marketBreadth={marketBreadth} sectorRelativeStrength={sectorRelativeStrength} />
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
          <StockCardList compact>
            {watchCards.length ? watchCards.map((stock) => (
              <StockCard
                key={stock.symbol}
                stock={stock}
                actions={["详情", "分析", "编辑", "移除"]}
                compact
                onAction={(action) => {
                  if (action === "移除") {
                    onRemove(stock.symbol);
                  } else if (action === "编辑") {
                    onEdit(stock);
                  } else if (action === "分析") {
                    onAnalyze(stock);
                  } else {
                    onSelect(stock);
                  }
                }}
              />
            )) : <EmptyState text="暂无自选持仓。录入底仓后会显示做T信号。" />}
          </StockCardList>
        </div>
      </aside>

      <div className="panel" style={MONITOR_PRIORITY_STYLE}>
        <PanelTitle
          title="全策略优先级榜"
          actions={
            <>
              <Button style={MONITOR_GOLD_ACTION_STYLE} onClick={onAi} loading={loading === "ai"}>{loading === "ai" ? "解读中..." : "解读榜单"}</Button>
              <Button onClick={onGoPlaybook}>去选股宝典</Button>
            </>
          }
        />
        <ContextRow>
          <InfoPill compact label="今日方向" value={priorityBoard?.directional_bias_text ?? "--"} />
          <InfoPill compact label="市场状态" value={priorityBoard?.market_state_text ?? "--"} />
          <InfoPill compact label="热点板块" value={(priorityBoard?.hot_industries ?? []).slice(0, 4).join(" / ") || "--"} />
          <InfoPill compact label="宽度情绪" value={`上涨 ${formatPct(priorityBoard?.stock_up_ratio, 0)} / 涨停 ${priorityBoard?.limit_up_count ?? "--"}`} />
          <InfoPill compact label="组合风险" value={priorityBoard?.portfolio_risk?.risk_level ? riskLevelText(priorityBoard.portfolio_risk.risk_level) : "--"} />
          <InfoPill compact label="快照日期" value={`${priorityBoard?.latest_trade_date ?? "--"} / 更新 ${shortTime(priorityBoard?.updated_at) || "--"}`} />
          <InfoPill compact label="数据状态" value={priorityBoard?.data_quality_text ?? "--"} tone={dataQualityTone(priorityBoard?.data_quality)} />
          <InfoPill compact label="今日分层" value={`确认 ${priorityBoard?.immediate_count ?? 0} / 观察 ${(priorityBoard?.focus_count ?? 0) + (priorityBoard?.track_count ?? 0)} / 榜单 ${priorityBoard?.total_candidates ?? 0}`} tone={(priorityBoard?.immediate_count ?? 0) ? "up" : "warn"} />
        </ContextRow>
        {priorityNotice ? (
          <Callout title={priorityNotice.title} detail={priorityNotice.detail} tone={priorityNotice.tone === "danger" ? "down" : "warn"} compact />
        ) : null}
        {priorityBoard?.snapshot_warning ? <Callout title={priorityBoard.snapshot_warning} tone="warn" compact /> : null}
        <FamilyStrip priorityBoard={priorityBoard} />
        <StockCardList compact>
          {priorityCards.length ? priorityCards.slice(0, 12).map((stock) => (
            <StockCard
              key={`${stock.symbol}-${stock.actionText}`}
              stock={stock}
              actions={["详情", "分析"]}
              compact
              onAction={(action) => (action === "分析" ? onAnalyze(stock) : onSelect(stock))}
            />
          )) : <EmptyState text="暂无优先级榜单结果，等待后台全量深筛缓存完成。" />}
        </StockCardList>
      </div>

      <div className="panel" style={MONITOR_ETF_STYLE}>
        <PanelTitle title="行业 ETF 做T替代" actions={<span className="muted">利用 ETF T+0 特性，降低个股隔夜风险</span>} />
        {pairedHedge?.disclaimer ? <Callout title={pairedHedge.disclaimer} tone="down" compact /> : null}
        <StockCardList compact>
          {(sectorEtfT0?.opportunities ?? []).length ? sectorEtfT0!.opportunities.slice(0, 6).map((item) => (
            <article style={MONITOR_ETF_CARD_STYLE} key={`${item.etf_symbol}-${item.source_signal_symbol}`}>
              <div style={MONITOR_ETF_CARD_HEAD_STYLE}>
                <div style={MONITOR_ETF_CARD_HEAD_TEXT_STYLE}>
                  <strong>{item.etf_name}</strong>
                  <span>{item.etf_symbol} · 来源 {item.source_signal_name}</span>
                </div>
                <span className={`pill ${item.bias === "positive_t" ? "up" : item.bias === "negative_t" ? "down" : "neutral"}`}>{item.bias_text}</span>
              </div>
              <div style={MONITOR_ETF_CARD_META_STYLE}>
                <span>板块：{item.sector_name || "未分类"}</span>
                <span>信心：{formatPct(item.confidence, 0)}</span>
                <span>ETF价：{formatPrice(item.last_price)}</span>
                <span>ETF涨跌：{formatPct(item.change_pct)}</span>
              </div>
              <p style={MONITOR_ETF_CARD_HINT_STYLE}>{item.reason}</p>
              <p style={MONITOR_ETF_CARD_HINT_STYLE}>买点 {item.entry_zone || "--"}；卖点 {item.sell_zone || "--"}；风险：{item.risk}</p>
            </article>
          )) : <EmptyState text="暂无 ETF 做T替代信号。只有板块低吸/热点信号明确时才展示。" />}
        </StockCardList>
        {sectorEtfT0?.notes?.length ? <p className="hint">{sectorEtfT0.notes[0]}</p> : null}
      </div>
    </section>
  );
});

function MarketBreadthStrip({ marketBreadth }: { marketBreadth: MarketBreadth | null }) {
  if (!marketBreadth) {
    return null;
  }
  return (
    <Row gutter={[8, 8]} style={MONITOR_BREADTH_ROW_STYLE}>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="市场宽度" value={formatRatioPct(marketBreadth.stock_up_ratio)} />
      </Col>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="中位涨跌" value={formatPct(marketBreadth.stock_median_change)} />
      </Col>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="涨停/跌停" value={`${marketBreadth.limit_up_count} / ${marketBreadth.limit_down_count ?? "--"}`} />
      </Col>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="炸板率" value={formatRatioPct(marketBreadth.broken_board_ratio)} />
      </Col>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="连板高度" value={String(marketBreadth.board_height || "--")} />
      </Col>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="数据质量" value={marketBreadth.data_quality_text || "--"} tone={dataQualityTone(marketBreadth.data_quality)} />
      </Col>
    </Row>
  );
}

function MonitorInputSideRail({
  marketPulse,
  primaryAction,
  priorityCards,
  reviewStatus,
  watchCards,
  onAnalyze,
  onGoPlaybook,
  onRefresh,
  onSelect,
}: {
  marketPulse: IntradayMarketPulse | null;
  primaryAction: ReturnType<typeof resolveTodayAction>;
  priorityCards: StockCardView[];
  reviewStatus: MarketReviewStatus | null;
  watchCards: StockCardView[];
  onAnalyze: (stock: StockCardView) => void;
  onGoPlaybook: () => void;
  onRefresh: () => void;
  onSelect: (stock: StockCardView) => void;
}) {
  const activeHoldings = watchCards.filter((card) => card.actionText !== "暂不操作").slice(0, 3);
  const topCandidates = priorityCards.slice(0, 3);
  return (
    <div style={MONITOR_SIDE_RAIL_STYLE}>
      <PanelTitle
        title="右侧速览"
        actions={<Button size="small" onClick={primaryAction.source === "holding" ? onRefresh : onGoPlaybook}>{primaryAction.source === "holding" ? "刷新" : "榜单"}</Button>}
      />
      <Callout
        title={primaryAction.title}
        detail={primaryAction.detail}
        tone={primaryAction.tone}
        compact
      />
      <div style={MONITOR_SIDE_GRID_STYLE}>
        <InfoPill compact label="复盘状态" value={reviewStatus?.status_text || "等待"} tone={reviewStatus?.has_midday || reviewStatus?.has_close ? "up" : "warn"} />
        <InfoPill compact label="下次触发" value={shortTime(reviewStatus?.next_trigger_at) || "--"} />
        <InfoPill compact label="Pulse" value={marketPulse?.data_quality_text || "--"} tone={marketPulse?.data_quality === "fresh" ? "up" : marketPulse?.data_quality ? "warn" : "neutral"} />
        <InfoPill compact label="风险数" value={String(reviewStatus?.risk_alert_count ?? 0)} tone={(reviewStatus?.risk_alert_count ?? 0) > 0 ? "down" : "neutral"} />
      </div>
      <MiniMonitorList
        emptyText="暂无可执行持仓信号"
        items={activeHoldings}
        title="持仓动作"
        onAnalyze={onAnalyze}
        onSelect={onSelect}
      />
      <MiniMonitorList
        emptyText="暂无候选"
        items={topCandidates}
        title="榜单前三"
        onAnalyze={onAnalyze}
        onSelect={onSelect}
      />
    </div>
  );
}

function MiniMonitorList({
  emptyText,
  items,
  title,
  onAnalyze,
  onSelect,
}: {
  emptyText: string;
  items: StockCardView[];
  title: string;
  onAnalyze: (stock: StockCardView) => void;
  onSelect: (stock: StockCardView) => void;
}) {
  return (
    <div style={MONITOR_SIDE_LIST_STYLE}>
      <Typography.Text strong style={{ fontSize: 11 }}>{title}</Typography.Text>
      {items.length ? items.map((stock) => (
        <article key={`${title}-${stock.symbol}`} style={MONITOR_SIDE_ROW_STYLE}>
          <div style={MONITOR_SIDE_ROW_HEAD_STYLE}>
            <Typography.Text strong ellipsis style={MONITOR_SIDE_ROW_TEXT_STYLE}>{stock.name}</Typography.Text>
            <Typography.Text style={{ ...MONITOR_SIDE_ROW_TEXT_STYLE, color: toneColor(stock.tone) }}>{stock.changeText}</Typography.Text>
          </div>
          <Typography.Text ellipsis={{ tooltip: stock.actionText }} style={MONITOR_SIDE_ROW_META_STYLE}>{stock.symbol} · {stock.actionText}</Typography.Text>
          <Flex gap={5} wrap>
            <Button size="small" onClick={() => onSelect(stock)}>详情</Button>
            <Button size="small" onClick={() => onAnalyze(stock)}>分析</Button>
          </Flex>
        </article>
      )) : <EmptyState text={emptyText} />}
    </div>
  );
}

function IntradayPulseCard({ pulse }: { pulse: IntradayMarketPulse | null }) {
  if (!pulse) {
    return (
      <Card size="small" title="盘中 Pulse" style={MONITOR_HOURLY_CARD_STYLE} styles={{ body: MONITOR_HOURLY_BODY_STYLE }}>
        <EmptyState text="Pulse 暂无数据" />
      </Card>
    );
  }
  return (
    <Card
      size="small"
      title="盘中 Pulse"
      extra={<Tag color={pulseTagColor(pulse.data_quality)}>{pulse.data_quality_text || pulse.data_quality}</Tag>}
      style={MONITOR_HOURLY_CARD_STYLE}
      styles={{ body: MONITOR_HOURLY_BODY_STYLE }}
    >
      <Space direction="vertical" size={8} style={MONITOR_FULL_WIDTH_STYLE}>
        <Callout
          title={pulse.pulse_text || "等待盘中数据刷新"}
          detail={pulse.suggested_action || "只读观察，不触发交易。"}
          tone={pulseTone(pulse.pulse_level)}
          compact
        />
        <Row gutter={[8, 8]}>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="市场宽度" value={pulse.market_strength_text || "--"} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="龙头强度" value={pulse.leader_strength_text || "--"} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="情绪温度" value={pulse.emotion_text || "--"} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="小时快照" value={pulse.hourly_snapshot_text || "--"} />
          </Col>
        </Row>
        {pulse.partial_errors?.length ? <InfoPill compact label="降级源" value={pulse.partial_errors.map((item) => item.source).join(" / ")} tone="warn" /> : null}
      </Space>
    </Card>
  );
}

function MonitorReviewPanel({
  reviewStatus,
  reviewReports,
  marketPulse,
}: {
  reviewStatus: MarketReviewStatus | null;
  reviewReports: MarketReviewReport[];
  marketPulse: IntradayMarketPulse | null;
}) {
  const midday = reviewReports.find((item) => item.report_slot === "midday");
  const close = reviewReports.find((item) => item.report_slot === "close");
  return (
    <Card
      size="small"
      title="今日全市场午盘 / 收盘复盘"
      extra={<Typography.Text type="secondary">下次 {reviewStatus?.next_trigger_at || "--"}</Typography.Text>}
      style={MONITOR_HOURLY_CARD_STYLE}
      styles={{ body: MONITOR_HOURLY_BODY_STYLE }}
    >
      <Space direction="vertical" size={8} style={MONITOR_FULL_WIDTH_STYLE}>
        <Row gutter={[8, 8]}>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="今日状态" value={reviewStatus?.status_text || "今日暂无市场复盘"} tone={reviewStatus?.has_midday || reviewStatus?.has_close ? "up" : "warn"} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="市场午盘复盘" value={midday ? "已生成" : "等待触发"} tone={midday ? "up" : "warn"} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="市场收盘复盘" value={close ? "已生成" : "等待触发"} tone={close ? "up" : "warn"} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="风险提示" value={String(reviewStatus?.risk_alert_count ?? 0)} tone={(reviewStatus?.risk_alert_count ?? 0) > 0 ? "down" : "neutral"} />
          </Col>
        </Row>
        <Callout
          title="建议动作"
          detail={reviewStatus?.suggested_action || "等待午盘或收盘市场复盘生成，盘中按市场 pulse、既有风控和仓位约束执行。"}
          tone={(reviewStatus?.risk_alert_count ?? 0) > 0 ? "down" : "neutral"}
          compact
        />
        <Row gutter={[8, 8]}>
          <Col xs={24} md={12}>
            <ReviewSnippet title="全市场午盘复盘" report={midday} />
          </Col>
          <Col xs={24} md={12}>
            <ReviewSnippet title="全市场收盘复盘" report={close} />
          </Col>
        </Row>
        {marketPulse?.autofill_details?.length ? (
          <Collapse
            ghost
            size="small"
            items={[{
              key: "autofill",
              label: "自动补全明细",
              children: marketPulse.autofill_details.map((item) => item.detail || item.source).join("；"),
            }]}
          />
        ) : null}
      </Space>
    </Card>
  );
}

function ReviewSnippet({ title, report }: { title: string; report?: MarketReviewReport }) {
  if (!report) {
    return <EmptyState text={`${title}暂未生成。`} />;
  }
  return (
    <article style={MONITOR_ETF_CARD_STYLE}>
      <Flex justify="space-between" gap={8}>
        <Typography.Text strong>{title}</Typography.Text>
        <Typography.Text type="secondary">{shortTime(report.generated_at) || report.report_date}</Typography.Text>
      </Flex>
      <Typography.Text ellipsis={{ tooltip: report.overall_summary || "--" }}>{report.overall_summary || "--"}</Typography.Text>
      <Typography.Text type="secondary" ellipsis={{ tooltip: report.suggestion || "--" }}>{report.suggestion || "--"}</Typography.Text>
      {(report.autofill_details?.length || report.missing_data?.length || report.risk_alerts?.length) ? (
        <Collapse
          ghost
          size="small"
          items={[{
            key: "detail",
            label: "明细",
            children: (
              <Space direction="vertical" size={2}>
                {report.autofill_details?.length ? <Typography.Text type="secondary">自动补全：{report.autofill_details.map((item) => item.detail || item.source).join("；")}</Typography.Text> : null}
                {report.missing_data?.length ? <Typography.Text type="secondary">缺少：{report.missing_data.map((item) => item.name || item.source).join("；")}</Typography.Text> : null}
                {report.risk_alerts?.length ? <Typography.Text type="danger">风险：{report.risk_alerts.map((item) => item.content).join("；")}</Typography.Text> : null}
              </Space>
            ),
          }]}
        />
      ) : null}
    </article>
  );
}

function pulseTagColor(quality?: string): string {
  if (quality === "fresh") return "green";
  if (quality === "partial" || quality === "stale") return "gold";
  return "red";
}

function pulseTone(level?: string): "up" | "warn" | "down" | "neutral" {
  if (level === "weak" || level === "defensive" || level === "unavailable" || level === "risk_off") return "down";
  if (level === "strong" || level === "repair" || level === "risk_on") return "up";
  if (level === "neutral" || level === "balanced") return "warn";
  return "neutral";
}

function toneColor(tone: string): string {
  if (tone === "up") return "#cf2626";
  if (tone === "down") return "#1f8b4c";
  if (tone === "warn") return "#b7791f";
  return "#475569";
}

function HourlyAllMarketPulse({
  marketBreadth,
  history,
}: {
  marketBreadth: MarketBreadth | null;
  history: MarketHourlySnapshotHistoryItem[];
}) {
  const snapshot = marketBreadth?.hourly_all_market_snapshot;
  const points = buildHourlyTrendPoints(history, snapshot);
  if ((!snapshot || Object.keys(snapshot).length === 0) && !points.length) {
    return null;
  }
  const weakening = hourlyTrendWeakening(points);
  const latestPoint = points.length ? points[points.length - 1] : undefined;
  const firstHistory = history.length ? history[0] : undefined;
  return (
    <Card
      size="small"
      title="小时全市场快照"
      extra={<Typography.Text type="secondary">{shortTime(snapshot?.updated_at) || latestPoint?.label || "--"}</Typography.Text>}
      style={MONITOR_HOURLY_CARD_STYLE}
      styles={{ body: MONITOR_HOURLY_BODY_STYLE }}
    >
      {weakening ? (
        <Alert
          type="warning"
          showIcon
          message="全市场强弱分连续走弱"
          description="最近两个小时快照都在回落，短线追高要降速，优先观察已验证方向。"
          style={MONITOR_ALERT_SPACING_STYLE}
        />
      ) : null}
      <Row gutter={[8, 8]}>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="样本数" value={String(snapshot?.snapshot_count ?? firstHistory?.snapshot_count ?? "--")} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="上涨比例" value={formatRatioPct(snapshot?.stock_up_ratio)} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="下跌比例" value={formatRatioPct(snapshot?.stock_down_ratio)} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="中位涨跌" value={formatPct(snapshot?.stock_median_change)} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="强/弱" value={`${snapshot?.strong_count ?? "--"} / ${snapshot?.weak_count ?? "--"}`} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="强弱分" value={String(snapshot?.market_strength_score ?? latestPoint?.score ?? "--")} tone={hourlyPulseTone(snapshot?.market_strength_score ?? latestPoint?.score)} />
        </Col>
      </Row>
      {points.length >= 2 ? <HourlyTrendStrip points={points} /> : null}
      <Typography.Text type="secondary" style={MONITOR_HOURLY_NOTE_STYLE}>
        {snapshot?.market_strength_text || snapshot?.data_quality_text || latestPoint?.quality || "等待全市场快照刷新"}
      </Typography.Text>
    </Card>
  );
}

function HourlyTrendStrip({ points }: { points: Array<{ label: string; score: number; quality: string }> }) {
  const min = Math.min(...points.map((item) => item.score), -20);
  const max = Math.max(...points.map((item) => item.score), 20);
  const span = Math.max(max - min, 1);
  return (
    <div style={MONITOR_TREND_STRIP_STYLE}>
      <Flex justify="space-between" align="center">
        <Typography.Text strong>日内强弱趋势</Typography.Text>
        <Typography.Text type="secondary">{points.length} 个快照</Typography.Text>
      </Flex>
      <div style={{ ...MONITOR_TREND_BAR_GRID_STYLE, gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))` }}>
        {points.map((item) => {
          const height = Math.max(14, Math.round(((item.score - min) / span) * 54) + 10);
          return (
            <div key={item.label} style={MONITOR_TREND_BAR_ITEM_STYLE}>
              <div
                title={`${item.label} 强弱分 ${item.score.toFixed(1)} · ${item.quality}`}
                style={{
                  height,
                  borderRadius: 4,
                  background: item.score >= 10 ? "#16a34a" : item.score <= -10 ? "#dc2626" : "#f59e0b",
                }}
              />
              <Typography.Text type="secondary" style={MONITOR_TREND_LABEL_STYLE}>
                {item.label}
              </Typography.Text>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function buildHourlyTrendPoints(
  history: MarketHourlySnapshotHistoryItem[],
  snapshot?: MarketBreadth["hourly_all_market_snapshot"],
): Array<{ label: string; score: number; quality: string }> {
  const points = history
    .slice()
    .sort((left, right) => String(left.snapshot_bucket).localeCompare(String(right.snapshot_bucket)))
    .map((item) => ({
      label: hourlyBucketLabel(item.snapshot_bucket) || shortTime(item.updated_at) || "--",
      score: Number(item.market_strength_score ?? item.payload?.market_strength_score ?? 0),
      quality: item.data_quality || String(item.payload?.data_quality_text || ""),
    }))
    .filter((item) => Number.isFinite(item.score));
  if (snapshot && Number.isFinite(Number(snapshot.market_strength_score))) {
    const label = shortTime(snapshot.updated_at) || "最新";
    const latestScore = Number(snapshot.market_strength_score);
    const exists = points.some((item) => item.label === label && Math.abs(item.score - latestScore) < 0.001);
    if (!exists) {
      points.push({
        label,
        score: latestScore,
        quality: snapshot.data_quality_text || "",
      });
    }
  }
  return points.slice(-8);
}

function hourlyTrendWeakening(points: Array<{ score: number }>): boolean {
  if (points.length < 3) return false;
  const recent = points.slice(-3);
  return recent[2].score < recent[1].score - 5 && recent[1].score < recent[0].score - 5;
}

function hourlyBucketLabel(bucket: string): string {
  const compact = String(bucket || "").replace(/\D/g, "");
  if (compact.length >= 12) {
    return `${compact.slice(8, 10)}:${compact.slice(10, 12)}`;
  }
  return "";
}

function hourlyPulseTone(score?: number): "up" | "warn" | "down" | "neutral" {
  if (typeof score !== "number" || !Number.isFinite(score)) return "neutral";
  if (score >= 10) return "up";
  if (score <= -10) return "down";
  return "warn";
}

function MarketEmotionDashboard({
  marketBreadth,
  sectorRelativeStrength,
}: {
  marketBreadth: MarketBreadth | null;
  sectorRelativeStrength: SectorRelativeStrengthResponse | null;
}) {
  if (!marketBreadth && !sectorRelativeStrength?.items.length) {
    return null;
  }
  const distribution = buildBoardDistribution(marketBreadth?.board_height ?? 0);
  const leaders = (sectorRelativeStrength?.items ?? []).slice(0, 5);
  return (
      <Card
        size="small"
        style={MONITOR_EMOTION_CARD_STYLE}
        styles={{ header: MONITOR_EMOTION_HEADER_STYLE, body: MONITOR_EMOTION_BODY_STYLE }}
        title="市场情绪与龙头强度"
        extra={<Tag color="blue">{marketBreadth?.emotion_temperature_text || marketBreadth?.state_text || "等待情绪数据"}</Tag>}
      >
        <Row gutter={[10, 10]} align="stretch">
          <Col xs={24} md={10} style={MONITOR_EMOTION_COLUMN_STYLE}>
            <div style={MONITOR_BAR_STAGE_STYLE} aria-label="涨停连板高度分布">
              {distribution.map((item) => (
                <div key={item.label} style={MONITOR_BAR_COLUMN_STYLE}>
                  <div
                    title={`${item.label}：相对高度 ${item.height}%`}
                    style={{
                      ...MONITOR_BAR_FILL_STYLE,
                      background: "linear-gradient(180deg, #ef4444, #f59e0b)",
                      height: `${item.height}%`,
                    }}
                  />
                  <Typography.Text type="secondary" style={MONITOR_BAR_LABEL_STYLE}>
                    {item.label}
                  </Typography.Text>
                </div>
              ))}
            </div>
          </Col>
          <Col xs={24} md={14} style={MONITOR_EMOTION_COLUMN_STYLE}>
            <Space direction="vertical" size={3} style={MONITOR_FULL_WIDTH_STYLE}>
            {leaders.length ? leaders.map((item) => (
              <Flex
                gap={8}
                justify="space-between"
                key={`${item.sector_name}-${item.symbol}`}
                style={MONITOR_LEADER_ROW_STYLE}
              >
                <Typography.Text strong style={MONITOR_LEADER_NAME_STYLE}>{item.name}</Typography.Text>
                <Typography.Text type="secondary" style={MONITOR_LEADER_META_STYLE}>
                  {item.sector_name} #{item.rank} · 龙头分 {item.leader_score.toFixed(0)}
                </Typography.Text>
              </Flex>
            )) : <Typography.Text type="secondary">暂无板块龙头强度数据</Typography.Text>}
            </Space>
          </Col>
        </Row>
      </Card>
    );
}

function KeyLevelAlerts({ alerts }: { alerts: IntradayKeyLevelResponse[] }) {
  const triggered = alerts.filter((item) => item.alert_triggered).slice(0, 2);
  if (!triggered.length) {
    return null;
  }
  return (
    <Space
      direction="vertical"
      role="alert"
      aria-live="polite"
      style={MONITOR_KEY_ALERT_WRAP_STYLE}
    >
      {triggered.map((item) => (
        <Alert
          key={item.symbol}
          type="warning"
          showIcon
          style={MONITOR_KEY_ALERT_STYLE}
          message={<span style={MONITOR_KEY_ALERT_TITLE_STYLE}>{item.name} 接近关键价位</span>}
          description={<span style={MONITOR_KEY_ALERT_DESC_STYLE}>{item.alert_text || `现价 ${formatPrice(item.latest_price)}`}</span>}
        />
      ))}
    </Space>
  );
}
