import { useMemo, useState } from "react";
import type {
  PaperAgentRun,
  PaperGroupedPerformance,
  PaperLedgerRepairResponse,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperSectorEtfT0Performance,
  PaperStockPnlItem,
  PaperStockPnlSummary,
  PaperTagPerformance,
  PaperTrade,
  PaperTradeTag,
  RiskEventItem,
} from "../../types";
import { PaperLedgerRepairPanel } from "./PaperLedgerRepairPanel";
import { PaperPositionDetailsPanel } from "./PaperPositionDetailsPanel";
import {
  AgentRunList,
  GroupedPerformanceTable,
  PerformancePills,
  RiskEventList,
  SectorEtfT0PerformancePanel,
  TagPerformanceStrip,
} from "./PaperTradingPerformance";
import { formatPaperDateTime } from "./paperTradingFormatters";
import { EmptyState } from "./WorkspaceComponents";
import { formatInteger, formatPrice } from "./workspaceFormatters";

type DetailTabKey = "orders" | "trades" | "pnl" | "strategy" | "risk" | "diagnostic";

export function PaperDetailTabs(props: PaperDetailTabsProps) {
  const [tab, setTab] = useState<DetailTabKey>("orders");
  const tabs = useMemo(() => buildTabs(props), [props]);

  return (
    <section className="panel paper-detail-tabs">
      <div className="panel-title">
        <h2>详情信息</h2>
        <span className="hint">低频信息统一收纳，避免首屏堆满。</span>
      </div>
      <div className="paper-tab-strip" role="tablist" aria-label="模拟盘详情切换">
        {tabs.map((item) => (
          <button
            key={item.key}
            type="button"
            className={tab === item.key ? "active" : ""}
            onClick={() => setTab(item.key)}
            role="tab"
            aria-selected={tab === item.key}
          >
            <strong>{item.label}</strong>
            <span>{item.hint}</span>
          </button>
        ))}
      </div>
      <div className="paper-tab-panel" role="tabpanel">
        {tab === "orders" ? <OrdersTab orders={props.orders} loading={props.loading} /> : null}
        {tab === "trades" ? (
          <TradesTab
            trades={props.trades}
            performance={props.performance}
            tagPerformance={props.tagPerformance}
            tradeTags={props.tradeTags}
            onAddTradeTag={props.onAddTradeTag}
            onDeleteTradeTag={props.onDeleteTradeTag}
            loading={props.loading}
          />
        ) : null}
        {tab === "pnl" ? (
          <PaperPositionDetailsPanel
            positions={props.positions}
            orders={props.orders}
            trades={props.trades}
            stockPnl={props.stockPnl}
            stockPnlSummary={props.stockPnlSummary}
            loading={props.loading}
            embedded
          />
        ) : null}
        {tab === "strategy" ? (
          <StrategyTab
            strategyPerformance={props.strategyPerformance}
            marketPerformance={props.marketPerformance}
            sectorEtfT0Performance={props.sectorEtfT0Performance}
          />
        ) : null}
        {tab === "risk" ? (
          <RiskTab
            riskEvents={props.riskEvents}
            autoTradingRuns={props.autoTradingRuns}
          />
        ) : null}
        {tab === "diagnostic" ? (
          <DiagnosticTab
            ledgerRepairStatus={props.ledgerRepairStatus}
            canManageReconcile={props.canManageReconcile}
            loading={props.loading}
            onRefreshLedgerRepair={props.onRefreshLedgerRepair}
            onApplyLedgerRepair={props.onApplyLedgerRepair}
          />
        ) : null}
      </div>
    </section>
  );
}

interface PaperDetailTabsProps {
  positions: PaperPosition[];
  orders: PaperOrder[];
  trades: PaperTrade[];
  stockPnl: PaperStockPnlItem[];
  stockPnlSummary: PaperStockPnlSummary | null;
  performance: PaperPerformance | null;
  sectorEtfT0Performance: PaperSectorEtfT0Performance | null;
  strategyPerformance: PaperGroupedPerformance[];
  marketPerformance: PaperGroupedPerformance[];
  tagPerformance: PaperTagPerformance[];
  tradeTags: Record<number, PaperTradeTag[]>;
  riskEvents: RiskEventItem[];
  autoTradingRuns: PaperAgentRun[];
  ledgerRepairStatus?: PaperLedgerRepairResponse | null;
  canManageReconcile?: boolean;
  loading: boolean;
  onRefreshLedgerRepair?: () => void | Promise<void>;
  onApplyLedgerRepair?: () => void | Promise<void>;
  onAddTradeTag: (tradeId: number, tag: string) => void;
  onDeleteTradeTag: (tradeId: number, tagId: number) => void;
}

