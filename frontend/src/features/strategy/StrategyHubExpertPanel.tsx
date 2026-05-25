import type { AuthUser } from "../../types";
import { Card, Col, Row, Space, Typography } from "antd";
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
    <Row gutter={[12, 12]}>
      <Col xs={24} xl={7}>
        <Card size="small">
          <Space direction="vertical" size={4}>
            <Typography.Title level={4} style={{ margin: 0 }}>{meta[0]}</Typography.Title>
            <Typography.Text type="secondary">{meta[1]}</Typography.Text>
          </Space>
        </Card>
      </Col>
      <Col xs={24} xl={17}>
        <BacktestResearchPanel
          state={dashboard.research}
          actions={dashboard.researchActions}
          sections={[researchSectionForTab(tab)]}
        />
      </Col>
    </Row>
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
    <Card size="small">
      <Space direction="vertical" size={4}>
        <Typography.Title level={4} style={{ margin: 0 }}>{title}</Typography.Title>
        <Typography.Text type="secondary">{description}</Typography.Text>
      </Space>
    </Card>
  );
}

const EXPERT_META: Record<ExpertTabKey, [string, string]> = {
  optimize: ["专家工具：找更稳参数", "只建议研究员使用。它会自动搜索评分、仓位、止损和持有天数。"],
  validate: ["专家工具：防过拟合检查", "检查策略是不是只在历史里好看。样本外不通过，不要进生产。"],
  compare: ["策略对比", "把多个体检结果放在一起，直接选择更稳的策略。"],
  capacity: ["管理员工具：ML / 容量", "查看模拟盘平仓样本是否进入训练池，并评估策略在不同资金规模下是否还能承载。"],
};
