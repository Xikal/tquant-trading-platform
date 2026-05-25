import type { CSSProperties, ReactNode } from "react";
import { Button, Grid } from "antd";
import { directActionTitle, scoreStars } from "../../utils/uxClarity";
import type { StockCardView, Tone } from "./workspaceTypes";

const { useBreakpoint } = Grid;

const STOCK_LIST_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
};

const STOCK_LIST_COMPACT_STYLE: CSSProperties = {
  gap: 6,
};

const STOCK_CARD_STYLE: CSSProperties = {
  display: "grid",
  gap: "6px 12px",
  alignItems: "start",
  border: "1px solid var(--line)",
  borderRadius: 8,
  background: "#fff",
  padding: 9,
};

const STOCK_CARD_WIDE_STYLE: CSSProperties = {
  gridTemplateColumns: "minmax(112px, 160px) minmax(0, 1fr)",
};

const STOCK_CARD_NARROW_STYLE: CSSProperties = {
  gridTemplateColumns: "1fr",
};

const STOCK_CARD_BODY_STYLE: CSSProperties = {
  display: "grid",
  minWidth: 0,
  gap: 6,
};

const STOCK_CARD_TONE_STYLES: Partial<Record<Tone, CSSProperties>> = {
  up: { background: "#fff7f4", borderColor: "#f0c9bf" },
  down: { background: "#f2fbf5", borderColor: "#b8dbc7" },
  warn: { background: "#fbf4e6", borderColor: "#ecd59a" },
};

const STOCK_CARD_HIGHLIGHT_STYLE: CSSProperties = {
  borderColor: "#f1a33c",
  boxShadow: "inset 3px 0 0 #f1a33c",
};

const STOCK_TONE_TEXT_STYLES: Partial<Record<Tone, CSSProperties>> = {
  up: { color: "var(--up)" },
  down: { color: "var(--down)" },
  warn: { color: "var(--warning)" },
};

const STOCK_DIRECT_ACTION_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 10,
  margin: "4px 0",
};

const STOCK_DIRECT_ACTION_TITLE_STYLE: CSSProperties = {
  color: "#0f172a",
  fontSize: 16,
};

const STOCK_SCORE_BADGE_STYLE: CSSProperties = {
  color: "#b7791f",
  fontSize: 12,
  fontWeight: 800,
  whiteSpace: "nowrap",
};

const STOCK_OPERATION_BAND_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(112px, 1fr))",
  gap: 6,
  margin: "2px 0 0",
  minWidth: 0,
};

const STOCK_OPERATION_ITEM_STYLE: CSSProperties = {
  display: "grid",
  gap: 2,
  minWidth: 0,
  borderRadius: 8,
  background: "#f8fafc",
  padding: "5px 7px",
};

const STOCK_OPERATION_HELP_STYLE: CSSProperties = {
  color: "#64748b",
  fontSize: 10,
  lineHeight: 1.2,
  whiteSpace: "nowrap",
};

const STOCK_OPERATION_VALUE_STYLE: CSSProperties = {
  color: "#0f172a",
  overflow: "hidden",
  fontSize: 12,
  lineHeight: 1.25,
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const STOCK_IDENTITY_STYLE: CSSProperties = {
  display: "grid",
  gap: 3,
};

const STOCK_IDENTITY_MAIN_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: 6,
};

const STOCK_IDENTITY_NAME_STYLE: CSSProperties = {
  fontSize: 14,
};

const STOCK_IDENTITY_META_STYLE: CSSProperties = {
  color: "#66758a",
  fontFamily: "IBM Plex Mono, monospace",
  fontSize: 11,
};

const STOCK_IDENTITY_TAGS_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 4,
};

const STOCK_IDENTITY_TAG_STYLE: CSSProperties = {
  borderRadius: 999,
  background: "#eef2f7",
  color: "#435168",
  fontSize: 10,
  fontWeight: 700,
  padding: "1px 5px",
};

const STOCK_META_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 10,
  color: "#66758a",
  fontFamily: "IBM Plex Mono, monospace",
  fontSize: 11,
};

const STOCK_META_TAG_STYLE: CSSProperties = {
  borderRadius: 999,
  background: "#eef2f7",
  color: "#435168",
  fontSize: 11,
  fontWeight: 700,
  padding: "3px 7px",
};

const STOCK_META_SUB_TAG_STYLE: CSSProperties = {
  background: "#fff7e6",
  color: "#9a5a00",
};

const STOCK_BADGE_ROW_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 4,
};

const STOCK_ACTIONS_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 6,
};

const STOCK_EXECUTION_HINT_STYLE: CSSProperties = {
  border: "1px solid #f3d49c",
  borderRadius: 6,
  background: "#fff7e8",
  color: "#7a4b00",
  fontSize: 12,
  lineHeight: 1.45,
  padding: "6px 8px",
};

