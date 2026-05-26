import { Children, useMemo } from "react";
import type { ReactNode } from "react";
import { Button, Card, Col, Flex, Row, Skeleton, Space, Statistic, Tag, Typography } from "antd";

import type { PaperOrder, PaperPosition, PaperStockPnlItem, PaperStockPnlSummary, PaperTrade } from "../../types";
import { EmptyState } from "../workspace-shared/WorkspaceComponents";
import { formatPaperDateTime } from "./paperTradingFormatters";
import {
  formatInteger,
  formatMoneyPlain,
  formatPct,
  formatPrice,
  plainTradingText,
  toneFromChange,
} from "../workspace-shared/workspaceFormatters";
import { usePaperUiStore } from "../../stores/paperUiStore";

interface PaperPositionDetailsPanelProps {
  positions: PaperPosition[];
  orders: PaperOrder[];
  trades: PaperTrade[];
  stockPnl: PaperStockPnlItem[];
  stockPnlSummary: PaperStockPnlSummary | null;
  loading: boolean;
  embedded?: boolean;
}

interface StockTradeDetail {
  symbol: string;
  name: string;
  position: PaperPosition | null;
  orders: PaperOrder[];
  trades: PaperTrade[];
  buyQuantity: number;
  sellQuantity: number;
  avgBuyPrice: number | null;
  realizedPnl: number;
  totalPnl: number | null;
  totalFees: number;
}

export function PaperPositionDetailsPanel({
  positions,
  orders,
  trades,
  stockPnl,
  stockPnlSummary,
  loading,
  embedded = false,
}: PaperPositionDetailsPanelProps) {
  const details = useMemo(() => buildStockTradeDetails(positions, orders, trades, stockPnl), [positions, orders, trades, stockPnl]);
  const selectedSymbol = usePaperUiStore((state) => state.selectedPositionSymbol);
  const setSelectedSymbol = usePaperUiStore((state) => state.setSelectedPositionSymbol);
  const selected = details.find((item) => item.symbol === selectedSymbol) ?? details[0] ?? null;
  const content = (
    <Space direction="vertical" size={8} style={{ display: "flex", width: "100%", fontSize: 11 }}>
      {loading ? <DetailSkeleton /> : null}
      {!loading && !details.length ? <EmptyState text="暂无持仓或成交明细" /> : null}
      {!loading && selected ? (
        <>
          {stockPnlSummary ? <PortfolioPnlSummary summary={stockPnlSummary} /> : null}
          <Flex gap={8} role="tablist" aria-label="选择股票" style={{ overflowX: "auto", paddingBottom: 2 }}>
            {details.map((item) => {
              const tone = toneFromChange(item.totalPnl);
              const active = item.symbol === selected.symbol;
              return (
                <Button
                  type={active ? "primary" : "default"}
                  key={item.symbol}
                  onClick={() => setSelectedSymbol(item.symbol)}
                  role="tab"
                  aria-selected={active}
                  style={{ flex: "0 0 132px", height: "auto", padding: "6px 8px", textAlign: "left" }}
                >
                  <Space direction="vertical" size={1} style={{ width: "100%" }}>
                    <Typography.Text strong ellipsis style={active ? { color: "#fff", fontSize: 11 } : { fontSize: 11 }}>
                      {item.name}
                    </Typography.Text>
                    <Typography.Text style={active ? { color: "rgba(255,255,255,0.8)", fontSize: 10 } : { fontSize: 10 }} type={active ? undefined : "secondary"}>
                      {item.symbol}
                    </Typography.Text>
                    <Typography.Text style={{ color: active ? "#fff" : amountColor(item.totalPnl, tone), fontSize: 11 }}>
                      {formatSignedMoney(item.totalPnl)}
                    </Typography.Text>
                  </Space>
                </Button>
              );
            })}
          </Flex>
          <SelectedStockSummary detail={selected} />
          <Row gutter={[12, 12]}>
            <DetailList
              title="最近成交"
              hint={selected.trades.length ? `共 ${selected.trades.length} 笔` : "暂无成交"}
              emptyText="这只股票暂无成交记录"
            >
              {selected.trades.slice(0, 10).map((item) => <TradeDetailRow item={item} key={item.id} />)}
            </DetailList>
            <DetailList
              title="最近委托"
              hint={selected.orders.length ? `共 ${selected.orders.length} 条` : "暂无委托"}
              emptyText="这只股票暂无委托记录"
            >
              {selected.orders.slice(0, 10).map((item) => <OrderDetailRow item={item} key={item.id} />)}
            </DetailList>
          </Row>
          <Typography.Text type="secondary" style={{ fontSize: 11 }}>
            已实现盈亏由后台按全量成交顺序回放，当前持仓盈亏以后台持仓价和最新行情为准。
          </Typography.Text>
        </>
      ) : null}
    </Space>
  );

  if (embedded) return content;

  return (
    <Card
      title="个股交易详情与盈利"
      extra={<Typography.Text type="secondary">按股票查看成交、委托和后台盈亏汇总</Typography.Text>}
    >
      {content}
    </Card>
  );
}

