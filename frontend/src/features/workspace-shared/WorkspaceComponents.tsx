import type { CSSProperties, ReactNode } from "react";
import { Button, Input, Modal, Skeleton } from "antd";
import type { AiDecisionSupportResponse } from "../../types";
import { formatPct, normalizeLines, plainTradingText } from "./workspaceFormatters";
import type { MetricItem, StockCardView, Tone } from "./workspaceTypes";
import { PriceText, StatTile } from "../../ui/data";
import { Panel, SectionHeader } from "../../ui/surfaces";
import {
  DISPLAY_TONE_VALUE_STYLES,
  METRIC_GRID_COMPACT_STYLE,
  METRIC_GRID_STYLE,
} from "./workspaceDisplayStyles";

export { MiniKline } from "./MiniKlineChart";

const METRIC_SKELETON_STYLE: CSSProperties = {
  width: "78%",
  minHeight: 19,
};

export function PanelTitle({
  title,
  actions,
  className = "",
  style,
}: {
  title: string;
  actions?: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={className} style={style}>
      <SectionHeader title={title} actions={actions ? <div className="tq-section-header__actions">{actions}</div> : undefined} />
    </div>
  );
}

export function MetricGrid({
  items,
  className = "",
  loading = false,
  as: Component = "div",
  compact: compactProp = false,
  style,
}: {
  items: MetricItem[];
  className?: string;
  loading?: boolean;
  as?: "div" | "section";
  compact?: boolean;
  style?: CSSProperties;
}) {
  const compact = compactProp || className.includes("compact");
  const gridClassName = ["tq-metric-grid", compact ? "tq-metric-grid--compact" : "", className].filter(Boolean).join(" ");
  return (
    <Component className={gridClassName} style={{ ...METRIC_GRID_STYLE, ...(compact ? METRIC_GRID_COMPACT_STYLE : undefined), ...style }}>
      {items.map((item) => (
        <StatTile
          key={item.label}
          label={item.label}
          value={loading ? <Skeleton.Input active size="small" style={METRIC_SKELETON_STYLE} /> : item.value}
          delta={undefined}
        />
      ))}
    </Component>
  );
}

export function toneTextStyle(tone: Tone): CSSProperties | undefined {
  return DISPLAY_TONE_VALUE_STYLES[tone];
}

export { Callout } from "./Callout";

export function ContextRow({ children, className = "", style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return <div className={`tq-context-row ${className}`.trim()} style={style}>{children}</div>;
}

export function InfoPill({
  label,
  value,
  tone = "neutral",
  compact = false,
}: {
  label: string;
  value: string;
  tone?: "up" | "down" | "neutral" | "warn";
  compact?: boolean;
}) {
  return (
    <div className={`tq-info-pill ${compact ? "tq-info-pill--compact" : ""}`.trim()}>
      <span className="tq-info-pill__label">{label}</span>
      <strong className={`tq-info-pill__value tq-info-pill__value--${tone}`.trim()}>{value}</strong>
    </div>
  );
}

export function PriceToneBadge({ value }: { value: number | null | undefined }) {
  return <PriceText value={value ?? null} />;
}

export function ContentPanel({ title, children, extra }: { title?: ReactNode; children: ReactNode; extra?: ReactNode }) {
  return (
    <Panel title={title} extra={extra}>
      {children}
    </Panel>
  );
}

export function EditableGrid({
  fields,
}: {
  fields: Array<[string, string, (value: string) => void]>;
}) {
  return (
    <div className="tq-editable-grid">
      {fields.map(([label, value, onChange]) => (
        <label key={label} className="tq-editable-grid__label">
          <span>{label}</span>
          <Input value={value} onChange={(event) => onChange(event.target.value)} />
        </label>
      ))}
    </div>
  );
}

export { StockCard, StockCardList, StockIdentity } from "./StockCard";
export { FamilyStrip } from "./FamilyStrip";

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
    <Panel className={`tq-setting-card ${className}`.trim()} title={title}>
      <div className="tq-setting-card__fields">{children}</div>
      <Button
        type="primary"
        className={`tq-setting-card__save ${saved ? "tq-setting-card__save--saved" : ""}`.trim()}
        onClick={onSave}
        disabled={loading || disabled}
        loading={loading}
      >
        {loading ? "保存中..." : saved ? "已保存" : button}
      </Button>
    </Panel>
  );
}

export function EmptyState({ text, className = "" }: { text: string; className?: string }) {
  return <div className={`tq-empty-state ${className}`.trim()}>{text}</div>;
}

export function StatusStrip({ loading: _loading, notice }: { loading: string; notice: string }) {
  if (!notice) {
    return null;
  }
  return (
    <div className="tq-status-strip">
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
      <div className="tq-modal-metrics">
        <InfoPill label="当前价" value={stock.priceText} />
        <InfoPill label="涨跌" value={stock.changeText} />
        <InfoPill label="风险" value={stock.riskText} />
        <InfoPill label="板块" value={stock.sectorText || "--"} />
      </div>
      <p><strong>{stock.actionText}</strong></p>
      <p>{stock.details}</p>
      {stock.executionHint ? <div className="tq-stock-detail-hint">{stock.executionHint}</div> : null}
      {stock.badges?.length ? (
        <div className="tq-stock-detail-row">
          {stock.badges.map((badge) => <span key={badge} className="tq-stock-detail-badge">{badge}</span>)}
        </div>
      ) : null}
      {stock.subBadges?.length ? (
        <div className="tq-stock-detail-row">
          {stock.subBadges.map((badge) => <span key={badge} className="tq-stock-detail-badge tq-stock-detail-badge--sub">{badge}</span>)}
        </div>
      ) : null}
    </Modal>
  );
}

export function AiInsightPanel({ response }: { response: AiDecisionSupportResponse }) {
  const suggestions = normalizeLines(response.insight.suggestions).map(plainTradingText);
  const warnings = normalizeLines(response.insight.warnings).map(plainTradingText);
  return (
    <div className="tq-ai-panel">
      <strong>{response.title}</strong>
      <p className="tq-ai-panel__summary">{plainTradingText(response.insight.summary)}</p>
      <div className="tq-report-pill-row">
        <span className="tq-report-pill">模型 {response.model || "未配置"}</span>
        <span className="tq-report-pill">置信度 {formatPct(response.insight.confidence * 100, 0)}</span>
        <span className="tq-report-pill">{response.insight.enabled ? "AI 已启用" : "量化降级"}</span>
      </div>
      {response.fixed_sections ? (
        <div className="tq-ai-panel__fixed-grid">
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
        <div className="tq-empty-state">AI 正在读取榜单并生成分析...</div>
      ) : response ? (
        <AiInsightPanel response={response} />
      ) : null}
    </Modal>
  );
}

export function LineList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="tq-line-list">
      <span className="tq-line-list__title">{title}</span>
      <ul className="tq-line-list__items">
        {items.map((item, index) => <li key={`${item}-${index}`} className="tq-line-list__item">{item}</li>)}
      </ul>
    </div>
  );
}
