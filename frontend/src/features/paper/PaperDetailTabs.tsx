import { type ReactNode, useMemo } from "react";
import { Button, Card, Space, Tabs, Typography } from "antd";
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
    <Card
      title="详情信息"
      size="small"
      style={{ gridArea: "details" }}
      styles={{ body: { padding: 10 } }}
    >
      <Tabs
        size="small"
        activeKey={tab}
        onChange={(key) => setTab(key as PaperDetailTabKey)}
        tabBarStyle={{ marginBottom: 6 }}
        items={tabs.map((item) => ({
          key: item.key,
          label: (
            <Typography.Text strong style={{ fontSize: 12 }}>{item.label} <Typography.Text type="secondary" style={{ fontSize: 11 }}>{item.hint}</Typography.Text></Typography.Text>
          ),
        }))}
      />
      <div role="tabpanel" style={{ minHeight: 260 }}>
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
    </Card>
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
            <Space direction="vertical" size={0} style={{ minWidth: 0 }}>
              <strong>{item.symbol}</strong>
              <Typography.Text type="secondary" style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {item.name || item.strategy_key || "--"}
              </Typography.Text>
              {item.reject_reason ? <Typography.Text type="warning" style={{ fontSize: 11 }}>原因：{item.reject_reason}</Typography.Text> : null}
            </Space>
          ),
        },
        {
          title: "方向/类型",
          render: (_, item) => (
            <StatusChip tone={item.side === "buy" ? "up" : "down"}>
              {item.side === "buy" ? "买入" : "卖出"} · {item.order_type === "market" ? "市价" : "限价"}
            </StatusChip>
          ),
        },
        {
          title: "状态",
          dataIndex: "status",
          render: (status: PaperOrder["status"]) => <StatusChip tone={orderStatusTone(status)}>{orderStatusText(status)}</StatusChip>,
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
    <TabScroll>
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
                <Space direction="vertical" size={0} style={{ minWidth: 0 }}>
                  <strong>{item.symbol}</strong>
                  <Typography.Text type="secondary" style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {item.strategy_key || "未标注"}
                  </Typography.Text>
                  <Typography.Text type={item.commission_warning ? "warning" : "secondary"} style={{ fontSize: 11 }}>
                    {item.commission_warning || reasonText || (item.side === "buy" ? "买入原因未记录" : "退出原因未记录")}
                  </Typography.Text>
                </Space>
              );
            },
          },
          {
            title: "方向",
            dataIndex: "side",
            render: (side: PaperTrade["side"]) => <StatusChip tone={side === "buy" ? "up" : "down"}>{side === "buy" ? "买入" : "卖出"}</StatusChip>,
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
    </TabScroll>
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
    <TabScroll>
      <Card size="small" title="按策略" extra={<Typography.Text type="secondary">看哪个策略赚钱，哪个策略拖后腿。</Typography.Text>}>
        <GroupedPerformanceTable items={strategyPerformance} emptyText="暂无策略绩效" />
      </Card>
      <Card size="small" title="按市场状态" extra={<Typography.Text type="secondary">判断不同环境下表现是否稳定。</Typography.Text>}>
        <GroupedPerformanceTable items={marketPerformance} emptyText="暂无市场状态绩效" />
      </Card>
      <Card size="small" title="行业 ETF T+0" extra={<Typography.Text type="secondary">单独查看 ETF 做 T 自动执行结果。</Typography.Text>}>
        <SectorEtfT0PerformancePanel item={sectorEtfT0Performance} />
      </Card>
    </TabScroll>
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
    <TabScroll>
      <Card size="small" title="风险待办" extra={<Typography.Text type="secondary">只保留需要你处理的风险。</Typography.Text>}>
        <RiskEventList items={riskEvents} />
        {!riskEvents.length ? <EmptyState text="暂无风险待办" /> : null}
      </Card>
      <Card size="small" title="系统日志" extra={<Typography.Text type="secondary">最近 5 次自动交易执行记录。</Typography.Text>}>
        <AgentRunList items={autoTradingRuns} />
      </Card>
    </TabScroll>
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
    <TabScroll>
      <PaperLedgerRepairPanel
        loading={loading}
        status={ledgerRepairStatus ?? null}
        onRefresh={() => void onRefreshLedgerRepair()}
        onApply={() => void onApplyLedgerRepair()}
      />
    </TabScroll>
  );
}

function TabScroll({ children }: { children: ReactNode }) {
  return (
    <Space direction="vertical" size={12} style={{ display: "flex", maxHeight: 420, overflowY: "auto", paddingRight: 4 }}>
      {children}
    </Space>
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
    <Space wrap size={5}>
      {tags.map((tag) => (
        <Button
          type="text"
          size="small"
          key={tag.id}
          onClick={() => onDeleteTag(item.id, tag.id)}
          title="点击删除标签"
          style={{
            border: "1px solid rgba(31, 139, 76, 0.22)",
            borderRadius: 999,
            background: "#f2fbf5",
            color: "var(--price-down, #1f8b4c)",
            fontSize: 10,
            fontWeight: 800,
            padding: "2px 6px",
          }}
        >
          {tag.tag} ×
        </Button>
      ))}
      {quickTags.slice(0, tags.length ? 1 : 2).map((tag) => (
        <Button
          type="text"
          size="small"
          key={tag}
          onClick={() => onAddTag(item.id, tag)}
          style={{
            border: "1px dashed var(--line)",
            borderRadius: 999,
            background: "#fff",
            color: "var(--muted)",
            fontSize: 10,
            fontWeight: 800,
            padding: "2px 6px",
          }}
        >
          +{tag}
        </Button>
      ))}
    </Space>
  );
}

function StatusChip({ tone, children }: { tone: "up" | "down" | "warn" | "neutral"; children: ReactNode }) {
  const style = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 22,
    padding: "2px 7px",
    borderRadius: 999,
    background:
      tone === "up" ? "#fff7f4" : tone === "down" ? "#f2fbf5" : tone === "warn" ? "#fff8e8" : "#eef2f7",
    color:
      tone === "up"
        ? "var(--price-up, #c62828)"
        : tone === "down"
          ? "var(--price-down, #1f8b4c)"
          : tone === "warn"
            ? "var(--muted)"
            : "var(--muted)",
    fontSize: 11,
    fontWeight: 800,
  } as const;
  return <span style={style}>{children}</span>;
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
