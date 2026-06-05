import type {
  PaperPosition,
} from "../../types";
import { Card, Skeleton, Typography } from "antd";
import { OrderEntryModal } from "./PaperOrderEntryModal";
import { EmptyState } from "../workspace-shared/WorkspaceComponents";
import { formatInteger, formatPct, formatPrice, toneFromChange } from "../workspace-shared/workspaceFormatters";
export { formatPaperDateTime } from "./paperTradingFormatters";

export { OrderEntryModal };

export function PaperPositionsPanel({
  positions,
  loading,
  embedded = false,
}: {
  positions: PaperPosition[];
  loading: boolean;
  embedded?: boolean;
}) {
  const body = (
    <>
      {loading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : positions.length ? (
        <div
          className="paper-position-card-grid"
          style={{
            maxHeight: positions.length > 8 ? 260 : undefined,
            overflowY: positions.length > 8 ? "auto" : "visible",
            paddingRight: positions.length > 8 ? 4 : 0,
          }}
        >
          {positions.map((item) => <PositionRow key={item.id || item.symbol} item={item} />)}
        </div>
      ) : (
        <EmptyState text="暂无模拟持仓" />
      )}
    </>
  );
  if (embedded) {
    return (
      <section className="paper-positions-embedded" aria-label="当前持仓">
        <header className="paper-positions-embedded__header">
          <Typography.Text strong>当前持仓</Typography.Text>
          <Typography.Text type="secondary">{positions.length ? `共 ${positions.length} 只，首屏直接处理` : "暂无持仓"}</Typography.Text>
        </header>
        <div className="paper-positions-embedded__body">{body}</div>
      </section>
    );
  }
  return (
    <Card
      size="small"
      title="当前持仓"
      extra={<Typography.Text type="secondary">{positions.length ? `共 ${positions.length} 只，首屏直接处理` : "暂无持仓"}</Typography.Text>}
      variant="borderless"
      styles={{ body: { padding: 6, minHeight: 0, fontSize: 12 } }}
    >
      {body}
    </Card>
  );
}
function PositionRow({ item }: { item: PaperPosition }) {
  const tone = item.latest_price == null ? "neutral" : toneFromChange(item.unrealized_pnl_pct);
  return (
    <article
      className={`paper-position-card paper-position-card--${tone}`}
      style={{
        boxShadow: `inset 3px 0 0 ${toneColor(tone)}`,
      }}
    >
      <Typography.Text className="paper-position-card__line paper-position-card__line--identity" strong>
        {item.name || item.symbol} / {item.symbol}
      </Typography.Text>
      <Typography.Text className="paper-position-card__line">
        持/可 {formatInteger(item.quantity)} / {formatInteger(item.available_quantity)}
      </Typography.Text>
      <Typography.Text className="paper-position-card__line">
        成本/现价 {formatPrice(item.cost_basis)} / {formatPrice(item.latest_price)}
      </Typography.Text>
      <Typography.Text className="paper-position-card__line" strong style={{ color: toneColor(tone) }}>
        盈亏 {formatPct(item.unrealized_pnl_pct)}
      </Typography.Text>
    </article>
  );
}

function toneColor(tone: string): string {
  if (tone === "up") return "var(--price-up)";
  if (tone === "down") return "var(--price-down)";
  return "var(--text-1)";
}
