import type { CSSProperties } from "react";
import { memo, useMemo } from "react";
import { Alert, Button, Card, Col, Flex, Grid, Row, Space, Tag, Typography } from "antd";
import type {
  IntradayKeyLevelResponse,
  LowBuyPriorityBoardResult,
  MarketBreadth,
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
import { formatPct, formatPrice, riskLevelText, shortTime } from "../workspace-shared/workspaceFormatters";
import type { MetricItem, StockCardView, WatchDraft } from "../workspace-shared/workspaceTypes";
import {
  MONITOR_ETF_STYLE,
  MONITOR_INPUT_STYLE,
  MONITOR_PRIORITY_STYLE,
  MONITOR_SUMMARY_STYLE,
  MONITOR_WATCH_STYLE,
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

export interface MonitorPageProps {
  priorityBoard: LowBuyPriorityBoardResult | null;
  marketBreadth: MarketBreadth | null;
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
        <PanelTitle
          title="盘中监控摘要"
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
        <details style={MONITOR_METRIC_DETAILS_STYLE}>
          <summary style={MONITOR_METRIC_SUMMARY_STYLE}>展开盘面数字摘要</summary>
          <MetricGrid items={metrics} compact style={MONITOR_METRIC_GRID_STYLE} />
        </details>
        <MarketBreadthStrip marketBreadth={marketBreadth} />
        <MarketEmotionDashboard marketBreadth={marketBreadth} sectorRelativeStrength={sectorRelativeStrength} />
        <KeyLevelAlerts alerts={keyLevelAlerts} />
        <InstrumentSyncProgress status={instrumentSyncStatus} loading={loading === "sync"} />
        <p className="hint">“更新股票库”只更新全市场基础资料，不会直接买卖股票；平时看信号点“手动刷新”即可。</p>
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

      <div className="panel" style={MONITOR_WATCH_STYLE}>
        <PanelTitle title="已持仓做T信号扫描" actions={<span className="muted">{watchCards.length} 个自选 / {runtime?.database_backend ?? "runtime"} </span>} />
        <StockCardList>
          {watchCards.length ? watchCards.map((stock) => (
            <StockCard
              key={stock.symbol}
              stock={stock}
              actions={["详情", "分析", "编辑", "移除"]}
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
    <Row gutter={[8, 8]} style={{ marginTop: 10 }}>
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
        styles={{ header: { minHeight: 34, padding: "0 10px" }, body: { padding: 8 } }}
        title="市场情绪与龙头强度"
        extra={<Tag color="blue">{marketBreadth?.emotion_temperature_text || marketBreadth?.state_text || "等待情绪数据"}</Tag>}
      >
        <Row gutter={[10, 10]} align="stretch">
          <Col xs={24} md={10} style={{ display: "flex" }}>
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
          <Col xs={24} md={14} style={{ display: "flex" }}>
            <Space direction="vertical" size={3} style={{ width: "100%" }}>
            {leaders.length ? leaders.map((item) => (
              <Flex
                gap={8}
                justify="space-between"
                key={`${item.sector_name}-${item.symbol}`}
                style={{ background: "#fff", borderRadius: 6, padding: "3px 6px" }}
              >
                <Typography.Text strong style={{ fontSize: 11.5 }}>{item.name}</Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 10.5 }}>
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
      style={{ bottom: 10, maxWidth: "min(300px, calc(100vw - 20px))", position: "fixed", right: 10, zIndex: 60 }}
    >
      {triggered.map((item) => (
        <Alert
          key={item.symbol}
          type="warning"
          showIcon
          style={{ padding: "6px 8px" }}
          message={<span style={{ fontSize: 12 }}>{item.name} 接近关键价位</span>}
          description={<span style={{ fontSize: 11 }}>{item.alert_text || `现价 ${formatPrice(item.latest_price)}`}</span>}
        />
      ))}
    </Space>
  );
}
