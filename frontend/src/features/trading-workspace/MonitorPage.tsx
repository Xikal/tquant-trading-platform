import { memo, useMemo } from "react";
import type { LowBuyPriorityBoardResult, MarketBreadth, RuntimeStatus } from "../../types";
import { EditableGrid, EmptyState, FamilyStrip, InfoPill, MetricGrid, PanelTitle, StockCard } from "./WorkspaceComponents";
import { average, formatPct, riskLevelText, shortTime } from "./workspaceFormatters";
import type { MetricItem, StockCardView, WatchDraft } from "./workspaceTypes";

export interface MonitorPageProps {
  priorityBoard: LowBuyPriorityBoardResult | null;
  marketBreadth: MarketBreadth | null;
  priorityCards: StockCardView[];
  watchCards: StockCardView[];
  runtime: RuntimeStatus | null;
  watchDraft: WatchDraft;
  setWatchDraft: (draft: WatchDraft) => void;
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
}

export const MonitorPage = memo(function MonitorPage({
  priorityBoard,
  marketBreadth,
  priorityCards,
  watchCards,
  runtime,
  watchDraft,
  setWatchDraft,
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
}: MonitorPageProps) {
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
        <PanelTitle title="录入底仓约束" />
        <p className="hint">代码、底仓、可卖、成本价决定做T信号是否可执行。A股 T+1 下，当日买入通常次日才进入可用数量。</p>
        <EditableGrid
          fields={[
            ["证券代码", watchDraft.symbol, (value) => setWatchDraft({ ...watchDraft, symbol: value })],
            ["底仓数量", watchDraft.base_position, (value) => setWatchDraft({ ...watchDraft, base_position: value })],
            ["可卖数量", watchDraft.available_position, (value) => setWatchDraft({ ...watchDraft, available_position: value })],
            ["成本价", watchDraft.cost_basis, (value) => setWatchDraft({ ...watchDraft, cost_basis: value })],
            ["备注", watchDraft.memo, (value) => setWatchDraft({ ...watchDraft, memo: value })],
            ["名称", watchDraft.name, (value) => setWatchDraft({ ...watchDraft, name: value })],
          ]}
        />
        <button className="primary full" onClick={onAddWatchlist} disabled={loading === "watchlist"}>
          {watchDraft.symbol.trim() ? "保存持仓" : "加入自选监控"}
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
