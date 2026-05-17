import type { ReactNode } from "react";
import type { AiDecisionSupportResponse, LowBuyPriorityBoardResult } from "../../types";
import { directActionTitle, scoreStars } from "../../utils/uxClarity";
import { formatPct, normalizeLines, plainTradingText } from "./workspaceFormatters";
import type { MetricItem, StockCardView } from "./workspaceTypes";

export { MiniKline } from "./MiniKlineChart";

export function PanelTitle({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <div className="panel-title">
      <h2>{title}</h2>
      {actions ? <div className="actions">{actions}</div> : null}
    </div>
  );
}

export function MetricGrid({
  items,
  className = "",
  loading = false,
  as: Component = "div",
}: {
  items: MetricItem[];
  className?: string;
  loading?: boolean;
  as?: "div" | "section";
}) {
  return (
    <Component className={`metric-grid ${className}`}>
      {items.map((item) => (
        <div className={`metric ${item.tone}`} key={item.label}>
          <span>{item.label}</span>
          {loading ? <span className="skeleton-line strong" /> : <strong>{item.value}</strong>}
        </div>
      ))}
    </Component>
  );
}

export function InfoPill({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "up" | "down" | "neutral" | "warn" }) {
  return (
    <div className={`info-pill ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function EditableGrid({
  fields,
}: {
  fields: Array<[string, string, (value: string) => void]>;
}) {
  return (
    <div className="form-grid">
      {fields.map(([label, value, onChange]) => (
        <label key={label}>
          <span>{label}</span>
          <input value={value} onChange={(event) => onChange(event.target.value)} />
        </label>
      ))}
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
    <div className="stock-identity">
      <div className="identity-main">
        <strong>{name}</strong>
        <span>{symbol}</span>
      </div>
      {note ? <span className="identity-note">{note}</span> : null}
      {tags.length ? (
        <div className="identity-tags">
          {tags.map((tag) => <span key={tag}>{tag}</span>)}
        </div>
      ) : null}
    </div>
  );
}

export function StockCard({
  stock,
  actions,
  onAction,
}: {
  stock: StockCardView;
  actions?: string[];
  onAction?: (action: string) => void;
}) {
  return (
    <article className={`stock-card ${stock.tone} ${stock.highlight ? "highlight" : ""}`}>
      <StockIdentity name={stock.name} symbol={stock.symbol} note={stock.identityNote} tags={stock.identityTags} />
      <div className="stock-direct-action">
        <strong>{directActionTitle(stock.actionText)}</strong>
        {stock.scoreText ? <span title={`质量分 ${stock.scoreText}`}>质量 {scoreStars(stock.scoreText)}</span> : null}
      </div>
      <div className="stock-meta">
        <span>当前价 {stock.priceText}</span>
        <span className={stock.tone}>涨跌 {stock.changeText}</span>
        {stock.scoreText ? <span>质量分 {stock.scoreText}</span> : null}
        <span className={`stock-risk-tag ${riskToneClass(stock.riskText)}`}>风险 {stock.riskText}</span>
        {stock.expectedText ? <span>预期 {stock.expectedText}</span> : null}
      </div>
      {(stock.entryText || stock.stopText || stock.operationAmountText) ? (
        <div className="stock-operation-band">
          {stock.entryText ? <span><small>建议买入区间</small><strong>{stock.entryText}</strong></span> : null}
          {stock.stopText ? <span><small>止损价</small><strong>{stock.stopText}</strong></span> : null}
          {stock.operationAmountText ? <span><small>建议仓位/数量</small><strong>{stock.operationAmountText}</strong></span> : null}
        </div>
      ) : null}
      {stock.badges?.length ? (
        <div className="badge-row">
          {stock.badges.map((badge) => <span key={badge}>{badge}</span>)}
        </div>
      ) : null}
      {stock.subBadges?.length ? (
        <div className="badge-row sub-badge-row">
          {stock.subBadges.map((badge) => <span key={badge}>{badge}</span>)}
        </div>
      ) : null}
      {actions?.length ? (
        <div className="card-actions">
          {actions.map((action) => (
            <button
              type="button"
              className={action === "移除" ? "danger" : ""}
              onClick={(event) => {
                event.stopPropagation();
                onAction?.(action);
              }}
              key={action}
            >
              {action}
            </button>
          ))}
        </div>
      ) : null}
      {stock.executionHint ? <div className="stock-execution-hint">{stock.executionHint}</div> : null}
    </article>
  );
}

function riskToneClass(value?: string): string {
  const text = value ?? "";
  if (text.includes("高") || text.includes("阻断")) return "danger";
  if (text.includes("中") || text.includes("注意") || text.includes("降级")) return "warn";
  if (text.includes("低") || text.includes("正常") || text.includes("清晰")) return "ok";
  return "neutral";
}

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
    <div className={`panel setting-card ${className}`.trim()}>
      <PanelTitle title={title} />
      <div className="setting-fields">{children}</div>
      <button className={`primary ${saved ? "saved" : ""}`} onClick={onSave} disabled={loading || disabled}>
        {loading ? "保存中..." : saved ? "已保存" : button}
      </button>
    </div>
  );
}

export function EmptyState({ text, className = "" }: { text: string; className?: string }) {
  return <div className={`empty-state ${className}`}>{text}</div>;
}

export function StatusStrip({ loading: _loading, notice }: { loading: string; notice: string }) {
  if (!notice) {
    return null;
  }
  return (
    <div className="status-strip">
      {notice ? <span>{notice}</span> : null}
    </div>
  );
}

export function ErrorDialog({ message, onClose }: { message: string; onClose: () => void }) {
  if (!message) {
    return null;
  }
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal-card error-modal" role="alertdialog" aria-modal="true" aria-label="错误提示" onClick={(event) => event.stopPropagation()}>
        <div className="modal-title">
          <strong>操作失败</strong>
          <button type="button" onClick={onClose}>关闭</button>
        </div>
        <p>{message}</p>
      </div>
    </div>
  );
}

export function StockDetailDialog({ stock, onClose, onAnalyze }: { stock: StockCardView | null; onClose: () => void; onAnalyze: (stock: StockCardView) => void }) {
  if (!stock) {
    return null;
  }
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal-card detail-modal" role="dialog" aria-modal="true" aria-label="信号详情" onClick={(event) => event.stopPropagation()}>
        <div className="modal-title">
          <strong>{stock.name} {stock.symbol}</strong>
          <button type="button" onClick={onClose}>关闭</button>
        </div>
        <div className="modal-metrics">
          <InfoPill label="当前价" value={stock.priceText} />
          <InfoPill label="涨跌" value={stock.changeText} />
          <InfoPill label="风险" value={stock.riskText} />
          <InfoPill label="板块" value={stock.sectorText || "--"} />
        </div>
        <p><strong>{stock.actionText}</strong></p>
        <p>{stock.details}</p>
        {stock.executionHint ? <div className="stock-execution-hint">{stock.executionHint}</div> : null}
        {stock.badges?.length ? (
          <div className="badge-row">
            {stock.badges.map((badge) => <span key={badge}>{badge}</span>)}
          </div>
        ) : null}
        {stock.subBadges?.length ? (
          <div className="badge-row sub-badge-row">
            {stock.subBadges.map((badge) => <span key={badge}>{badge}</span>)}
          </div>
        ) : null}
        <div className="card-actions modal-actions">
          <button type="button" onClick={() => onAnalyze(stock)}>分析</button>
          <button type="button" onClick={onClose}>知道了</button>
        </div>
      </div>
    </div>
  );
}

export function FamilyStrip({ priorityBoard }: { priorityBoard: LowBuyPriorityBoardResult | null }) {
  const sections = priorityBoard?.family_sections ?? [];
  if (!sections.length) {
    return null;
  }
  return (
    <div className="family-strip">
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
    <div className="ai-result">
      <strong>{response.title}</strong>
      <p>{plainTradingText(response.insight.summary)}</p>
      <div className="report-pill-row">
        <span>模型 {response.model || "未配置"}</span>
        <span>置信度 {formatPct(response.insight.confidence * 100, 0)}</span>
        <span>{response.insight.enabled ? "AI 已启用" : "量化降级"}</span>
      </div>
      {response.fixed_sections ? (
        <div className="ai-fixed-grid">
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
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal-card ai-modal" role="dialog" aria-modal="true" aria-label="AI 解读榜单" onClick={(event) => event.stopPropagation()}>
        <div className="modal-title">
          <strong>AI 解读榜单</strong>
          <button type="button" onClick={onClose}>关闭</button>
        </div>
        {loading ? (
          <div className="empty-state">AI 正在读取榜单并生成分析...</div>
        ) : response ? (
          <AiInsightPanel response={response} />
        ) : null}
      </div>
    </div>
  );
}

export function LineList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="line-list">
      <span>{title}</span>
      <ul>
        {items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
      </ul>
    </div>
  );
}
