import type { BacktestRunSummary } from "../../api/backtests";
import type { StrategyHubTab } from "./useStrategyHub";

type WorkflowStep = {
  key: StrategyHubTab;
  title: string;
  description: string;
};

const STEPS: WorkflowStep[] = [
  { key: "quick", title: "1. 体检", description: "先判断策略还能不能用" },
  { key: "history", title: "2. 复盘", description: "看上次结果和变化" },
  { key: "optimize", title: "3. 优化", description: "只有历史通过了才调参数，不能先调好看再验证" },
  { key: "validate", title: "4. 验证", description: "防止策略只在历史里好看" },
];

export function StrategyWorkflowSteps({
  activeTab,
  runs,
  onSelect,
}: {
  activeTab: StrategyHubTab;
  runs: BacktestRunSummary[];
  onSelect: (tab: StrategyHubTab) => void;
}) {
  const latestCompleted = runs.find((run) => run.status === "completed" || run.status === "succeeded");
  return (
    <section className="panel strategy-workflow" aria-label="策略使用流程">
      {STEPS.map((step) => {
        const status = stepStatus(step.key, activeTab, Boolean(latestCompleted));
        return (
          <button
            key={step.key}
            type="button"
            className={activeTab === step.key ? "active" : ""}
            onClick={() => onSelect(step.key)}
          >
            <b>{step.title}</b>
            <span>{step.description}</span>
            <em className={status.tone}>{status.label}</em>
          </button>
        );
      })}
    </section>
  );
}

function stepStatus(tab: StrategyHubTab, activeTab: StrategyHubTab, hasCompletedRun: boolean) {
  if (tab === activeTab) return { label: "⏳ 正在查看", tone: "current" };
  if (tab === "quick" && hasCompletedRun) return { label: "✅ 已完成", tone: "done" };
  if (tab === "history" && hasCompletedRun) return { label: "✅ 有结果", tone: "done" };
  if (tab === "optimize" && !hasCompletedRun) return { label: "⚠ 先体检", tone: "warn" };
  if (tab === "validate" && !hasCompletedRun) return { label: "⚠ 先体检", tone: "warn" };
  return { label: "⚠ 建议执行", tone: "warn" };
}