function PortfolioPnlSummary({ summary }: { summary: PaperStockPnlSummary }) {
  const gapWarn = Math.abs(summary.reconciliation_gap) >= 0.01;
  const items = [
    { label: "账户总盈亏", value: formatSignedMoney(summary.account_total_pnl), tone: toneFromChange(summary.account_total_pnl) },
    { label: "股票累计盈亏", value: formatSignedMoney(summary.stock_total_pnl), tone: toneFromChange(summary.stock_total_pnl) },
    { label: "已实现汇总", value: formatSignedMoney(summary.realized_pnl), tone: toneFromChange(summary.realized_pnl) },
    { label: "浮动汇总", value: formatSignedMoney(summary.unrealized_pnl), tone: toneFromChange(summary.unrealized_pnl) },
    { label: "对账差额", value: formatSignedMoney(summary.reconciliation_gap), tone: gapWarn ? "down" : "neutral" },
  ];
  return (
    <Row gutter={[8, 8]}>
      {items.map((item) => (
        <SummaryMetric key={item.label} label={item.label} value={item.value} tone={item.tone} />
      ))}
    </Row>
  );
}

function buildStockTradeDetails(
  positions: PaperPosition[],
  orders: PaperOrder[],
  trades: PaperTrade[],
  stockPnl: PaperStockPnlItem[],
): StockTradeDetail[] {
  const symbols = new Map<string, string>();
  for (const item of positions) symbols.set(item.symbol, item.name || item.symbol);
  for (const item of stockPnl) symbols.set(item.symbol, item.name || item.symbol);
  for (const item of trades) symbols.set(item.symbol, symbols.get(item.symbol) || item.symbol);
  for (const item of orders) symbols.set(item.symbol, symbols.get(item.symbol) || item.name || item.symbol);
  const pnlBySymbol = new Map(stockPnl.map((item) => [item.symbol, item]));

  return Array.from(symbols, ([symbol, name]) => {
    const position = positions.find((item) => item.symbol === symbol) ?? null;
    const pnl = pnlBySymbol.get(symbol);
    const symbolTrades = trades
      .filter((item) => item.symbol === symbol)
      .sort((left, right) => compareDateDesc(left.trade_time, right.trade_time));
    const symbolOrders = orders
      .filter((item) => item.symbol === symbol)
      .sort((left, right) => compareDateDesc(left.created_at, right.created_at));
    const buyTrades = symbolTrades.filter((item) => item.side === "buy");
    const sellTrades = symbolTrades.filter((item) => item.side === "sell");
    const buyQuantity = pnl?.buy_quantity ?? sumBy(buyTrades, (item) => item.quantity);
    const sellQuantity = pnl?.sell_quantity ?? sumBy(sellTrades, (item) => item.quantity);
    const totalFees = pnl?.total_fees ?? sumBy(symbolTrades, tradeFees);
    const replay = replayWeightedCost(symbolTrades);
    const avgBuyPrice = position?.cost_basis ?? pnl?.avg_cost ?? replay.avgCost ?? null;
    const realizedPnl = pnl?.realized_pnl ?? replay.realizedPnl;
    const totalPnl = pnl ? pnl.total_pnl : (symbolTrades.length || position ? realizedPnl + (position?.unrealized_pnl ?? 0) : null);

    return {
      symbol,
      name: position?.name || pnl?.name || symbolOrders[0]?.name || name,
      position,
      orders: symbolOrders,
      trades: symbolTrades,
      buyQuantity,
      sellQuantity,
      avgBuyPrice,
      realizedPnl,
      totalPnl,
      totalFees,
    };
  }).sort((left, right) => Number(Boolean(right.position)) - Number(Boolean(left.position)) || left.symbol.localeCompare(right.symbol));
}