export function StockCardList({
  children,
  compact = false,
  style,
}: {
  children: ReactNode;
  compact?: boolean;
  style?: CSSProperties;
}) {
  return <div style={{ ...STOCK_LIST_STYLE, ...(compact ? STOCK_LIST_COMPACT_STYLE : undefined), ...style }}>{children}</div>;
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
    <div style={STOCK_IDENTITY_STYLE}>
      <div style={STOCK_IDENTITY_MAIN_STYLE}>
        <strong style={STOCK_IDENTITY_NAME_STYLE}>{name}</strong>
        <span style={STOCK_IDENTITY_META_STYLE}>{symbol}</span>
      </div>
      {note ? <span style={STOCK_IDENTITY_META_STYLE}>{note}</span> : null}
      {tags.length ? (
        <div style={STOCK_IDENTITY_TAGS_STYLE}>
          {tags.map((tag) => <span key={tag} style={STOCK_IDENTITY_TAG_STYLE}>{tag}</span>)}
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
  const cardStyle: CSSProperties = {
    ...STOCK_CARD_STYLE,
    ...(compact ? { gap: 6, padding: 7 } : undefined),
    ...(wide ? STOCK_CARD_WIDE_STYLE : STOCK_CARD_NARROW_STYLE),
    ...STOCK_CARD_TONE_STYLES[stock.tone],
    ...(stock.highlight ? STOCK_CARD_HIGHLIGHT_STYLE : undefined),
  };
  return (
    <article style={cardStyle}>
      <StockIdentity name={stock.name} symbol={stock.symbol} note={stock.identityNote} tags={stock.identityTags} />
      <div style={STOCK_CARD_BODY_STYLE}>
        <div style={STOCK_DIRECT_ACTION_STYLE}>
          <strong style={{ ...STOCK_DIRECT_ACTION_TITLE_STYLE, ...(compact ? { fontSize: 13 } : undefined) }}>{directActionTitle(stock.actionText)}</strong>
          {stock.scoreText ? <span style={STOCK_SCORE_BADGE_STYLE} title={`质量分 ${stock.scoreText}`}>质量 {scoreStars(stock.scoreText)}</span> : null}
        </div>
        <div style={{ ...STOCK_META_STYLE, ...(compact ? { gap: 7, fontSize: 10 } : undefined) }}>
          <span>当前价 {stock.priceText}</span>
          <span style={STOCK_TONE_TEXT_STYLES[stock.tone]}>涨跌 {stock.changeText}</span>
          {stock.scoreText ? <span>质量分 {stock.scoreText}</span> : null}
          <span style={{ ...STOCK_META_TAG_STYLE, ...riskToneStyle(stock.riskText) }}>风险 {stock.riskText}</span>
          {stock.expectedText ? <span>预期 {stock.expectedText}</span> : null}
        </div>
        {(stock.entryText || stock.stopText || stock.operationAmountText) ? (
          <div style={STOCK_OPERATION_BAND_STYLE}>
            {stock.entryText ? <span style={STOCK_OPERATION_ITEM_STYLE}><small style={STOCK_OPERATION_HELP_STYLE}>建议买入区间</small><strong style={STOCK_OPERATION_VALUE_STYLE}>{stock.entryText}</strong></span> : null}
            {stock.stopText ? <span style={STOCK_OPERATION_ITEM_STYLE}><small style={STOCK_OPERATION_HELP_STYLE}>止损价</small><strong style={STOCK_OPERATION_VALUE_STYLE}>{stock.stopText}</strong></span> : null}
            {stock.operationAmountText ? <span style={STOCK_OPERATION_ITEM_STYLE}><small style={STOCK_OPERATION_HELP_STYLE}>建议仓位/数量</small><strong style={STOCK_OPERATION_VALUE_STYLE}>{stock.operationAmountText}</strong></span> : null}
          </div>
        ) : null}
        {stock.badges?.length ? (
          <div style={STOCK_BADGE_ROW_STYLE}>
            {stock.badges.map((badge) => <span key={badge} style={STOCK_META_TAG_STYLE}>{badge}</span>)}
          </div>
        ) : null}
        {stock.subBadges?.length ? (
          <div style={STOCK_BADGE_ROW_STYLE}>
            {stock.subBadges.map((badge) => <span key={badge} style={{ ...STOCK_META_TAG_STYLE, ...STOCK_META_SUB_TAG_STYLE }}>{badge}</span>)}
          </div>
        ) : null}
        {actions?.length ? (
          <div style={STOCK_ACTIONS_STYLE}>
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
        {stock.executionHint ? <div style={STOCK_EXECUTION_HINT_STYLE}>{stock.executionHint}</div> : null}
      </div>
    </article>
  );
}

function riskToneStyle(value?: string): CSSProperties {
  const text = value ?? "";
  if (text.includes("高") || text.includes("阻断")) return { background: "#f9ece9", color: "var(--negative)" };
  if (text.includes("中") || text.includes("注意") || text.includes("降级")) return { background: "#fbf4e6", color: "var(--warning)" };
  if (text.includes("低") || text.includes("正常") || text.includes("清晰")) return { background: "#edf8f1", color: "var(--positive)" };
  return {};
}
