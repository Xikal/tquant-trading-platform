import type { CSSProperties, ReactNode } from "react";
import { Button, Input, Modal, Skeleton } from "antd";
import type { AiDecisionSupportResponse, LowBuyPriorityBoardResult } from "../../types";
import { formatPct, normalizeLines, plainTradingText } from "./workspaceFormatters";
import type { MetricItem, StockCardView, Tone } from "./workspaceTypes";
import {
  DISPLAY_TONE_VALUE_STYLES,
  INFO_PILL_STYLE,
  INFO_PILL_TEXT_STYLE,
  METRIC_GRID_COMPACT_STYLE,
  METRIC_GRID_STYLE,
  METRIC_TONE_STYLES,
  METRIC_COMPACT_STYLE,
  METRIC_STYLE,
  METRIC_TEXT_COMPACT_STYLE,
  METRIC_TEXT_STYLE,
  METRIC_VALUE_COMPACT_STYLE,
  METRIC_VALUE_STYLE,
} from "./workspaceDisplayStyles";

export { MiniKline } from "./MiniKlineChart";

const METRIC_SKELETON_STYLE: CSSProperties = {
  width: "78%",
  minHeight: 19,
};

const AI_RESULT_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  marginTop: 8,
  padding: 8,
  borderRadius: 8,
  background: "var(--muted-bg)",
};

const AI_FIXED_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
};

const LINE_LIST_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
};

const LINE_LIST_TITLE_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontSize: 11,
  fontWeight: 700,
};

const LINE_LIST_BODY_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  margin: 0,
  paddingLeft: 16,
};

const LINE_LIST_ITEM_STYLE: CSSProperties = {
  color: "var(--text)",
  fontSize: 11,
  lineHeight: 1.45,
};

const CONTEXT_ROW_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
};

const FAMILY_STRIP_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: 8,
  margin: "8px 0",
};

const PANEL_TITLE_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 8,
  marginBottom: 6,
};

const PANEL_TITLE_HEADING_STYLE: CSSProperties = {
  margin: 0,
  fontSize: 13,
  lineHeight: 1.2,
};

const PANEL_TITLE_ACTIONS_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 6,
};

const SETTING_CARD_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  minHeight: 216,
};

const SETTING_FIELDS_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
};

const SETTING_BUTTON_STYLE: CSSProperties = {
  width: "fit-content",
  marginTop: "auto",
};

const SETTING_BUTTON_SAVED_STYLE: CSSProperties = {
  borderColor: "#16a34a",
  background: "#16a34a",
  color: "#fff",
};

const EMPTY_STATE_STYLE: CSSProperties = {
  display: "block",
  marginBottom: 5,
  borderRadius: 7,
  background: "var(--muted-bg)",
  color: "var(--muted)",
  padding: 6,
  fontSize: 11,
};

const MODAL_METRICS_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
  gap: 6,
};

const EDITABLE_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
  gridTemplateColumns: "1fr 1fr",
};

const EDITABLE_GRID_LABEL_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
};

const REPORT_PILL_ROW_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 6,
};

const REPORT_PILL_STYLE: CSSProperties = {
  borderRadius: 999,
  background: "#eef2f7",
  color: "#435168",
  fontSize: 11,
  fontWeight: 700,
  padding: "3px 7px",
};

const STATUS_STRIP_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  marginBottom: 8,
  borderRadius: 8,
  background: "var(--muted-bg)",
  color: "var(--muted)",
  padding: "6px 8px",
  fontSize: 11,
};

const STOCK_DETAIL_BADGE_ROW_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 6,
};

const STOCK_DETAIL_BADGE_STYLE: CSSProperties = {
  borderRadius: 999,
  background: "#eef2f7",
  color: "#435168",
  fontSize: 11,
  fontWeight: 700,
  padding: "3px 7px",
};

const STOCK_DETAIL_SUB_BADGE_STYLE: CSSProperties = {
  ...STOCK_DETAIL_BADGE_STYLE,
  background: "#fff7e6",
  color: "#9a5a00",
};

const STOCK_DETAIL_HINT_STYLE: CSSProperties = {
  gridColumn: "1 / -1",
  border: "1px solid #f3d49c",
  borderRadius: 6,
  background: "#fff7e8",
  color: "#7a4b00",
  padding: "6px 8px",
  fontSize: 12,
  lineHeight: 1.45,
};

export function PanelTitle({ title, actions, style }: { title: string; actions?: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{ ...PANEL_TITLE_STYLE, ...style }}>
      <h2 style={PANEL_TITLE_HEADING_STYLE}>{title}</h2>
      {actions ? <div style={PANEL_TITLE_ACTIONS_STYLE}>{actions}</div> : null}
    </div>
  );
}

