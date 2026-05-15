import type { BacktestRunSummary } from "../../api/backtests";
import type { StrategyHubTab } from "./useStrategyHub";

type DisplayStep = "quick" | "history" | "signals" | "expert";

const STEPS: Array<{ key: DisplayStep; title: string; description: string }> = [
  { key: "quick", title: "1. 策略体检", description: "先判断策略还能不能用" },
  { key: "history", title: "2. 查看结果", description: "看最新收益、胜率和结论" },
  { key: "signals", title: "3. 信号复盘", description: "看哪些信号有效，哪些失败" },
  { key: "expert", title: "4. 专家工具", description: "通过了再调参数，不先调好看再验证" },
];

export function StrategyHubSimpleFlow({
  activeTab,
  runs,
  showExpert,
  onSelect,
}: {
  activeTab: StrategyHubTab;
  runs: BacktestRunSummary[];
  showExpert: boolean;
  onSelect: (tab: StrategyHubTab) => void;
}) {
  const activeStep = tabToStep(activeTab);
  const hasResult = runs.some((run) => run.status === "completed" || run.status === "succeeded");
  const steps = showExpert ? STEPS : STEPS.filter((step) => step.key !== "expert");

  return (
    <section className="panel strategy-simple-flow" aria-label="策略工作流程">
      {steps.map((step) => {
        const status = stepBadge(step.key, activeStep, hasResult);
        return (
          <button
            key={step.key}
            type="button"
            className={activeStep === step.key ? "active" : ""}
            onClick={() => onSelect(stepToTab(step.key, activeTab))}
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

function tabToStep(tab: StrategyHubTab): DisplayStep {
  if (tab === "quick") return "quick";
  if (tab === "history") return "history";
  if (tab === "signals") return "signals";
  return "expert";
}

function stepToTab(step: DisplayStep, activeTab: StrategyHubTab): StrategyHubTab {
  if (step === "expert") {
    return ["optimize", "validate", "compare", "capacity"].includes(activeTab) ? activeTab : "optimize";
  }
  return step;
}

function stepBadge(step: DisplayStep, active: DisplayStep, hasResult: boolean) {
  if (step === active) return { label: "⏳ 当前步骤", tone: "current" };
  if ((step === "quick" || step === "history") && hasResult) return { label: "✅ 已完成", tone: "done" };
  if (step === "signals" && hasResult) return { label: "✅ 可查看", tone: "done" };
  if (step === "expert" && !hasResult) return { label: "⚠ 先体检", tone: "warn" };
  return { label: "⚠ 建议执行", tone: "warn" };
}
