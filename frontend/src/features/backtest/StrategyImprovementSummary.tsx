import { useEffect } from "react";
import { Alert, Col, Row, Space, Tag, Typography } from "antd";
import { backtestsApi, type StrategyImprovementReportResponse } from "../../api/backtests";
import { useBacktestResearchUiStore } from "../../stores/backtestResearchUiStore";
import { useServerState } from "../../state/serverState";
import { STRATEGY_IMPROVEMENT_REPORT_KEY } from "./StrategyImprovementGatePanel";
import { Metric } from "./BacktestDashboard.components";
import { formatInteger, formatNumber } from "./backtestDisplay";
import { BACKTEST_METRIC_GRID_STYLE } from "./backtestStyles";
import { BACKTEST_SECTION_META_STYLE } from "./backtestPageLayoutStyles";

export function StrategyGovernanceSummaryPanel() {
  const report = useStrategyImprovementReport();
  const error = useBacktestResearchUiStore((state) => state.strategyImprovementError);
  if (error && !report) return <Alert type="warning" showIcon title="策略治理报告暂不可用" description={error} />;
  if (!report) return <Typography.Text type="secondary">正在读取策略治理报告。</Typography.Text>;
  return <StrategyGovernanceSummaryContent report={report} />;
}

export function PaperExitModelShadowSummaryPanel() {
  const report = useStrategyImprovementReport();
  const error = useBacktestResearchUiStore((state) => state.strategyImprovementError);
  if (error && !report) return <Alert type="warning" showIcon title="模型影子验证报告暂不可用" description={error} />;
  if (!report) return <Typography.Text type="secondary">正在读取模型影子验证报告。</Typography.Text>;
  return <PaperExitModelShadowSummaryContent report={report} />;
}

export function StrategyGovernanceSummaryContent({ report }: { report: StrategyImprovementReportResponse }) {
  const counts = report.strategy_governance.state_counts ?? {};
  const items = report.strategy_governance.items ?? report.strategy_governance.ranking ?? [];
  const weak = items.filter((item) => item.governance_state === "weak_strategy").slice(0, 3);
  const candidates = items.filter((item) => item.governance_state === "positive_expectancy_candidate").slice(0, 3);
  const highDrawdown = items.filter((item) => item.governance_state === "high_return_high_drawdown").slice(0, 3);
  const etfGate = report.gates.find((gate) => gate.key === "etf_t0_minute_coverage");
  return (
    <Space orientation="vertical" size={10} style={{ width: "100%" }}>
      <div style={BACKTEST_METRIC_GRID_STYLE}>
        <Metric label="生产候选" value={formatInteger(counts.positive_expectancy_candidate ?? 0)} />
        <Metric label="高收益高回撤" value={formatInteger(counts.high_return_high_drawdown ?? 0)} />
        <Metric label="暂停/降权" value={formatInteger(counts.weak_strategy ?? 0)} />
        <Metric label="滚动窗口" value={formatInteger(report.walk_forward?.window_count ?? 0)} />
      </div>
      <Alert
        type={report.summary.production_parameter_change_allowed ? "success" : "warning"}
        showIcon
        title={report.summary.production_parameter_change_allowed ? "允许参数晋级" : "参数晋级保持阻断"}
        description={etfGate?.message || report.summary.reason || "样本外验证和门禁未全部通过前，不写生产参数。"}
      />
      <Row gutter={[8, 8]}>
        <Col xs={24} lg={8}><StrategyList title="生产候选" tone="green" items={candidates} emptyText="暂无可晋级候选" /></Col>
        <Col xs={24} lg={8}><StrategyList title="高收益高回撤" tone="gold" items={highDrawdown} emptyText="暂无高回撤策略" /></Col>
        <Col xs={24} lg={8}><StrategyList title="暂停/降权" tone="red" items={weak} emptyText="暂无弱策略" /></Col>
      </Row>
      <Typography.Text style={BACKTEST_SECTION_META_STYLE}>
        滚动验证：{report.walk_forward?.status ?? "--"}，随机切分{report.walk_forward?.random_split_allowed ? "允许" : "禁止"}；约束审计 {report.constraint_policy?.status ?? "--"}，防未来函数 {report.temporal_guard?.status ?? "--"}。
      </Typography.Text>
    </Space>
  );
}

