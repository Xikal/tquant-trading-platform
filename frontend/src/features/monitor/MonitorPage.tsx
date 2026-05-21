import { memo, useMemo } from "react";
import { Button } from "antd";
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
import { EmptyState, FamilyStrip, InfoPill, MetricGrid, PanelTitle, StockCard } from "../workspace-shared/WorkspaceComponents";
import { formatPct, formatPrice, riskLevelText, shortTime } from "../workspace-shared/workspaceFormatters";
import type { MetricItem, StockCardView, WatchDraft } from "../workspace-shared/workspaceTypes";

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
  const isEditing = Boolean(editingWatchSymbol);
  const primaryAction = useMemo(() => resolveTodayAction(watchCards, priorityCards, priorityBoard), [watchCards, priorityCards, priorityBoard]);
  const priorityNotice = useMemo(() => buildPriorityNotice(priorityBoard, priorityCards.length), [priorityBoard, priorityCards.length]);
  const metrics: MetricItem[] = useMemo(
    () => buildMonitorMetrics({ priorityBoard, priorityCards, watchCards }),
    [priorityBoard, priorityCards, watchCards]
  );
  const instrumentSyncActive =
    loading === "sync" || instrumentSyncStatus?.status === "queued" || instrumentSyncStatus?.status === "running";
  return (
    <section className="page-grid monitor-grid">
      <div className="panel monitor-summary">
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
        <div className={`decision-brief monitor-primary-action-card ${primaryAction.tone}`}>
          <span>今天最重要的 1 件事</span>
          <strong>{primaryAction.title}</strong>
          <small>{primaryAction.detail}</small>
          <Button type="primary" size="small" onClick={primaryAction.source === "holding" ? onRefresh : onGoPlaybook}>
            {primaryAction.source === "holding" ? "刷新确认" : "查看候选"}
          </Button>
        </div>
        <details className="monitor-metric-details">
          <summary>展开盘面数字摘要</summary>
          <MetricGrid items={metrics} />
        </details>
        <MarketBreadthStrip marketBreadth={marketBreadth} />
        <MarketEmotionDashboard marketBreadth={marketBreadth} sectorRelativeStrength={sectorRelativeStrength} />
        <KeyLevelAlerts alerts={keyLevelAlerts} />
        <InstrumentSyncProgress status={instrumentSyncStatus} loading={loading === "sync"} />
        <p className="hint">“更新股票库”只更新全市场基础资料，不会直接买卖股票；平时看信号点“手动刷新”即可。</p>
      </div>

      <aside className="panel monitor-input">
        <PanelTitle
          title={isEditing ? "编辑持仓约束" : "录入底仓约束"}
          actions={isEditing ? <Button htmlType="button" onClick={onCancelEdit}>取消编辑</Button> : null}
        />
        <p className="hint">
          {isEditing
            ? `正在编辑 ${editingWatchSymbol}，修改后点击“更新持仓”。`
            : "代码、底仓、可卖、成本价决定做T信号是否可执行。A股 T+1 下，当日买入通常次日才进入可用数量。"}
        </p>
        <MonitorHoldingWizard draft={watchDraft} editing={isEditing} />
        <div className="compact-form-grid">
          <SearchField
            label="证券代码"
            value={watchDraft.symbol}
            placeholder="代码或名称"
            disabled={isEditing}
            onChange={(value) => setWatchDraft({ ...watchDraft, symbol: value })}
          />
          <NumberField label="底仓数量" hint="例：1000，代表当前总持仓。" value={watchDraft.base_position} onChange={(event) => setWatchDraft({ ...watchDraft, base_position: event.target.value })} />
          <NumberField label="可卖数量" hint="例：600，今天可先卖的底仓数量。" value={watchDraft.available_position} onChange={(event) => setWatchDraft({ ...watchDraft, available_position: event.target.value })} />
          <NumberField label="成本价" hint="例：12.35，用于计算盈亏和止损。" value={watchDraft.cost_basis} onChange={(event) => setWatchDraft({ ...watchDraft, cost_basis: event.target.value })} />
          <TextField label="备注" hint="例：主线前排、只做正T。" value={watchDraft.memo} onChange={(event) => setWatchDraft({ ...watchDraft, memo: event.target.value })} />
          <TextField label="名称" hint="可留空，系统会自动补全。" value={watchDraft.name} onChange={(event) => setWatchDraft({ ...watchDraft, name: event.target.value })} />
        </div>
        <Button className="primary full" type="primary" onClick={onAddWatchlist} loading={loading === "watchlist"}>
          {loading === "watchlist" ? "保存中..." : isEditing ? "更新持仓" : watchDraft.symbol.trim() ? "保存持仓" : "加入自选监控"}
        </Button>
      </aside>

      <div className="panel monitor-priority">
        <PanelTitle
          title="全策略优先级榜"
          actions={
            <>
              <Button className="gold" onClick={onAi} loading={loading === "ai"}>{loading === "ai" ? "解读中..." : "解读榜单"}</Button>
              <Button onClick={onGoPlaybook}>去选股宝典</Button>
            </>
          }
        />
        <div className="context-row">
          <InfoPill label="今日方向" value={priorityBoard?.directional_bias_text ?? "--"} />
          <InfoPill label="市场状态" value={priorityBoard?.market_state_text ?? "--"} />
          <InfoPill label="热点板块" value={(priorityBoard?.hot_industries ?? []).slice(0, 4).join(" / ") || "--"} />
          <InfoPill label="宽度情绪" value={`上涨 ${formatPct(priorityBoard?.stock_up_ratio, 0)} / 涨停 ${priorityBoard?.limit_up_count ?? "--"}`} />
          <InfoPill label="组合风险" value={priorityBoard?.portfolio_risk?.risk_level ? riskLevelText(priorityBoard.portfolio_risk.risk_level) : "--"} />
          <InfoPill label="快照日期" value={`${priorityBoard?.latest_trade_date ?? "--"} / 更新 ${shortTime(priorityBoard?.updated_at) || "--"}`} />
          <InfoPill label="数据状态" value={priorityBoard?.data_quality_text ?? "--"} tone={dataQualityTone(priorityBoard?.data_quality)} />
          <InfoPill label="今日分层" value={`确认 ${priorityBoard?.immediate_count ?? 0} / 观察 ${(priorityBoard?.focus_count ?? 0) + (priorityBoard?.track_count ?? 0)} / 榜单 ${priorityBoard?.total_candidates ?? 0}`} tone={(priorityBoard?.immediate_count ?? 0) ? "up" : "warn"} />
        </div>
        {priorityNotice ? (
          <div className={`board-warning ${priorityNotice.tone === "danger" ? "danger" : ""}`}>
            <strong>{priorityNotice.title}</strong>
            <span>{priorityNotice.detail}</span>
          </div>
        ) : null}
        {priorityBoard?.snapshot_warning ? <div className="board-warning">{priorityBoard.snapshot_warning}</div> : null}
        <FamilyStrip priorityBoard={priorityBoard} />
        <div className="stock-list compact">
          {priorityCards.length ? priorityCards.slice(0, 12).map((stock) => (
            <StockCard
              key={`${stock.symbol}-${stock.actionText}`}
              stock={stock}
              actions={["详情", "分析"]}
              onAction={(action) => (action === "分析" ? onAnalyze(stock) : onSelect(stock))}
            />
          )) : <EmptyState text="暂无优先级榜单结果，等待后台全量深筛缓存完成。" />}
        </div>
      </div>

      <div className="panel monitor-watch">
        <PanelTitle title="已持仓做T信号扫描" actions={<span className="muted">{watchCards.length} 个自选 / {runtime?.database_backend ?? "runtime"} </span>} />
        <div className="stock-list">
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
        </div>
      </div>

      <div className="panel monitor-etf-t0">
        <PanelTitle title="行业 ETF 做T替代" actions={<span className="muted">利用 ETF T+0 特性，降低个股隔夜风险</span>} />
        {pairedHedge?.disclaimer ? <div className="board-warning danger">{pairedHedge.disclaimer}</div> : null}
        <div className="stock-list compact">
          {(sectorEtfT0?.opportunities ?? []).length ? sectorEtfT0!.opportunities.slice(0, 6).map((item) => (
            <article className="stock-card compact-card" key={`${item.etf_symbol}-${item.source_signal_symbol}`}>
              <div className="stock-card-head">
                <div>
                  <strong>{item.etf_name}</strong>
                  <span>{item.etf_symbol} · 来源 {item.source_signal_name}</span>
                </div>
                <span className={`pill ${item.bias === "positive_t" ? "up" : item.bias === "negative_t" ? "down" : "neutral"}`}>{item.bias_text}</span>
              </div>
              <div className="stock-card-meta">
                <span>板块：{item.sector_name || "未分类"}</span>
                <span>信心：{formatPct(item.confidence, 0)}</span>
                <span>ETF价：{formatPrice(item.last_price)}</span>
                <span>ETF涨跌：{formatPct(item.change_pct)}</span>
              </div>
              <p className="hint">{item.reason}</p>
              <p className="hint">买点 {item.entry_zone || "--"}；卖点 {item.sell_zone || "--"}；风险：{item.risk}</p>
            </article>
          )) : <EmptyState text="暂无 ETF 做T替代信号。只有板块低吸/热点信号明确时才展示。" />}
        </div>
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
    <div className="market-breadth-strip">
      <InfoPill label="市场宽度" value={formatRatioPct(marketBreadth.stock_up_ratio)} />
      <InfoPill label="中位涨跌" value={formatPct(marketBreadth.stock_median_change)} />
      <InfoPill label="涨停/跌停" value={`${marketBreadth.limit_up_count} / ${marketBreadth.limit_down_count ?? "--"}`} />
      <InfoPill label="炸板率" value={formatRatioPct(marketBreadth.broken_board_ratio)} />
      <InfoPill label="连板高度" value={String(marketBreadth.board_height || "--")} />
      <InfoPill label="数据质量" value={marketBreadth.data_quality_text || "--"} tone={dataQualityTone(marketBreadth.data_quality)} />
    </div>
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
    <div className="market-emotion-dashboard">
      <div className="emotion-header">
        <strong>市场情绪与龙头强度</strong>
        <span>{marketBreadth?.emotion_temperature_text || marketBreadth?.state_text || "等待情绪数据"}</span>
      </div>
      <div className="emotion-grid">
        <div className="limit-board-bars" aria-label="涨停连板高度分布">
          {distribution.map((item) => (
            <span key={item.label} style={{ height: `${item.height}%` }} title={`${item.label}：相对高度 ${item.height}%`}>
              <i>{item.label}</i>
            </span>
          ))}
        </div>
        <div className="leader-rank-mini">
          {leaders.length ? leaders.map((item) => (
            <span key={`${item.sector_name}-${item.symbol}`}>
              <b>{item.name}</b>
              <em>{item.sector_name} #{item.rank} · 龙头分 {item.leader_score.toFixed(0)}</em>
            </span>
          )) : <small>暂无板块龙头强度数据</small>}
        </div>
      </div>
    </div>
  );
}

function KeyLevelAlerts({ alerts }: { alerts: IntradayKeyLevelResponse[] }) {
  const triggered = alerts.filter((item) => item.alert_triggered).slice(0, 4);
  if (!triggered.length) {
    return null;
  }
  return (
    <div className="key-level-alerts" role="alert" aria-live="polite">
      {triggered.map((item) => (
        <span className="key-level-alert" key={item.symbol}>
          {item.name} 接近关键价位：{item.alert_text || `现价 ${formatPrice(item.latest_price)}`}
        </span>
      ))}
    </div>
  );
}
