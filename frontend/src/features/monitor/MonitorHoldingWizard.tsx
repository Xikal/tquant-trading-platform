import type { CSSProperties } from "react";
import type { WatchDraft } from "../workspace-shared/workspaceTypes";

const HOLDING_WIZARD_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
  gap: 8,
  margin: "10px 0 12px",
};

const HOLDING_WIZARD_CARD_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  minWidth: 0,
  border: "1px solid rgba(148, 163, 184, 0.24)",
  borderRadius: 12,
  background: "#ffffff",
  padding: 10,
};

const HOLDING_WIZARD_LABEL_STYLE: CSSProperties = {
  color: "#64748b",
  fontSize: 11,
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
      title: "1. 股票",
      value: draft.symbol.trim() || "先填代码或名称",
      helper: "系统会用它拉取行情和信号。",
    },
    {
      title: "2. 总持仓",
      value: draft.base_position.trim() ? `${draft.base_position} 股` : "您一共持有多少股",
      helper: "例：1000 股，包含今天不可卖的部分。",
    },
    {
      title: "3. 今天可卖",
      value: draft.available_position.trim() ? `${draft.available_position} 股` : "今天能卖多少股",
      helper: "A 股当天买入通常不能当天卖出。",
    },
    {
      title: "4. 成本价",
      value: draft.cost_basis.trim() ? `¥${draft.cost_basis}` : "买入均价",
      helper: "用于判断盈利、止损和做T空间。",
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