function SelectedStockSummary({ detail }: { detail: StockTradeDetail }) {
  const position = detail.position;
  const summaryItems = [
    { label: "当前持仓", value: `${formatInteger(position?.quantity)} 股`, tone: "neutral" },
    { label: "可卖数量", value: `${formatInteger(position?.available_quantity)} 股`, tone: "neutral" },
    { label: "当前价", value: formatPriceWithYuan(position?.latest_price), tone: "neutral" },
    { label: "持仓市值", value: formatMoneyWithYuan(position?.market_value), tone: "neutral" },
    { label: "浮动盈亏", value: formatSignedMoney(position?.unrealized_pnl), tone: toneFromChange(position?.unrealized_pnl) },
    { label: "浮动收益率", value: formatPct(position?.unrealized_pnl_pct), tone: toneFromChange(position?.unrealized_pnl_pct) },
    { label: "已实现盈亏", value: formatSignedMoney(detail.realizedPnl), tone: toneFromChange(detail.realizedPnl) },
    { label: "个股总盈亏", value: formatSignedMoney(detail.totalPnl), tone: toneFromChange(detail.totalPnl) },
    { label: "平均买入价", value: formatPriceWithYuan(detail.avgBuyPrice), tone: "neutral" },
    { label: "累计手续费", value: formatMoneyWithYuan(detail.totalFees), tone: "neutral" },
  ];
  return (
    <Row gutter={[8, 8]}>
      {summaryItems.map((item) => (
        <SummaryMetric key={item.label} label={item.label} value={item.value} tone={item.tone} />
      ))}
    </Row>
  );
}

function SummaryMetric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <Col xs={12} sm={8} lg={6} xl={4}>
      <Card size="small" styles={{ body: { padding: 6 } }}>
        <Statistic title={label} value={value} styles={{ content: { color: amountColor(undefined, tone), fontSize: 12, lineHeight: 1.1 } }} />
      </Card>
    </Col>
  );
}

function DetailList({
  title,
  hint,
  emptyText,
  children,
}: {
  title: string;
  hint: string;
  emptyText: string;
  children: ReactNode;
}) {
  return (
    <Col xs={24} lg={12}>
      <Card size="small" title={title} extra={<Typography.Text type="secondary" style={{ fontSize: 11 }}>{hint}</Typography.Text>} styles={{ body: { padding: 6 } }}>
        <Space direction="vertical" size={6} style={{ display: "flex", maxHeight: 260, overflowY: "auto" }}>
          {Children.count(children) ? children : <EmptyState text={emptyText} />}
        </Space>
      </Card>
    </Col>
  );
}

function TradeDetailRow({ item }: { item: PaperTrade }) {
  const sideText = item.side === "buy" ? "买入" : "卖出";
  const reason = plainTradingText(item.side === "buy" ? item.entry_reason : item.exit_reason);
  return (
    <Card size="small" styles={{ body: { padding: 6 } }}>
      <Space direction="vertical" size={5} style={{ width: "100%", fontSize: 11 }}>
        <Flex justify="space-between" wrap gap={8}>
          <Tag color={item.side === "buy" ? "red" : "green"}>{sideText} {formatInteger(item.quantity)} 股</Tag>
          <Typography.Text type="secondary" style={{ fontSize: 11 }}>{formatPaperDateTime(item.trade_time)}</Typography.Text>
        </Flex>
        <Flex wrap gap={12}>
          <Typography.Text>价格 {formatPriceWithYuan(item.price)}</Typography.Text>
          <Typography.Text>成交额 {formatMoneyWithYuan(item.gross_amount)}</Typography.Text>
          <Typography.Text>费用 {formatMoneyWithYuan(tradeFees(item))}</Typography.Text>
        </Flex>
        {reason ? <Typography.Text type="secondary" style={{ fontSize: 11 }}>{reason}</Typography.Text> : null}
      </Space>
    </Card>
  );
}

