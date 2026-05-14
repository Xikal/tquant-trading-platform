import type { WatchDraft } from "./workspaceTypes";

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
    <div className="holding-wizard" aria-label={editing ? "编辑持仓步骤" : "录入持仓步骤"}>
      {steps.map((step) => (
        <article key={step.title}>
          <span>{step.title}</span>
          <strong>{step.value}</strong>
          <small>{step.helper}</small>
        </article>
      ))}
    </div>
  );
}