function buildTabs(props: PaperDetailTabsProps) {
  return [
    { key: "orders", label: "委托记录", hint: `${props.orders.length} 条` },
    { key: "trades", label: "成交记录", hint: `${props.trades.length} 条` },
    { key: "pnl", label: "个股盈亏", hint: `${props.stockPnl.length} 只` },
    { key: "strategy", label: "策略绩效", hint: `${props.strategyPerformance.length + props.marketPerformance.length} 组` },
    { key: "risk", label: "风险与日志", hint: `${props.riskEvents.length} 个风险` },
    { key: "diagnostic", label: "对账诊断", hint: props.canManageReconcile ? "可修复" : "只读" },
  ] as Array<{ key: DetailTabKey; label: string; hint: string }>;
}

function OrdersTab({ orders, loading }: { orders: PaperOrder[]; loading: boolean }) {
  if (loading) return <EmptyState text="委托记录加载中…" />;
  return (
    <div className="paper-tab-scroll">
      <div className="paper-table-head paper-order-head">
        <span>标的</span>
        <span>方向/类型</span>
        <span>状态</span>
        <span>数量</span>
        <span>成交</span>
      </div>
      <div className="line-list">
        {orders.length ? orders.map((item) => <OrderRow key={item.id} item={item} />) : <EmptyState text="暂无委托" />}
      </div>
    </div>
  );
}

function TradesTab({
  trades,
  performance,
  tagPerformance,
  tradeTags,
  loading,
  onAddTradeTag,
  onDeleteTradeTag,
}: {
  trades: PaperTrade[];
  performance: PaperPerformance | null;
  tagPerformance: PaperTagPerformance[];
  tradeTags: Record<number, PaperTradeTag[]>;
  loading: boolean;
  onAddTradeTag: (tradeId: number, tag: string) => void;
  onDeleteTradeTag: (tradeId: number, tagId: number) => void;
}) {
  if (loading) return <EmptyState text="成交记录加载中…" />;
  return (
    <div className="paper-tab-scroll">
      <PerformancePills performance={performance} />
      <TagPerformanceStrip items={tagPerformance} />
      <div className="paper-table-head paper-trade-head with-tags">
        <span>标的</span>
        <span>方向</span>
        <span>数量</span>
        <span>价格</span>
        <span>时间</span>
        <span>标签</span>
      </div>
      <div className="line-list">
        {trades.length ? trades.map((item) => (
          <TradeRow
            key={item.id}
            item={item}
            tags={tradeTags[item.id] ?? []}
            onAddTag={onAddTradeTag}
            onDeleteTag={onDeleteTradeTag}
          />
        )) : <EmptyState text="暂无成交" />}
      </div>
    </div>
  );
}

function StrategyTab({
  strategyPerformance,
  marketPerformance,
  sectorEtfT0Performance,
}: {
  strategyPerformance: PaperGroupedPerformance[];
  marketPerformance: PaperGroupedPerformance[];
  sectorEtfT0Performance: PaperSectorEtfT0Performance | null;
}) {
  return (
    <div className="paper-tab-scroll">
      <section className="paper-detail-card">
        <div className="paper-detail-card-title">
          <strong>按策略</strong>
          <span>看哪个策略赚钱，哪个策略拖后腿。</span>
        </div>
        <GroupedPerformanceTable items={strategyPerformance} emptyText="暂无策略绩效" />
      </section>
      <section className="paper-detail-card">
        <div className="paper-detail-card-title">
          <strong>按市场状态</strong>
          <span>判断不同环境下表现是否稳定。</span>
        </div>
        <GroupedPerformanceTable items={marketPerformance} emptyText="暂无市场状态绩效" />
      </section>
      <section className="paper-detail-card">
        <div className="paper-detail-card-title">
          <strong>行业 ETF T+0</strong>
          <span>单独查看 ETF 做T 自动执行结果。</span>
        </div>
        <SectorEtfT0PerformancePanel item={sectorEtfT0Performance} />
      </section>
    </div>
  );
}

function RiskTab({
  riskEvents,
  autoTradingRuns,
}: {
  riskEvents: RiskEventItem[];
  autoTradingRuns: PaperAgentRun[];
}) {
  return (
    <div className="paper-tab-scroll">
      <section className="paper-detail-card">
        <div className="paper-detail-card-title">
          <strong>风险待办</strong>
          <span>只保留需要你处理的风险。</span>
        </div>
        <RiskEventList items={riskEvents} />
        {!riskEvents.length ? <EmptyState text="暂无风险待办" /> : null}
      </section>
      <section className="paper-detail-card">
        <div className="paper-detail-card-title">
          <strong>系统日志</strong>
          <span>最近 5 次自动交易执行记录。</span>
        </div>
        <AgentRunList items={autoTradingRuns} />
      </section>
    </div>
  );
}

