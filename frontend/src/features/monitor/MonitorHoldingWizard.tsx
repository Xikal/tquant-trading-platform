import type { CSSProperties } from "react";
import type { WatchDraft } from "../workspace-shared/workspaceTypes";

const HOLDING_WIZARD_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: 6,
  margin: "6px 0 8px",
};

const HOLDING_WIZARD_CARD_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  minWidth: 0,
  border: "1px solid rgba(148, 163, 184, 0.24)",
  borderRadius: 8,
  background: "#ffffff",
  padding: 7,
};

const HOLDING_WIZARD_LABEL_STYLE: CSSProperties = {
  color: "#64748b",
  fontSize: 12,
  lineHeight: 1.35,
};

const HOLDING_WIZARD_VALUE_STYLE: CSSProperties = {
  color: "#0f172a",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export function MonitorHoldingWizard({
  draft,
  editing,
}: {
  draft: WatchDraft;
  editing: boolean;
}) {
  const steps = [
    {
      title: "股票",
      value: draft.symbol.trim() || "先填代码或名称",
      helper: "用于行情和信号。",
    },
    {
      title: "总持仓",
      value: draft.base_position.trim() ? `${draft.base_position} 股` : "您一共持有多少股",
      helper: "含不可卖数量。",
    },
    {
      title: "今天可卖",
      value: draft.available_position.trim() ? `${draft.available_position} 股` : "今天能卖多少股",
      helper: "按 T+1 约束。",
    },
    {
      title: "成本价",
      value: draft.cost_basis.trim() ? `¥${draft.cost_basis}` : "买入均价",
      helper: "用于盈亏边界。",
    },
  ];

  return (
    <div style={HOLDING_WIZARD_STYLE} aria-label={editing ? "编辑持仓步骤" : "录入持仓步骤"}>
      {steps.map((step) => (
        <article key={step.title} style={HOLDING_WIZARD_CARD_STYLE}>
          <span style={HOLDING_WIZARD_LABEL_STYLE}>{step.title}</span>
          <strong style={HOLDING_WIZARD_VALUE_STYLE}>{step.value}</strong>
          <small style={HOLDING_WIZARD_LABEL_STYLE}>{step.helper}</small>
        </article>
      ))}
    </div>
  );
}
