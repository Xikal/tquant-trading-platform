import type {
  PaperPosition,
} from "../../types";
import type { ReactNode } from "react";
import { OrderEntryModal } from "./PaperOrderEntryModal";
import { EmptyState } from "./WorkspaceComponents";
import { formatInteger, formatPct, formatPrice, toneFromChange } from "./workspaceFormatters";
export { formatPaperDateTime } from "./paperTradingFormatters";

export { OrderEntryModal };

export function PaperPositionsPanel({
  positions,
  loading,
}: {
  positions: PaperPosition[];
  loading: boolean;
}) {
  return (
    <section className="panel paper-positions">
      <div className="panel-title">
        <h2>当前持仓</h2>
        <span className="hint">{positions.length ? `共 ${positions.length} 只，首屏直接处理` : "暂无持仓"}</span>
      </div>
      <DataBody loading={loading} columns={4}>
        <div className="stock-list compact">
          {positions.length ? positions.map((item) => <PositionRow key={item.id} item={item} />) : <EmptyState text="暂无模拟持仓" />}
        </div>
      </DataBody>
    </section>
  );
}
function PositionRow({ item }: { item: PaperPosition }) {
  const tone = item.latest_price == null ? "neutral" : toneFromChange(item.unrealized_pnl_pct);
  const actionText = item.smart_exit_text || item.smart_exit_action || "按计划持有";
  return (
    <article className={`paper-row paper-position-row ${tone}`}>
      <div className="paper-stock-name">
        <strong>{item.name || item.symbol}</strong>
        <span>{item.symbol}</span>
      </div>
      <span>持仓 {formatInteger(item.quantity)} / 可卖 {formatInteger(item.available_quantity)}</span>
      <span>成本 {formatPrice(item.cost_basis)} / 现价 {formatPrice(item.latest_price)}</span>
      <span className="paper-position-action">{actionText}</span>
      <strong className={tone}>{formatPct(item.unrealized_pnl_pct)}</strong>
    </article>
  );
}

function DataBody({ loading, columns, children }: { loading: boolean; columns: number; children: ReactNode }) {
  if (loading) return <SkeletonList columns={columns} />;
  return <>{children}</>;
}

function SkeletonList({ columns }: { columns: number }) {
  return (
    <div className="paper-skeleton-list" aria-label="加载中">
      {Array.from({ length: 4 }).map((_, row) => (
        <div className="paper-skeleton-row" key={row}>
          {Array.from({ length: columns }).map((__, col) => (
            <span className="skeleton-line" key={col} />
          ))}
        </div>
      ))}
    </div>
  );
}