function DiagnosticTab({
  ledgerRepairStatus,
  canManageReconcile,
  loading,
  onRefreshLedgerRepair,
  onApplyLedgerRepair,
}: {
  ledgerRepairStatus?: PaperLedgerRepairResponse | null;
  canManageReconcile?: boolean;
  loading: boolean;
  onRefreshLedgerRepair?: () => void | Promise<void>;
  onApplyLedgerRepair?: () => void | Promise<void>;
}) {
  if (!canManageReconcile || !onRefreshLedgerRepair || !onApplyLedgerRepair) {
    return <EmptyState text="当前账号没有对账修复权限。" />;
  }
  return (
    <div className="paper-tab-scroll">
      <PaperLedgerRepairPanel
        loading={loading}
        status={ledgerRepairStatus ?? null}
        onRefresh={() => void onRefreshLedgerRepair()}
        onApply={() => void onApplyLedgerRepair()}
      />
    </div>
  );
}

function OrderRow({ item }: { item: PaperOrder }) {
  const statusTone = orderStatusTone(item.status);
  const sideText = item.side === "buy" ? "买入" : "卖出";
  const orderTypeText = item.order_type === "market" ? "市价" : "限价";
  return (
    <article className={`paper-row paper-order-row${item.reject_reason ? " has-note" : ""}`}>
      <div className="paper-stock-name">
        <strong>{item.symbol}</strong>
        <span>{item.name || item.strategy_key || "--"}</span>
      </div>
      <span className={`status-chip ${item.side === "buy" ? "up" : "down"}`}>{sideText} · {orderTypeText}</span>
      <span className={`status-chip ${statusTone}`}>{orderStatusText(item.status)}</span>
      <span className="cell-number">{formatInteger(item.quantity)} 股</span>
      <span className="cell-number">{formatPrice(item.avg_fill_price)}</span>
      {item.reject_reason ? <span className="paper-order-reason warn">原因：{item.reject_reason}</span> : null}
    </article>
  );
}

function TradeRow({
  item,
  tags,
  onAddTag,
  onDeleteTag,
}: {
  item: PaperTrade;
  tags: PaperTradeTag[];
  onAddTag: (tradeId: number, tag: string) => void;
  onDeleteTag: (tradeId: number, tagId: number) => void;
}) {
  const quickTags = ["止盈", "止损", "做T", "计划外"].filter((tag) => !tags.some((entry) => entry.tag === tag));
  const reasonText = item.side === "buy" ? item.entry_reason : item.exit_reason;
  return (
    <article className="paper-row paper-trade-row with-tags">
      <div className="paper-stock-name">
        <strong>{item.symbol}</strong>
        <span>{item.strategy_key || "未标注"}</span>
        <span className="paper-trade-reason">{reasonText || (item.side === "buy" ? "买入原因未记录" : "退出原因未记录")}</span>
        {item.commission_warning ? <span className="paper-trade-reason warn">{item.commission_warning}</span> : null}
      </div>
      <span className={`status-chip ${item.side === "buy" ? "up" : "down"}`}>{item.side === "buy" ? "买入" : "卖出"}</span>
      <span className="cell-number">{formatInteger(item.quantity)} 股</span>
      <span className="cell-number">{formatPrice(item.price)}</span>
      <span>{formatPaperDateTime(item.trade_time)}</span>
      <div className="paper-trade-tags">
        {tags.map((tag) => (
          <button type="button" className="paper-tag-chip" key={tag.id} onClick={() => onDeleteTag(item.id, tag.id)} title="点击删除标签">
            {tag.tag} ×
          </button>
        ))}
        {quickTags.slice(0, tags.length ? 1 : 2).map((tag) => (
          <button type="button" className="paper-tag-add" key={tag} onClick={() => onAddTag(item.id, tag)}>
            +{tag}
          </button>
        ))}
      </div>
    </article>
  );
}

function orderStatusText(status: PaperOrder["status"]): string {
  if (status === "pending") return "待成交";
  if (status === "filled") return "已成交";
  if (status === "partial") return "部分成交";
  if (status === "rejected") return "已拒绝";
  if (status === "cancelled") return "已撤销";
  return status;
}

function orderStatusTone(status: PaperOrder["status"]) {
  if (status === "pending" || status === "partial") return "warn";
  if (status === "filled") return "down";
  if (status === "rejected") return "up";
  return "neutral";
}