export function MetricGrid({
  items,
  className = "",
  loading = false,
  as: Component = "div",
  style,
}: {
  items: MetricItem[];
  className?: string;
  loading?: boolean;
  as?: "div" | "section";
  style?: CSSProperties;
}) {
  const compact = className.includes("compact");
  return (
    <Component style={{ ...METRIC_GRID_STYLE, ...(compact ? METRIC_GRID_COMPACT_STYLE : undefined), ...style }}>
      {items.map((item) => (
        <div key={item.label} style={{ ...METRIC_STYLE, ...(METRIC_TONE_STYLES[item.tone] ?? undefined), ...(compact ? METRIC_COMPACT_STYLE : undefined) }}>
          <span style={compact ? { ...METRIC_TEXT_STYLE, ...METRIC_TEXT_COMPACT_STYLE } : METRIC_TEXT_STYLE}>{item.label}</span>
          {loading ? <Skeleton.Input active size="small" style={METRIC_SKELETON_STYLE} /> : <strong style={{ ...(compact ? { ...METRIC_VALUE_STYLE, ...METRIC_VALUE_COMPACT_STYLE } : METRIC_VALUE_STYLE), ...DISPLAY_TONE_VALUE_STYLES[item.tone] }}>{item.value}</strong>}
        </div>
      ))}
    </Component>
  );
}

export function toneTextStyle(tone: Tone): CSSProperties | undefined {
  return DISPLAY_TONE_VALUE_STYLES[tone];
}

export { Callout } from "./Callout";

