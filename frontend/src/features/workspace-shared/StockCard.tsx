import type { CSSProperties, ReactNode } from "react";
import { Button, Grid } from "antd";
import { directActionTitle, scoreStars } from "../../utils/uxClarity";
import { LiveCell } from "../../ui/realtime/LiveCell";
import type { StockCardView, Tone } from "./workspaceTypes";

const { useBreakpoint } = Grid;

export function StockCardList({
  children,
  compact = false,
  style,
}: {
  children: ReactNode;
  compact?: boolean;
  style?: CSSProperties;
}) {
  return (
    <div className={`tq-stock-list ${compact ? "tq-stock-list--compact" : ""}`.trim()} style={style}>
      {children}
    </div>
  );
}

export function StockIdentity({
  name,
  symbol,
  note,
  tags = [],
}: {
  name: string;
  symbol: string;
  note?: string;
  tags?: string[];
}) {
  return (
    <div className="tq-stock-identity">
      <div className="tq-stock-identity__main">
        <strong className="tq-stock-identity__name">{name}</strong>
        <span className="tq-stock-identity__meta">{symbol}</span>
      </div>
      {note ? <span className="tq-stock-identity__meta">{note}</span> : null}
      {tags.length ? (
        <div className="tq-stock-identity__tags">
          {tags.map((tag) => <span key={tag} className="tq-stock-identity__tag">{tag}</span>)}
        </div>
      ) : null}
    </div>
  );
}

export function StockCard({
  stock,
  actions,
  onAction,
  compact = false,
}: {
  stock: StockCardView;
  actions?: string[];
  onAction?: (action: string) => void;
  compact?: boolean;
}) {
  const screens = useBreakpoint();
  const wide = screens.md ?? true;
  return (
    <article className={[
      "tq-stock-card",
      compact ? "tq-stock-card--compact" : "",
      wide ? "tq-stock-card--wide" : "tq-stock-card--narrow",
      `tq-stock-card--tone-${stock.tone}`,
      stock.highlight ? "tq-stock-card--highlight" : "",
    ].filter(Boolean).join(" ")}
    >
      <StockIdentity name={stock.name} symbol={stock.symbol} note={stock.identityNote} tags={stock.identityTags} />
      <div className="tq-stock-card__body">
        <div className="tq-stock-card__direct-action">
          <strong className="tq-stock-card__direct-action-title">{directActionTitle(stock.actionText)}</strong>
          {stock.scoreText ? <span className="tq-stock-card__score" title={qualityScoreTitle(stock.scoreText)}>{qualityScoreText(stock.scoreText)}</span> : null}
        </div>
        <div className="tq-stock-card__meta">
          <span>当前价 {stock.livePrice ? <LiveCell symbol={stock.symbol} field="price" fallback={stock.priceText} /> : stock.priceText}</span>
          <span className={`tq-stock-card__meta--${stock.tone}`}>涨跌 {stock.livePrice ? <LiveCell symbol={stock.symbol} field="changePct" fallback={stock.changeText} /> : stock.changeText}</span>
          <span className={`tq-stock-card__badge tq-stock-card__risk tq-stock-card__risk--${riskTone(stock.riskText)}`}>风险 {stock.riskText}</span>
          {stock.expectedText ? <span>预期 {stock.expectedText}</span> : null}
        </div>
        {(stock.entryText || stock.stopText || stock.operationAmountText) ? (
          <div className="tq-stock-card__operation">
            {stock.entryText ? <OperationItem label="建议买入区间" value={stock.entryText} /> : null}
            {stock.stopText ? <OperationItem label="止损价" value={stock.stopText} /> : null}
            {stock.operationAmountText ? <OperationItem label="建议仓位/数量" value={stock.operationAmountText} /> : null}
          </div>
        ) : null}
        {stock.badges?.length ? (
          <div className="tq-stock-card__badge-row">
            {stock.badges.slice(0, 2).map((badge) => <span key={badge} className="tq-stock-card__badge">{badge}</span>)}
          </div>
        ) : null}
        {actions?.length ? (
          <div className="tq-stock-card__actions">
            {actions.map((action) => (
              <Button
                size="small"
                htmlType="button"
                danger={action === "移除"}
                onClick={(event) => {
                  event.stopPropagation();
                  onAction?.(action);
                }}
                key={action}
              >
                {action}
              </Button>
            ))}
          </div>
        ) : null}
        {stock.executionHint ? <div className="tq-stock-card__execution-hint">{stock.executionHint}</div> : null}
      </div>
    </article>
  );
}

function qualityScoreText(scoreText: string): string {
  return scoreText.includes("分") ? scoreText : `质量分 ${scoreText}`;
}

function qualityScoreTitle(scoreText: string): string {
  const score = Number(scoreText);
  if (!Number.isFinite(score)) return "质量分仅作排序参考";
  return `质量星级 ${scoreStars(scoreText)}`;
}

function OperationItem({ label, value }: { label: string; value: string }) {
  return (
    <span className="tq-stock-card__operation-item">
      <small className="tq-stock-card__operation-label">{label}</small>
      <strong className="tq-stock-card__operation-value">{value}</strong>
    </span>
  );
}

function riskTone(value?: string): "danger" | "warn" | "success" | "neutral" {
  const text = value ?? "";
  if (text.includes("高") || text.includes("阻断")) return "danger";
  if (text.includes("中") || text.includes("注意") || text.includes("降级")) return "warn";
  if (text.includes("低") || text.includes("正常") || text.includes("清晰")) return "success";
  return "neutral";
}
