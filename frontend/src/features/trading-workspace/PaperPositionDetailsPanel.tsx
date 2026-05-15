import { Children, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { PaperOrder, PaperPosition, PaperTrade } from "../../types";
import { EmptyState } from "./WorkspaceComponents";
import { formatPaperDateTime } from "./paperTradingFormatters";
import {
  formatInteger,
  formatMoneyPlain,
  formatPct,
  formatPrice,
  plainTradingText,
  toneFromChange,
} from "./workspaceFormatters";

interface PaperPositionDetailsPanelProps {
  positions: PaperPosition[];
  orders: PaperOrder[];
  trades: PaperTrade[];
  loading: boolean;
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
  realizedPnl: number | null;
  totalPnl: number | null;
  totalFees: number;
}

export function PaperPositionDetailsPanel({
  positions,
  orders,
  trades,
  loading,
}: PaperPositionDetailsPanelProps) {
  const details = useMemo(() => buildStockTradeDetails(positions, orders, trades), [positions, orders, trades]);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const selected = details.find((item) => item.symbol === selectedSymbol) ?? details[0] ?? null;

  return (
    <section className="panel paper-position-details">
      <div className="panel-title">
        <h2>个股交易详情与盈利</h2>
        <span className="hint">按股票查看成交、委托和盈亏估算</span>
      </div>
      {loading ? <DetailSkeleton /> : null}
      {!loading && !details.length ? <EmptyState text="暂无持仓或成交明细" /> : null}
      {!loading && selected ? (
        <>
          <div className="paper-position-symbol-tabs" role="tablist" aria-label="选择股票">
            {details.map((item) => {
              const tone = toneFromChange(item.totalPnl);
              const active = item.symbol === selected.symbol;
              return (
                <button
                  type="button"
                  key={item.symbol}
                  className={`paper-position-symbol-tab ${active ? "active" : ""} ${tone}`}
                  onClick={() => setSelectedSymbol(item.symbol)}
                  role="tab"
                  aria-selected={active}
                >
                  <strong>{item.name}</strong>
                  <span>{item.symbol}</span>
                  <em>{formatSignedMoney(item.totalPnl)}</em>
                </button>
              );
            })}
          </div>
          <SelectedStockSummary detail={selected} />
          <div className="paper-position-detail-columns">
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
          </div>
          <p className="paper-position-detail-note">
            已实现盈亏按成交均价估算，最终以账户绩效和后台清算口径为准。
          </p>
        </>
      ) : null}
    </section>
  );
}

function buildStockTradeDetails(
  positions: PaperPosition[],
  orders: PaperOrder[],
  trades: PaperTrade[],
): StockTradeDetail[] {
  const symbols = new Map<string, string>();
  for (const item of positions) symbols.set(item.symbol, item.name || item.symbol);
  for (const item of trades) symbols.set(item.symbol, symbols.get(item.symbol) || item.symbol);
  for (const item of orders) symbols.set(item.symbol, symbols.get(item.symbol) || item.name || item.symbol);

  return Array.from(symbols, ([symbol, name]) => {
    const position = positions.find((item) => item.symbol === symbol) ?? null;
    const symbolTrades = trades
      .filter((item) => item.symbol === symbol)
      .sort((left, right) => compareDateDesc(left.trade_time, right.trade_time));
    const symbolOrders = orders
      .filter((item) => item.symbol === symbol)
      .sort((left, right) => compareDateDesc(left.created_at, right.created_at));
    const buyTrades = symbolTrades.filter((item) => item.side === "buy");
    const sellTrades = symbolTrades.filter((item) => item.side === "sell");
    const buyQuantity = sumBy(buyTrades, (item) => item.quantity);
    const sellQuantity = sumBy(sellTrades, (item) => item.quantity);
    const buyGross = sumBy(buyTrades, (item) => item.gross_amount);
    const buyFees = sumBy(buyTrades, tradeFees);
    const sellGross = sumBy(sellTrades, (item) => item.gross_amount);
    const sellFees = sumBy(sellTrades, tradeFees);
    const totalFees = buyFees + sellFees;
    const avgBuyPrice = buyQuantity > 0 ? buyGross / buyQuantity : position?.cost_basis ?? null;
    const realizedPnl = buyQuantity > 0 && sellQuantity > 0
      ? sellGross - sellFees - ((buyGross + buyFees) / buyQuantity) * Math.min(sellQuantity, buyQuantity)
      : null;
    const totalPnl = typeof realizedPnl === "number" || position
      ? (realizedPnl ?? 0) + (position?.unrealized_pnl ?? 0)
      : null;

    return {
      symbol,
      name: position?.name || symbolOrders[0]?.name || name,
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
    { label: "估算已实现", value: formatSignedMoney(detail.realizedPnl), tone: toneFromChange(detail.realizedPnl) },
    { label: "估算总盈亏", value: formatSignedMoney(detail.totalPnl), tone: toneFromChange(detail.totalPnl) },
    { label: "平均买入价", value: formatPriceWithYuan(detail.avgBuyPrice), tone: "neutral" },
    { label: "累计手续费", value: formatMoneyWithYuan(detail.totalFees), tone: "neutral" },
  ];
  return (
    <div className="paper-position-summary">
      {summaryItems.map((item) => (
        <div className={`paper-position-summary-item ${item.tone}`} key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
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
    <section className="paper-position-detail-list">
      <div className="paper-position-detail-list-title">
        <strong>{title}</strong>
        <span>{hint}</span>
      </div>
      <div className="paper-position-detail-scroll">
        {Children.count(children) ? children : <EmptyState text={emptyText} />}
      </div>
    </section>
  );
}

function TradeDetailRow({ item }: { item: PaperTrade }) {
  const sideText = item.side === "buy" ? "买入" : "卖出";
  const reason = plainTradingText(item.side === "buy" ? item.entry_reason : item.exit_reason);
  return (
    <article className="paper-position-detail-row">
      <div>
        <strong className={item.side === "buy" ? "up" : "down"}>{sideText} {formatInteger(item.quantity)} 股</strong>
        <span>{formatPaperDateTime(item.trade_time)}</span>
      </div>
      <div>
        <span>价格 {formatPriceWithYuan(item.price)}</span>
        <span>成交额 {formatMoneyWithYuan(item.gross_amount)}</span>
        <span>费用 {formatMoneyWithYuan(tradeFees(item))}</span>
      </div>
      {reason ? <small>{reason}</small> : null}
    </article>
  );
}

function OrderDetailRow({ item }: { item: PaperOrder }) {
  const sideText = item.side === "buy" ? "买入" : "卖出";
  const statusText = orderStatusText(item.status);
  return (
    <article className="paper-position-detail-row">
      <div>
        <strong className={item.side === "buy" ? "up" : "down"}>{sideText} {formatInteger(item.quantity)} 股</strong>
        <span>{formatPaperDateTime(item.created_at)}</span>
      </div>
      <div>
        <span>{item.order_type === "market" ? "市价" : "限价"} {formatPriceWithYuan(item.price ?? item.avg_fill_price)}</span>
        <span>已成 {formatInteger(item.filled_quantity)} 股</span>
        <span>{statusText}</span>
      </div>
      {item.reject_reason ? <small className="warn">{plainTradingText(item.reject_reason)}</small> : null}
    </article>
  );
}

function DetailSkeleton() {
  return (
    <div className="paper-position-detail-skeleton" aria-label="个股详情加载中">
      {Array.from({ length: 4 }).map((_, index) => <span className="skeleton-line" key={index} />)}
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

function tradeFees(item: PaperTrade): number {
  return (item.commission || 0) + (item.stamp_tax || 0) + (item.transfer_fee || 0);
}

function sumBy<T>(items: T[], pick: (item: T) => number): number {
  return items.reduce((sum, item) => sum + (Number.isFinite(pick(item)) ? pick(item) : 0), 0);
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