function OrderDetailRow({ item }: { item: PaperOrder }) {
  const sideText = item.side === "buy" ? "买入" : "卖出";
  const statusText = orderStatusText(item.status);
  return (
    <Card size="small" styles={{ body: { padding: 6 } }}>
      <Space direction="vertical" size={5} style={{ width: "100%", fontSize: 11 }}>
        <Flex justify="space-between" wrap gap={8}>
          <Tag color={item.side === "buy" ? "red" : "green"}>{sideText} {formatInteger(item.quantity)} 股</Tag>
          <Typography.Text type="secondary" style={{ fontSize: 11 }}>{formatPaperDateTime(item.created_at)}</Typography.Text>
        </Flex>
        <Flex wrap gap={12}>
          <Typography.Text>{item.order_type === "market" ? "市价" : "限价"} {formatPriceWithYuan(item.price ?? item.avg_fill_price)}</Typography.Text>
          <Typography.Text>已成 {formatInteger(item.filled_quantity)} 股</Typography.Text>
          <Typography.Text>{statusText}</Typography.Text>
        </Flex>
        {item.reject_reason ? <Typography.Text type="warning" style={{ fontSize: 11 }}>{plainTradingText(item.reject_reason)}</Typography.Text> : null}
      </Space>
    </Card>
  );
}

function DetailSkeleton() {
  return (
    <Row gutter={[8, 8]} aria-label="个股详情加载中">
      {Array.from({ length: 4 }).map((_, index) => (
        <Col xs={24} sm={12} lg={6} key={index}>
          <Skeleton.Button active block style={{ height: 54 }} />
        </Col>
      ))}
    </Row>
  );
}

function amountColor(value?: number | null, tone?: string): string | undefined {
  const resolvedTone = tone ?? toneFromChange(value);
  if (resolvedTone === "up") return "#cf2626";
  if (resolvedTone === "down") return "#1f8b4c";
  return undefined;
}

function orderStatusText(status: PaperOrder["status"]): string {
  if (status === "pending") return "待成交";
  if (status === "filled") return "已成交";
  if (status === "partial") return "部分成交";
  if (status === "rejected") return "已拒绝";
  if (status === "cancelled") return "已撤销";
  return status;
}

function tradeFees(item: PaperTrade): number {
  return (item.commission || 0) + (item.stamp_tax || 0) + (item.transfer_fee || 0);
}

function replayWeightedCost(trades: PaperTrade[]): { avgCost: number | null; quantity: number; realizedPnl: number } {
  let quantity = 0;
  let avgCost: number | null = null;
  let realizedPnl = 0;
  const chronological = [...trades].sort((left, right) => compareDateAsc(left.trade_time, right.trade_time));
  for (const item of chronological) {
    const tradeQuantity = Number.isFinite(item.quantity) ? item.quantity : 0;
    if (tradeQuantity <= 0) continue;
    if (item.side === "buy") {
      const buyCost = Number.isFinite(item.net_amount) ? item.net_amount : item.gross_amount + tradeFees(item);
      const currentCost: number = (avgCost ?? 0) * quantity;
      quantity += tradeQuantity;
      avgCost = quantity > 0 ? (currentCost + buyCost) / quantity : null;
      continue;
    }
    const sellNet = Number.isFinite(item.net_amount) ? item.net_amount : item.gross_amount - tradeFees(item);
    const costBasis = avgCost ?? item.price;
    const settledQuantity = Math.min(quantity || tradeQuantity, tradeQuantity);
    realizedPnl += sellNet - costBasis * settledQuantity;
    quantity = Math.max(0, quantity - tradeQuantity);
    if (quantity === 0) avgCost = null;
  }
  return { avgCost, quantity, realizedPnl };
}

function sumBy<T>(items: T[], pick: (item: T) => number): number {
  return items.reduce((sum, item) => sum + (Number.isFinite(pick(item)) ? pick(item) : 0), 0);
}

function compareDateAsc(left?: string | null, right?: string | null): number {
  return new Date(left ?? 0).getTime() - new Date(right ?? 0).getTime();
}

function compareDateDesc(left?: string | null, right?: string | null): number {
  return new Date(right ?? 0).getTime() - new Date(left ?? 0).getTime();
}

function formatSignedMoney(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}¥${formatMoneyPlain(Math.abs(value))}`;
}

function formatMoneyWithYuan(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `¥${formatMoneyPlain(value)}`;
}

function formatPriceWithYuan(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `¥${formatPrice(value)}`;
}
