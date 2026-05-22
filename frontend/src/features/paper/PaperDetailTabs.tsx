import { useMemo } from "react";
import { Button, Tabs } from "antd";
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
import { EmptyState } from "../workspace-shared/WorkspaceComponents";
import { formatInteger, formatPrice } from "../workspace-shared/workspaceFormatters";
import { DataTable } from "../../ui/table/DataTable";
import { usePaperUiStore, type PaperDetailTabKey } from "../../stores/paperUiStore";

export function PaperDetailTabs(props: PaperDetailTabsProps) {
  const tab = usePaperUiStore((state) => state.detailTab);
  const setTab = usePaperUiStore((state) => state.setDetailTab);
  const tabs = useMemo(() => buildTabs(props), [props]);

  return (
    <section className="panel paper-detail-tabs">
      <div className="panel-title">
        <h2>详情信息</h2>
        <span className="hint">低频信息统一收纳，避免首屏堆满。</span>
      </div>
      <Tabs
        className="paper-detail-antd-tabs"
        activeKey={tab}
        onChange={(key) => setTab(key as PaperDetailTabKey)}
        items={tabs.map((item) => ({
          key: item.key,
          label: (
            <span className="paper-tab-label">
              <strong>{item.label}</strong>
              <small>{item.hint}</small>
            </span>
          ),
        }))}
      />
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
  ] as Array<{ key: PaperDetailTabKey; label: string; hint: string }>;
}

function OrdersTab({ orders, loading }: { orders: PaperOrder[]; loading: boolean }) {
  return (
    <DataTable<PaperOrder>
      rowKey="id"
      loading={loading}
      dataSource={orders}
      scroll={{ y: 320, x: 760 }}
      columns={[
        {
          title: "标的",
          dataIndex: "symbol",
          render: (_, item) => (
            <div className="paper-stock-name">
              <strong>{item.symbol}</strong>
              <span>{item.name || item.strategy_key || "--"}</span>
              {item.reject_reason ? <small className="warn">原因：{item.reject_reason}</small> : null}
            </div>
          ),
        },
        {
          title: "方向/类型",
          render: (_, item) => (
            <span className={`status-chip ${item.side === "buy" ? "up" : "down"}`}>
              {item.side === "buy" ? "买入" : "卖出"} · {item.order_type === "market" ? "市价" : "限价"}
            </span>
          ),
        },
        {
          title: "状态",
          dataIndex: "status",
          render: (status: PaperOrder["status"]) => <span className={`status-chip ${orderStatusTone(status)}`}>{orderStatusText(status)}</span>,
        },
        {
          title: "数量",
          dataIndex: "quantity",
          align: "right",
          render: (value: number) => `${formatInteger(value)} 股`,
        },
        {
          title: "成交价",
          dataIndex: "avg_fill_price",
          align: "right",
          render: (value?: number | null) => formatPrice(value),
        },
      ]}
    />
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
  return (
    <div className="paper-tab-scroll">
      <PerformancePills performance={performance} />
      <TagPerformanceStrip items={tagPerformance} />
      <DataTable<PaperTrade>
        rowKey="id"
        loading={loading}
        dataSource={trades}
        scroll={{ y: 340, x: 980 }}
        columns={[
          {
            title: "标的",
            dataIndex: "symbol",
            render: (_, item) => {
              const reasonText = item.side === "buy" ? item.entry_reason : item.exit_reason;
              return (
                <div className="paper-stock-name">
                  <strong>{item.symbol}</strong>
                  <span>{item.strategy_key || "未标注"}</span>
                  <small className={item.commission_warning ? "warn" : ""}>
                    {item.commission_warning || reasonText || (item.side === "buy" ? "买入原因未记录" : "退出原因未记录")}
                  </small>
                </div>
              );
            },
          },
          {
            title: "方向",
            dataIndex: "side",
            render: (side: PaperTrade["side"]) => <span className={`status-chip ${side === "buy" ? "up" : "down"}`}>{side === "buy" ? "买入" : "卖出"}</span>,
          },
          { title: "数量", dataIndex: "quantity", align: "right", render: (value: number) => `${formatInteger(value)} 股` },
          { title: "价格", dataIndex: "price", align: "right", render: (value?: number | null) => formatPrice(value) },
          { title: "时间", dataIndex: "trade_time", render: (value: string) => formatPaperDateTime(value) },
          {
            title: "标签",
            render: (_, item) => (
              <TradeTags
                item={item}
                tags={tradeTags[item.id] ?? []}
                onAddTag={onAddTradeTag}
                onDeleteTag={onDeleteTradeTag}
              />
            ),
          },
        ]}
      />
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

function TradeTags({
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
  return (
    <div className="paper-trade-tags">
      {tags.map((tag) => (
        <Button type="text" size="small" className="paper-tag-chip" key={tag.id} onClick={() => onDeleteTag(item.id, tag.id)} title="点击删除标签">
          {tag.tag} ×
        </Button>
      ))}
      {quickTags.slice(0, tags.length ? 1 : 2).map((tag) => (
        <Button type="text" size="small" className="paper-tag-add" key={tag} onClick={() => onAddTag(item.id, tag)}>
          +{tag}
        </Button>
      ))}
    </div>
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
