import { type ReactNode, useMemo } from "react";
import { Button, Card, Space, Tabs, Typography } from "antd";
import type {
  PaperAgentRun,
  PaperAutoTradingStatus,
  MarketReviewHistoryEntry,
  PaperGroupedPerformance,
  PaperLedgerRepairResponse,
  PaperOrder,
  PaperPerformance,
  PaperPerformanceDashboard,
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
import { PaperTodayActionPanel } from "./PaperTodayActionPanel";
import { PortfolioExecutionPanel } from "./PortfolioExecutionPanel";
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
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { VirtualCardList } from "../../ui/list/VirtualCardList";
import { usePaperUiStore, type PaperDetailGroupKey, type PaperDetailTabKey } from "../../stores/paperUiStore";
import { PaperExitModelShadowSummaryPanel } from "./PaperExitModelShadowSummary";

export function PaperDetailTabs(props: PaperDetailTabsProps) {
  const tab = usePaperUiStore((state) => state.detailTab);
  const setTab = usePaperUiStore((state) => state.setDetailTab);
  const group = usePaperUiStore((state) => state.detailGroup);
  const setGroup = usePaperUiStore((state) => state.setDetailGroup);
  const tabs = useMemo(() => buildTabs(props), [props]);
  const visibleTabs = tabs.filter((item) => item.group === group);
  const activeTab = visibleTabs.some((item) => item.key === tab) ? tab : defaultTabForGroup(group);

  return (
    <Card
      size="small"
      style={{ gridArea: "details" }}
      styles={{ body: { padding: 8, fontSize: 12 } }}
    >
      <Tabs
        size="small"
        activeKey={group}
        onChange={(key) => {
          const nextGroup = key as PaperDetailGroupKey;
          setGroup(nextGroup);
          setTab(defaultTabForGroup(nextGroup));
        }}
        tabBarGutter={8}
        tabBarStyle={{ marginBottom: 4, fontSize: 12 }}
        items={[
          { key: "automation", label: "自动化" },
          { key: "records", label: "记录" },
          { key: "performance", label: "策略绩效" },
          { key: "details", label: "详情信息" },
        ]}
      />
      <Tabs
        size="small"
        activeKey={activeTab}
        onChange={(key) => setTab(key as PaperDetailTabKey)}
        tabBarGutter={8}
        tabBarStyle={{ marginBottom: 6, fontSize: 12 }}
        items={visibleTabs.map((item) => ({
          key: item.key,
          label: (
            <Typography.Text strong style={{ fontSize: 12, lineHeight: 1.2 }}>{item.label} <Typography.Text type="secondary" style={{ fontSize: 12 }}>{item.hint}</Typography.Text></Typography.Text>
          ),
        }))}
      />
      <div role="tabpanel" style={{ minHeight: 236, fontSize: 12 }}>
        {activeTab === "today" ? (
          <PaperTodayActionPanel
            autoTradingStatus={props.autoTradingStatus}
            autoTradingRuns={props.autoTradingRuns}
            riskEvents={props.riskEvents}
          />
        ) : null}
        {activeTab === "orders" ? <PaperOrdersTab orders={props.orders} loading={props.loading} /> : null}
        {activeTab === "trades" ? (
          <PaperTradesTab
            trades={props.trades}
            performance={props.performance}
            tagPerformance={props.tagPerformance}
            tradeTags={props.tradeTags}
            onAddTradeTag={props.onAddTradeTag}
            onDeleteTradeTag={props.onDeleteTradeTag}
            loading={props.loading}
          />
        ) : null}
        {activeTab === "pnl" ? (
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
        {activeTab === "strategy" ? (
          <StrategyTab
            strategyPerformance={props.strategyPerformance}
            marketPerformance={props.marketPerformance}
            sectorEtfT0Performance={props.sectorEtfT0Performance}
          />
        ) : null}
        {activeTab === "risk" ? (
          <RiskTab
            riskEvents={props.riskEvents}
            autoTradingRuns={props.autoTradingRuns}
          />
        ) : null}
        {activeTab === "diagnostic" ? (
          <DiagnosticTab
            ledgerRepairStatus={props.ledgerRepairStatus}
            canManageReconcile={props.canManageReconcile}
            loading={props.loading}
            onRefreshLedgerRepair={props.onRefreshLedgerRepair}
            onApplyLedgerRepair={props.onApplyLedgerRepair}
          />
        ) : null}
        {activeTab === "review-history" ? (
          <ReviewHistoryTab performanceDashboard={props.performanceDashboard} />
        ) : null}
        {activeTab === "execution-preview" ? (
          <ExecutionPreviewTab performance={props.performance} />
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
  performanceDashboard?: PaperPerformanceDashboard | null;
  autoTradingStatus: PaperAutoTradingStatus | null;
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
    { key: "today", group: "automation", label: "今日动作", hint: props.autoTradingStatus?.running ? "运行" : "待命" },
    { key: "risk", group: "automation", label: "风险与日志", hint: `${props.riskEvents.length} 个风险` },
    { key: "diagnostic", group: "automation", label: "对账诊断", hint: props.canManageReconcile ? "可修复" : "只读" },
    { key: "orders", group: "records", label: "委托记录", hint: `${props.orders.length} 条` },
    { key: "trades", group: "records", label: "成交记录", hint: `${props.trades.length} 条` },
    { key: "pnl", group: "performance", label: "个股盈亏", hint: `${props.stockPnl.length} 只` },
    { key: "strategy", group: "performance", label: "策略绩效", hint: `${props.strategyPerformance.length + props.marketPerformance.length} 组` },
    { key: "execution-preview", group: "performance", label: "组合执行预览", hint: `${props.performance?.portfolio_execution_preview?.candidate_count ?? 0} 样本` },
    { key: "review-history", group: "details", label: "复盘历史", hint: `${reviewReportCount(props.performanceDashboard)} 条` },
  ] as Array<{ key: PaperDetailTabKey; group: PaperDetailGroupKey; label: string; hint: string }>;
}

function defaultTabForGroup(group: PaperDetailGroupKey): PaperDetailTabKey {
  if (group === "records") return "orders";
  if (group === "performance") return "strategy";
  if (group === "details") return "review-history";
  return "today";
}

export function PaperOrdersTab({ orders, loading }: { orders: PaperOrder[]; loading: boolean }) {
  return (
    <>
      <div className="paper-detail-grid">
        <VirtualGrid<PaperOrder>
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
                  {item.reject_reason ? <Typography.Text type="warning" style={{ fontSize: 12 }}>原因：{item.reject_reason}</Typography.Text> : null}
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
      </div>
      <VirtualCardList
        className="paper-detail-card-list"
        empty={<EmptyState text="暂无委托记录" />}
        estimateSize={112}
        getItemKey={(item) => item.id}
        items={orders}
        maxHeight={340}
        renderItem={(item) => <PaperOrderMobileCard item={item} />}
      />
    </>
  );
}

export function PaperTradesTab({
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
      <div className="paper-detail-grid">
        <VirtualGrid<PaperTrade>
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
                    <Typography.Text type={item.commission_warning ? "warning" : "secondary"} style={{ fontSize: 12 }}>
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
      </div>
      <VirtualCardList
        className="paper-detail-card-list"
        empty={<EmptyState text="暂无成交记录" />}
        estimateSize={118}
        getItemKey={(item) => item.id}
        items={trades}
        maxHeight={340}
        renderItem={(item) => (
          <PaperTradeMobileCard
            item={item}
            tags={tradeTags[item.id] ?? []}
            onAddTradeTag={onAddTradeTag}
            onDeleteTradeTag={onDeleteTradeTag}
          />
        )}
      />
    </TabScroll>
  );
}

function PaperOrderMobileCard({ item }: { item: PaperOrder }) {
  return (
    <article className="paper-mobile-card paper-order-mobile-card">
      <div className="paper-mobile-card__head">
        <strong>{item.name || item.symbol}</strong>
        <StatusChip tone={orderStatusTone(item.status)}>{orderStatusText(item.status)}</StatusChip>
      </div>
      <div className="paper-mobile-card__meta">
        <span>{item.symbol}</span>
        <span>{item.side === "buy" ? "买入" : "卖出"} · {item.order_type === "market" ? "市价" : "限价"}</span>
        <span>{formatPaperDateTime(item.created_at)}</span>
      </div>
      <div className="paper-mobile-card__facts">
        <span>委托 {formatInteger(item.quantity)} 股</span>
        <span>已成 {formatInteger(item.filled_quantity)} 股</span>
        <span>均价 {formatPrice(item.avg_fill_price)}</span>
      </div>
      {item.reject_reason ? <Typography.Text className="paper-mobile-card__note" type="warning">{item.reject_reason}</Typography.Text> : null}
    </article>
  );
}

function PaperTradeMobileCard({
  item,
  tags,
  onAddTradeTag,
  onDeleteTradeTag,
}: {
  item: PaperTrade;
  tags: PaperTradeTag[];
  onAddTradeTag: (tradeId: number, tag: string) => void;
  onDeleteTradeTag: (tradeId: number, tagId: number) => void;
}) {
  const reasonText = item.commission_warning || (item.side === "buy" ? item.entry_reason : item.exit_reason);
  return (
    <article className="paper-mobile-card paper-trade-mobile-card">
      <div className="paper-mobile-card__head">
        <strong>{item.symbol}</strong>
        <StatusChip tone={item.side === "buy" ? "up" : "down"}>{item.side === "buy" ? "买入" : "卖出"}</StatusChip>
      </div>
      <div className="paper-mobile-card__meta">
        <span>{item.strategy_key || "未标注策略"}</span>
        <span>{formatPaperDateTime(item.trade_time)}</span>
      </div>
      <div className="paper-mobile-card__facts">
        <span>{formatInteger(item.quantity)} 股</span>
        <span>价格 {formatPrice(item.price)}</span>
        <span>净额 {formatInteger(item.net_amount)}</span>
      </div>
      {reasonText ? <Typography.Text className="paper-mobile-card__note" type={item.commission_warning ? "warning" : "secondary"}>{reasonText}</Typography.Text> : null}
      <TradeTags item={item} tags={tags} onAddTag={onAddTradeTag} onDeleteTag={onDeleteTradeTag} />
    </article>
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
      <Card size="small" title="止盈止损模型影子验证" extra={<Typography.Text type="secondary">只读对比，不改规则动作。</Typography.Text>}>
        <PaperExitModelShadowSummaryPanel />
      </Card>
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

export function ReviewHistoryTab({ performanceDashboard }: { performanceDashboard?: PaperPerformanceDashboard | null }) {
  const items = reviewHistoryItems(performanceDashboard);
  return (
    <TabScroll>
      <Card size="small" title="复盘历史" extra={<Typography.Text type="secondary">模拟盘只作历史辅助，市场复盘主入口在实时监控。</Typography.Text>}>
        {items.length ? (
          <Space className="paper-review-history-list" direction="vertical" size={8}>
            {items.map((item) => <ReviewHistoryCard key={item.key} item={item} />)}
          </Space>
        ) : (
          <EmptyState text="暂无复盘历史" />
        )}
      </Card>
    </TabScroll>
  );
}

export function ExecutionPreviewTab({ performance }: { performance: PaperPerformance | null }) {
  return (
    <TabScroll>
      <Card size="small" title="组合执行预览" extra={<Typography.Text type="secondary">只读测算，不会触发委托。</Typography.Text>}>
        <PortfolioExecutionPanel preview={performance?.portfolio_execution_preview} embedded />
      </Card>
    </TabScroll>
  );
}

type ReviewHistoryItem = {
  key: string;
  title: string;
  summary: string;
  suggestion?: string;
  generatedAt?: string;
  riskCount: number;
};

function reviewHistoryItems(performanceDashboard?: PaperPerformanceDashboard | null): ReviewHistoryItem[] {
  if (!performanceDashboard) return [];
  const items: ReviewHistoryItem[] = [];
  const report = performanceDashboard.today_report;
  if (report) {
    items.push({
      key: `paper-${report.id}`,
      title: `模拟盘日报 · ${report.report_date}`,
      summary: report.overall_summary,
      suggestion: report.suggestion,
      generatedAt: report.generated_at,
      riskCount: report.risk_alerts.length,
    });
  }
  for (const reportItem of performanceDashboard.review_reports ?? []) {
    items.push(reviewHistoryEntry(reportItem));
  }
  return items;
}

function reviewHistoryEntry(report: MarketReviewHistoryEntry): ReviewHistoryItem {
  const slot = report.report_slot === "midday" ? "午盘" : report.report_slot === "close" ? "收盘" : (report.report_slot || "复盘");
  return {
    key: `market-${report.id}`,
    title: `${report.review_subject || "全市场"}${slot}复盘 · ${report.report_date}`,
    summary: report.overall_summary || "复盘记录已生成，具体正文请到实时监控页查看。",
    suggestion: report.suggestion,
    generatedAt: report.generated_at,
    riskCount: report.risk_alerts.length,
  };
}

export function reviewReportCount(performanceDashboard?: PaperPerformanceDashboard | null) {
  return (performanceDashboard?.today_report ? 1 : 0) + (performanceDashboard?.review_reports?.length ?? 0);
}

function ReviewHistoryCard({ item }: { item: ReviewHistoryItem }) {
  return (
    <article className="paper-mobile-card">
      <div className="paper-mobile-card__head">
        <strong>{item.title}</strong>
        <StatusChip tone={item.riskCount > 0 ? "warn" : "neutral"}>{item.riskCount > 0 ? `${item.riskCount} 个风险` : "无风险提示"}</StatusChip>
      </div>
      <Typography.Text className="paper-mobile-card__summary">{item.summary}</Typography.Text>
      {item.suggestion ? <Typography.Text className="paper-mobile-card__note" type="secondary">提示：{item.suggestion}</Typography.Text> : null}
      {item.generatedAt ? <Typography.Text className="paper-mobile-card__note" type="secondary">生成时间：{formatPaperDateTime(item.generatedAt)}</Typography.Text> : null}
    </article>
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
            border: "1px solid color-mix(in srgb, var(--price-down) 22%, transparent)",
            borderRadius: 999,
            background: "var(--mkt-down-soft)",
            color: "var(--price-down)",
            fontSize: 12,
            fontWeight: 700,
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
            background: "var(--bg-elevated)",
            color: "var(--muted)",
            fontSize: 12,
            fontWeight: 700,
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
      tone === "up" ? "var(--mkt-up-soft)" : tone === "down" ? "var(--mkt-down-soft)" : tone === "warn" ? "color-mix(in srgb, var(--warning) 12%, transparent)" : "var(--bg-subtle)",
    color:
      tone === "up" ? "var(--price-up)" : tone === "down" ? "var(--price-down)" : "var(--muted)",
    fontSize: 12,
    fontWeight: 700,
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
