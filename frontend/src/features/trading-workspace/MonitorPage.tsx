import { memo, useMemo } from "react";
import type { LowBuyPriorityBoardResult, MarketBreadth, PairedHedgeResearchResponse, RuntimeStatus, SectorEtfT0Response } from "../../types";
import { NumberField, SearchField, TextField } from "../../components/shared/FormFields";
import { EmptyState, FamilyStrip, InfoPill, MetricGrid, PanelTitle, StockCard } from "./WorkspaceComponents";
import { average, formatPct, formatPrice, riskLevelText, shortTime } from "./workspaceFormatters";
import type { MetricItem, StockCardView, WatchDraft } from "./workspaceTypes";

export interface MonitorPageProps {
  priorityBoard: LowBuyPriorityBoardResult | null;
  marketBreadth: MarketBreadth | null;
  sectorEtfT0: SectorEtfT0Response | null;
  pairedHedge: PairedHedgeResearchResponse | null;
  priorityCards: StockCardView[];
  watchCards: StockCardView[];
  runtime: RuntimeStatus | null;
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
  sectorEtfT0,
  pairedHedge,
  priorityCards,
  watchCards,
  runtime,
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
  const metrics: MetricItem[] = useMemo(() => {
    const executableCount = watchCards.filter((card) => card.actionText !== "暂不操作").length;
    const avgScore = average(priorityCards.map((card) => Number(card.scoreText))).toFixed(1);
    return [
      { label: "已持仓自选", value: String(watchCards.length), tone: "neutral" },
      { label: "可执行做T", value: String(executableCount), tone: executableCount ? "up" : "neutral" },
      { label: "高风险席位", value: String(watchCards.filter((card) => card.riskText.includes("高")).length), tone: "down" },
      { label: "平均质量分", value: Number.isFinite(Number(avgScore)) ? avgScore : "--", tone: "warn" },
      { label: "榜单 / 刷新", value: `${priorityBoard?.items.length ?? 0} / ${shortTime(priorityBoard?.updated_at) || "--"}`, tone: "neutral" },
    ];
  }, [priorityBoard?.items.length, priorityBoard?.updated_at, priorityCards, watchCards]);
  return (
    <section className="page-grid monitor-grid">
      <div className="panel monitor-summary">
        <PanelTitle
          title="盘中监控摘要"
          actions={
            <>
              <button onClick={onSync} disabled={loading === "sync"}>同步全市场标的</button>
              <button onClick={onRefresh} disabled={loading === "monitor"}>手动刷新</button>
            </>
          }
        />
        <MetricGrid items={metrics} />
        <MarketBreadthStrip marketBreadth={marketBreadth} />
      </div>

      <aside className="panel monitor-input">
        <PanelTitle
          title={isEditing ? "编辑持仓约束" : "录入底仓约束"}
          actions={isEditing ? <button type="button" onClick={onCancelEdit}>取消编辑</button> : null}
        />
        <p className="hint">
          {isEditing
            ? `正在编辑 ${editingWatchSymbol}，修改后点击“更新持仓”。`
            : "代码、底仓、可卖、成本价决定做T信号是否可执行。A股 T+1 下，当日买入通常次日才进入可用数量。"}
        </p>
        <div className="compact-form-grid">
          <SearchField
            label="证券代码"
            value={watchDraft.symbol}
            placeholder="代码或名称"
            disabled={isEditing}
            onChange={(value) => setWatchDraft({ ...watchDraft, symbol: value })}
          />
          <NumberField label="底仓数量" value={watchDraft.base_position} onChange={(event) => setWatchDraft({ ...watchDraft, base_position: event.target.value })} />
          <NumberField label="可卖数量" value={watchDraft.available_position} onChange={(event) => setWatchDraft({ ...watchDraft, available_position: event.target.value })} />
          <NumberField label="成本价" value={watchDraft.cost_basis} onChange={(event) => setWatchDraft({ ...watchDraft, cost_basis: event.target.value })} />
          <TextField label="备注" value={watchDraft.memo} onChange={(event) => setWatchDraft({ ...watchDraft, memo: event.target.value })} />
          <TextField label="名称" value={watchDraft.name} onChange={(event) => setWatchDraft({ ...watchDraft, name: event.target.value })} />
        </div>
        <button className="primary full" onClick={onAddWatchlist} disabled={loading === "watchlist"}>
          {loading === "watchlist" ? "保存中..." : isEditing ? "更新持仓" : watchDraft.symbol.trim() ? "保存持仓" : "加入自选监控"}
        </button>
      </aside>

      <div className="panel monitor-priority">
        <PanelTitle
          title="全策略优先级榜"
          actions={
            <>
              <button className="gold" onClick={onAi} disabled={loading === "ai"}>{loading === "ai" ? "解读中..." : "解读榜单"}</button>
              <button onClick={onGoPlaybook}>去选股宝典</button>
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
          <InfoPill label="候选覆盖" value={`榜单 ${priorityBoard?.total_candidates ?? 0} / 确定 ${priorityBoard?.immediate_count ?? 0} / 观察 ${priorityBoard?.focus_count ?? 0}`} />
        </div>
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

function dataQualityTone(value?: string | null): "up" | "warn" | "down" | "neutral" {
  if (value === "ok") return "up";
  if (value === "partial" || value === "stale" || value === "degraded") return "warn";
  if (value === "limited" || value === "unavailable") return "down";
  return "neutral";
}

function formatRatioPct(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const normalized = Math.abs(value) <= 1 ? value * 100 : value;
  return `${normalized.toFixed(0)}%`;
}
