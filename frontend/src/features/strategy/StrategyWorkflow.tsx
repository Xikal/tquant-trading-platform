import { Card, Space, Steps, Tag, Typography } from "antd";
import type { BacktestRunSummary } from "../../api/backtests";
import type { StrategyHubTab } from "./useStrategyHub";

type DisplayStep = "quick" | "history" | "signals" | "expert";
type FlowMode = "simple" | "expert";
type FlowStep = {
  id: string;
  step: DisplayStep;
  target: StrategyHubTab;
  preserveCurrentExpertTab?: boolean;
  title: string;
  description: string;
};

const SIMPLE_STEPS: FlowStep[] = [
  { id: "quick", step: "quick", target: "quick", title: "1. 策略体检", description: "先判断策略还能不能用" },
  { id: "history", step: "history", target: "history", title: "2. 查看结果", description: "看最新收益、胜率和结论" },
  { id: "signals", step: "signals", target: "signals", title: "3. 信号复盘", description: "看哪些信号有效，哪些失败" },
  {
    id: "expert",
    step: "expert",
    target: "optimize",
    preserveCurrentExpertTab: true,
    title: "4. 专家工具",
    description: "通过了再调参数，不先调好看再验证",
  },
];

const EXPERT_STEPS: FlowStep[] = [
  { id: "quick", step: "quick", target: "quick", title: "1. 体检", description: "先判断策略还能不能用" },
  { id: "history", step: "history", target: "history", title: "2. 复盘", description: "看上次结果和变化" },
  { id: "optimize", step: "expert", target: "optimize", title: "3. 优化", description: "只有历史通过了才调参数" },
  { id: "validate", step: "expert", target: "validate", title: "4. 验证", description: "防止策略只在历史里好看" },
  { id: "factor", step: "expert", target: "factor", title: "5. 因子实验室", description: "挖掘新因子，验证后再接入" },
];

export function StrategyWorkflow({
  activeTab,
  runs,
  mode,
  showExpert,
  onSelect,
}: {
  activeTab: StrategyHubTab;
  runs: BacktestRunSummary[];
  mode: FlowMode;
  showExpert: boolean;
  onSelect: (tab: StrategyHubTab) => void;
}) {
  const activeStep = tabToStep(activeTab);
  const hasResult = runs.some((run) => run.status === "completed" || run.status === "succeeded");
  const steps = (mode === "expert" ? EXPERT_STEPS : SIMPLE_STEPS).filter((step) => showExpert || step.step !== "expert");
  const activeIndex = steps.findIndex((step) => (mode === "expert" ? step.target === activeTab : tabToStep(step.target) === activeStep));

  return (
    <Card variant="borderless" aria-label="策略工作流程" styles={{ body: { padding: 8 } }}>
      <Steps
        size="small"
        current={activeIndex < 0 ? 0 : activeIndex}
        responsive
        onChange={(current) => {
          const step = steps[current];
          if (!step) return;
          onSelect(stepToTab(step.target, activeTab, step.preserveCurrentExpertTab));
        }}
        items={steps.map((step) => {
          const status = stepBadge(step.step, activeStep, hasResult);
          return {
            title: <Typography.Text strong>{step.title}</Typography.Text>,
            description: (
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">{step.description}</Typography.Text>
                <Tag color={status.color}>{status.label}</Tag>
              </Space>
            ),
            status: status.status,
          };
        })}
      />
    </Card>
  );
}

function tabToStep(tab: StrategyHubTab): DisplayStep {
  if (tab === "quick") return "quick";
  if (tab === "history") return "history";
  if (tab === "signals") return "signals";
  return "expert";
}

function stepToTab(step: StrategyHubTab, activeTab: StrategyHubTab, preserveCurrentExpertTab = false): StrategyHubTab {
  if (step === "optimize" && preserveCurrentExpertTab) {
    return ["optimize", "validate", "compare", "capacity", "factor"].includes(activeTab) ? activeTab : "optimize";
  }
  return step;
}

function stepBadge(step: DisplayStep, active: DisplayStep, hasResult: boolean) {
  if (step === active) return { label: "当前步骤", color: "processing", status: "process" as const };
  if ((step === "quick" || step === "history") && hasResult) return { label: "已完成", color: "success", status: "finish" as const };
  if (step === "signals" && hasResult) return { label: "可查看", color: "success", status: "finish" as const };
  if (step === "expert" && !hasResult) return { label: "先体检", color: "warning", status: "wait" as const };
  return { label: "建议执行", color: "warning", status: "wait" as const };
}