export function ContextRow({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return <div style={{ ...CONTEXT_ROW_STYLE, ...style }}>{children}</div>;
}

export function InfoPill({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "up" | "down" | "neutral" | "warn" }) {
  return (
    <div style={INFO_PILL_STYLE}>
      <span style={INFO_PILL_TEXT_STYLE}>{label}</span>
      <strong style={{ ...INFO_PILL_TEXT_STYLE, ...DISPLAY_TONE_VALUE_STYLES[tone] }}>{value}</strong>
    </div>
  );
}

export function EditableGrid({
  fields,
}: {
  fields: Array<[string, string, (value: string) => void]>;
}) {
  return (
    <div style={EDITABLE_GRID_STYLE}>
      {fields.map(([label, value, onChange]) => (
        <label key={label} style={EDITABLE_GRID_LABEL_STYLE}>
          <span>{label}</span>
          <Input value={value} onChange={(event) => onChange(event.target.value)} />
        </label>
      ))}
    </div>
  );
}

export { StockCard, StockCardList, StockIdentity } from "./StockCard";

export function SettingCard({
  title,
  children,
  button,
  loading,
  saved = false,
  disabled = false,
  className = "",
  onSave,
}: {
  title: string;
  children: ReactNode;
  button: string;
  loading: boolean;
  saved?: boolean;
  disabled?: boolean;
  className?: string;
  onSave: () => void;
}) {
  return (
    <div className={`panel ${className}`.trim()} style={SETTING_CARD_STYLE}>
      <PanelTitle title={title} />
      <div style={SETTING_FIELDS_STYLE}>{children}</div>
      <Button
        type="primary"
        style={saved ? { ...SETTING_BUTTON_STYLE, ...SETTING_BUTTON_SAVED_STYLE } : SETTING_BUTTON_STYLE}
        onClick={onSave}
        disabled={loading || disabled}
        loading={loading}
      >
        {loading ? "保存中..." : saved ? "已保存" : button}
      </Button>
    </div>
  );
}

export function EmptyState({ text, className = "" }: { text: string; className?: string }) {
  return <div className={className || undefined} style={EMPTY_STATE_STYLE}>{text}</div>;
}

export function StatusStrip({ loading: _loading, notice }: { loading: string; notice: string }) {
  if (!notice) {
    return null;
  }
  return (
    <div style={STATUS_STRIP_STYLE}>
      <span>{notice}</span>
    </div>
  );
}

export function ErrorDialog({ message, onClose }: { message: string; onClose: () => void }) {
  if (!message) {
    return null;
  }
  return (
    <Modal
      open
      title="操作失败"
      onCancel={onClose}
      footer={<Button onClick={onClose}>关闭</Button>}
      centered
      destroyOnHidden
    >
      <p>{message}</p>
    </Modal>
  );
}

export function StockDetailDialog({ stock, onClose, onAnalyze }: { stock: StockCardView | null; onClose: () => void; onAnalyze: (stock: StockCardView) => void }) {
  if (!stock) {
    return null;
  }
  return (
    <Modal
      open
      title={`${stock.name} ${stock.symbol}`}
      onCancel={onClose}
      width={720}
      centered
      destroyOnHidden
      footer={[
        <Button key="analyze" type="primary" onClick={() => onAnalyze(stock)}>分析</Button>,
        <Button key="close" onClick={onClose}>知道了</Button>,
      ]}
    >
      <div style={MODAL_METRICS_STYLE}>
        <InfoPill label="当前价" value={stock.priceText} />
        <InfoPill label="涨跌" value={stock.changeText} />
        <InfoPill label="风险" value={stock.riskText} />
        <InfoPill label="板块" value={stock.sectorText || "--"} />
      </div>
      <p><strong>{stock.actionText}</strong></p>
      <p>{stock.details}</p>
      {stock.executionHint ? <div style={STOCK_DETAIL_HINT_STYLE}>{stock.executionHint}</div> : null}
      {stock.badges?.length ? (
        <div style={STOCK_DETAIL_BADGE_ROW_STYLE}>
          {stock.badges.map((badge) => <span key={badge} style={STOCK_DETAIL_BADGE_STYLE}>{badge}</span>)}
        </div>
      ) : null}
      {stock.subBadges?.length ? (
        <div style={STOCK_DETAIL_BADGE_ROW_STYLE}>
          {stock.subBadges.map((badge) => <span key={badge} style={STOCK_DETAIL_SUB_BADGE_STYLE}>{badge}</span>)}
        </div>
      ) : null}
    </Modal>
  );
}

export function FamilyStrip({ priorityBoard }: { priorityBoard: LowBuyPriorityBoardResult | null }) {
  const sections = priorityBoard?.family_sections ?? [];
  if (!sections.length) {
    return null;
  }
  return (
    <div style={FAMILY_STRIP_STYLE}>
      {sections.slice(0, 4).map((section) => (
        <InfoPill
          key={section.family_key}
          label={section.family_text}
          value={`${section.total_candidates} 只 / 净胜优势 ${formatPct(section.performance?.net_win_rate, 0)}`}
        />
      ))}
    </div>
  );
}

export function AiInsightPanel({ response }: { response: AiDecisionSupportResponse }) {
  const suggestions = normalizeLines(response.insight.suggestions).map(plainTradingText);
  const warnings = normalizeLines(response.insight.warnings).map(plainTradingText);
  return (
    <div style={AI_RESULT_STYLE}>
      <strong>{response.title}</strong>
      <p>{plainTradingText(response.insight.summary)}</p>
      <div style={REPORT_PILL_ROW_STYLE}>
        <span style={REPORT_PILL_STYLE}>模型 {response.model || "未配置"}</span>
        <span style={REPORT_PILL_STYLE}>置信度 {formatPct(response.insight.confidence * 100, 0)}</span>
        <span style={REPORT_PILL_STYLE}>{response.insight.enabled ? "AI 已启用" : "量化降级"}</span>
      </div>
      {response.fixed_sections ? (
        <div style={AI_FIXED_GRID_STYLE}>
          <InfoPill label="能不能买" value={response.fixed_sections.can_buy} />
          <InfoPill label="为什么" value={response.fixed_sections.why} />
          <InfoPill label="最大风险" value={response.fixed_sections.main_risk} />
          <InfoPill label="明天处理" value={response.fixed_sections.tomorrow_plan} />
        </div>
      ) : null}
      {suggestions.length ? <LineList title="执行要点" items={suggestions} /> : null}
      {warnings.length ? <LineList title="风险提示" items={warnings} /> : null}
    </div>
  );
}

export function AiInsightDialog({
  response,
  loading,
  onClose,
}: {
  response: AiDecisionSupportResponse | null;
  loading: boolean;
  onClose: () => void;
}) {
  if (!response && !loading) {
    return null;
  }
  return (
    <Modal
      open
      title="AI 解读榜单"
      onCancel={onClose}
      footer={<Button onClick={onClose}>关闭</Button>}
      width={720}
      centered
      destroyOnHidden
    >
      {loading ? (
        <div style={EMPTY_STATE_STYLE}>AI 正在读取榜单并生成分析...</div>
      ) : response ? (
        <AiInsightPanel response={response} />
      ) : null}
    </Modal>
  );
}

export function LineList({ title, items }: { title: string; items: string[] }) {
  return (
    <div style={LINE_LIST_STYLE}>
      <span style={LINE_LIST_TITLE_STYLE}>{title}</span>
      <ul style={LINE_LIST_BODY_STYLE}>
        {items.map((item, index) => <li key={`${item}-${index}`} style={LINE_LIST_ITEM_STYLE}>{item}</li>)}
      </ul>
    </div>
  );
}
