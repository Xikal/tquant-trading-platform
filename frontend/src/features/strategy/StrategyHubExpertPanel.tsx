import type { AuthUser } from "../../types";
import { BacktestResearchPanel, type BacktestResearchSection } from "../backtest/BacktestResearchPanel";
import { useBacktestDashboard } from "../backtest/useBacktestDashboard";
import type { StrategyHubTab } from "./useStrategyHub";
import { canOptimize, canValidate, isAdmin } from "./strategyPermissions";

type ExpertTabKey = Extract<StrategyHubTab, "optimize" | "validate" | "compare" | "capacity">;

export function StrategyHubExpertPanel({
  tab,
  currentUser,
}: {
  tab: ExpertTabKey;
  currentUser: AuthUser;
}) {
  const meta = EXPERT_META[tab];
  if (tab === "optimize" && !canOptimize(currentUser)) {
    return <PermissionPanel title="需要参数优化权限" description="当前账号可以查看回测和信号复盘，但不能创建参数优化任务。" />;
  }
  if (tab === "validate" && !canValidate(currentUser)) {
    return <PermissionPanel title="需要研究员权限" description="当前账号可以查看回测和信号复盘，但不能创建样本外验证任务。" />;
  }
  if (tab === "capacity" && !isAdmin(currentUser)) {
    return <PermissionPanel title="需要管理员权限" description="ML 在线学习、手动增量训练和容量评估会读取训练样本与模型状态，仅管理员可操作。" />;
  }

  const dashboard = useBacktestDashboard(sectionForTab(tab));
  return (
    <div className="strategy-bridge">
      <section className="panel strategy-bridge-header">
        <h2>{meta[0]}</h2>
        <p>{meta[1]}</p>
      </section>
      <BacktestResearchPanel
        state={dashboard.research}
        actions={dashboard.researchActions}
        sections={[researchSectionForTab(tab)]}
      />
    </div>
  );
}

function sectionForTab(tab: ExpertTabKey) {
  if (tab === "optimize") return "optimization";
  if (tab === "validate") return "validation";
  if (tab === "compare") return "compare";
  return "none";
}

function researchSectionForTab(tab: ExpertTabKey): BacktestResearchSection {
  if (tab === "optimize") return "optimization";
  if (tab === "validate") return "validation";
  if (tab === "compare") return "compare";
  return "capacity";
}

function PermissionPanel({ title, description }: { title: string; description: string }) {
  return (
    <section className="panel strategy-access-panel">
      <h2>{title}</h2>
      <p>{description}</p>
    </section>
  );
}

const EXPERT_META: Record<ExpertTabKey, [string, string]> = {
  optimize: ["专家工具：找更稳参数", "只建议研究员使用。它会自动搜索评分、仓位、止损和持有天数。"],
  validate: ["专家工具：防过拟合检查", "检查策略是不是只在历史里好看。样本外不通过，不要进生产。"],
  compare: ["策略对比", "把多个体检结果放在一起，直接选择更稳的策略。"],
  capacity: ["管理员工具：ML / 容量", "查看模拟盘平仓样本是否进入训练池，并评估策略在不同资金规模下是否还能承载。"],
};
