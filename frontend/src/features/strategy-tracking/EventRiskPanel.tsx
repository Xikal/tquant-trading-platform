import { Alert, Tag } from "antd";
import type { DecisionContextAttribution, DecisionContextEventRisk } from "../../types";

export function EventRiskPanel({ context }: { context?: DecisionContextAttribution }) {
  const risk = resolveEventRisk(context);
  const dataQuality = risk.data_quality || context?.gates?.event_risk_gate?.decision || "missing";
  const reasons = risk.reasons?.length ? risk.reasons : context?.gates?.event_risk_gate?.reasons ?? [];
  return (
    <section className="strategy-tracking-detail-section">
      <div className="strategy-tracking-review-head">
        <strong>事件风险</strong>
        <span>{eventRiskStatusText(dataQuality, risk.decision)}</span>
      </div>
      <div className="strategy-tracking-tag-row">
        <Tag color={eventRiskTone(risk.severity || risk.decision)}>{severityText(risk.severity || "missing")}</Tag>
        <Tag>{risk.impact_window || "影响周期缺失"}</Tag>
        <Tag>{risk.production_blocked ? "生产阻断" : "摘要/复盘"}</Tag>
      </div>
      <Alert
        type={risk.production_blocked ? "error" : dataQuality === "missing" ? "warning" : "info"}
        showIcon
        title={risk.summary || reasons[0] || "公告/事件源缺失"}
        description={reasons.join("；") || "事件风险只显示结构化摘要，不输出买卖建议。"}
      />
      <div className="strategy-tracking-context-gates">
        {(risk.risk_types ?? []).map((item) => <Tag key={item}>{item}</Tag>)}
        {(risk.evidence_ids ?? []).map((item) => <Tag key={item}>证据 {item}</Tag>)}
      </div>
    </section>
  );
}

function resolveEventRisk(context?: DecisionContextAttribution): DecisionContextEventRisk {
  const gate = context?.gates?.event_risk_gate;
  const evidence = gate?.evidence ?? {};
  return {
    decision: stringValue(evidence.decision) || gate?.decision,
    severity: stringValue(evidence.severity),
    data_quality: stringValue(evidence.data_quality) || (gate?.decision === "no_data" ? "missing" : undefined),
    summary: stringValue(evidence.summary),
    risk_types: stringList(evidence.risk_types),
    impact_window: stringValue(evidence.impact_window),
    evidence_ids: stringList(evidence.evidence_ids),
    reasons: stringList(evidence.reasons).length ? stringList(evidence.reasons) : gate?.reasons ?? [],
    production_blocked: evidence.production_blocked === true || gate?.decision === "block",
  };
}

function eventRiskStatusText(dataQuality: string, decision?: string): string {
  if (dataQuality === "missing" || decision === "no_data") return "数据缺失";
  if (decision === "block") return "高风险阻断";
  if (decision === "research_only") return "仅摘要";
  return decision || "待生成";
}

function severityText(value: string): string {
  return {
    high: "高风险",
    medium: "中风险",
    low: "低风险",
    unknown: "风险未知",
    missing: "数据缺失",
  }[value] ?? value;
}

function eventRiskTone(value?: string): string {
  if (value === "high" || value === "block") return "red";
  if (value === "medium" || value === "research_only") return "gold";
  if (value === "low") return "green";
  return "default";
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item || "")).filter(Boolean) : [];
}