export function PaperExitModelShadowSummaryContent({ report }: { report: StrategyImprovementReportResponse }) {
  const shadow = report.auxiliary_model_shadow;
  const diff = shadow?.action_diff;
  const outcome = shadow?.outcome_summary;
  const blockers = shadow?.promotion_blockers?.join(", ") || "--";
  return (
    <Space orientation="vertical" size={8} style={{ width: "100%" }}>
      <div style={BACKTEST_METRIC_GRID_STYLE}>
        <Metric label="影子样本" value={`${formatInteger(shadow?.record_count ?? 0)} / ${formatInteger(shadow?.settled_count ?? 0)}`} />
        <Metric label="更激进动作" value={formatInteger(diff?.more_aggressive_than_rule ?? 0)} />
        <Metric label="Fallback" value={formatInteger(diff?.fallback ?? 0)} />
        <Metric label="卖飞率" value={`${formatNumber(outcome?.sell_flying_rate_pct ?? 0)}%`} />
      </div>
      <Alert
        type={shadow?.promotion_ready ? "success" : "info"}
        showIcon
        title={shadow?.promotion_ready ? "模型可进入下一阶段评审" : "模型仍为仅影子验证"}
        description={`硬止损覆盖：${shadow?.hard_stop_override_allowed ? "允许" : "禁止"}；阻断：${blockers}`}
      />
      <Typography.Text style={BACKTEST_SECTION_META_STYLE}>
        模型只比较规则动作与建议动作，不下单、不改账本、不取消硬止损；5日均收益 {formatNumber(outcome?.avg_return_5d_pct ?? 0)}%，最大不利 {formatNumber(outcome?.avg_max_adverse_5d_pct ?? 0)}%。
      </Typography.Text>
    </Space>
  );
}

function useStrategyImprovementReport() {
  const [report, setReport] = useServerState<StrategyImprovementReportResponse | null>(STRATEGY_IMPROVEMENT_REPORT_KEY, null);
  const loading = useBacktestResearchUiStore((state) => state.strategyImprovementLoading);
  const setStrategyImprovement = useBacktestResearchUiStore((state) => state.setStrategyImprovement);
  useEffect(() => {
    if (report || loading) return;
    setStrategyImprovement({ strategyImprovementLoading: true, strategyImprovementError: "" });
    backtestsApi.getStrategyImprovementReport()
      .then(setReport)
      .catch((err) => setStrategyImprovement({ strategyImprovementError: err instanceof Error ? err.message : "策略闭环报告加载失败" }))
      .finally(() => setStrategyImprovement({ strategyImprovementLoading: false }));
  }, [loading, report, setStrategyImprovement]);
  return report;
}

function StrategyList({
  title,
  tone,
  items,
  emptyText,
}: {
  title: string;
  tone: string;
  items: Array<{ strategy_key: string; strategy_title?: string; profit_factor?: number | null; win_rate_pct?: number; recommended_action?: string }>;
  emptyText: string;
}) {
  return (
    <Space orientation="vertical" size={4} style={{ width: "100%" }}>
      <Typography.Text strong>{title}</Typography.Text>
      {items.length ? items.map((item) => (
        <Space key={item.strategy_key} orientation="vertical" size={0} style={{ width: "100%" }}>
          <Typography.Text>{item.strategy_title || item.strategy_key}</Typography.Text>
          <Space size={4} wrap>
            <Tag color={tone}>PF {formatNumber(item.profit_factor ?? null)}</Tag>
            <Tag color={tone}>胜率 {formatNumber(item.win_rate_pct ?? null)}%</Tag>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>{actionText(item.recommended_action)}</Typography.Text>
          </Space>
        </Space>
      )) : <Typography.Text type="secondary">{emptyText}</Typography.Text>}
    </Space>
  );
}

function actionText(value?: string): string {
  if (value === "pause_or_downgrade_production_weight") return "暂停或降权";
  if (value === "add_market_state_position_exit_constraints") return "加市场/仓位/退出约束";
  if (value === "optimize_with_constraints") return "约束内优化";
  if (value === "observe_or_collect_more_samples") return "继续观察扩样本";
  return value || "保持观察";
}
