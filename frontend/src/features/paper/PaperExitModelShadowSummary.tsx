import { useEffect } from "react";
import { Alert, Space, Typography } from "antd";
import { backtestsApi, type StrategyImprovementReportResponse } from "../../api/backtests";
import { useServerState } from "../../state/serverState";
import { usePaperUiStore } from "../../stores/paperUiStore";
import { formatInteger, formatNumber } from "../workspace-shared/workspaceFormatters";

const PAPER_EXIT_MODEL_SHADOW_REPORT_KEY = ["paper", "exit-model-shadow-report"] as const;
const PANEL_STACK_STYLE = { width: "100%" } as const;
const METRIC_GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
  gap: 8,
} as const;
const METRIC_STYLE = {
  display: "grid",
  gap: 2,
  padding: "8px 10px",
  border: "1px solid rgba(148, 163, 184, 0.24)",
  borderRadius: 8,
  background: "#f8fafc",
} as const;
const METRIC_LABEL_STYLE = { fontSize: 12, color: "#64748b" } as const;
const METRIC_VALUE_STYLE = { fontSize: 14, color: "#0f172a" } as const;
const NOTE_STYLE = { fontSize: 12 } as const;

export function PaperExitModelShadowSummaryPanel() {
  const [report, setReport] = useServerState<StrategyImprovementReportResponse | null>(PAPER_EXIT_MODEL_SHADOW_REPORT_KEY, null);
  const loading = usePaperUiStore((state) => state.exitModelShadowLoading);
  const error = usePaperUiStore((state) => state.exitModelShadowError);
  const setLoading = usePaperUiStore((state) => state.setExitModelShadowLoading);
  const setError = usePaperUiStore((state) => state.setExitModelShadowError);

  useEffect(() => {
    if (report || loading) return;
    setLoading(true);
    setError("");
    backtestsApi.getStrategyImprovementReport()
      .then(setReport)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "模型影子验证报告加载失败"))
      .finally(() => setLoading(false));
  }, [loading, report, setReport]);

  if (error && !report) return <Alert type="warning" showIcon message="模型影子验证报告暂不可用" description={error} />;
  if (!report) return <Typography.Text type="secondary">正在读取模型影子验证报告。</Typography.Text>;
  return <PaperExitModelShadowSummaryContent report={report} />;
}

export function PaperExitModelShadowSummaryContent({ report }: { report: StrategyImprovementReportResponse }) {
  const shadow = report.auxiliary_model_shadow;
  const diff = shadow?.action_diff;
  const outcome = shadow?.outcome_summary;
  const blockers = shadow?.promotion_blockers?.join(", ") || "--";
  return (
    <Space direction="vertical" size={8} style={PANEL_STACK_STYLE}>
      <div style={METRIC_GRID_STYLE}>
        <PaperExitModelMetric label="影子样本" value={`${formatInteger(shadow?.record_count ?? 0)} / ${formatInteger(shadow?.settled_count ?? 0)}`} />
        <PaperExitModelMetric label="更激进动作" value={formatInteger(diff?.more_aggressive_than_rule ?? 0)} />
        <PaperExitModelMetric label="备用动作" value={formatInteger(diff?.fallback ?? 0)} />
        <PaperExitModelMetric label="卖飞率" value={`${formatNumber(outcome?.sell_flying_rate_pct ?? 0)}%`} />
      </div>
      <Alert
        type={shadow?.promotion_ready ? "success" : "info"}
        showIcon
        message={shadow?.promotion_ready ? "模型可进入下一阶段评审" : "模型仍为仅影子验证"}
        description={`硬止损覆盖：${shadow?.hard_stop_override_allowed ? "允许" : "禁止"}；阻断：${blockers}`}
      />
      <Typography.Text type="secondary" style={NOTE_STYLE}>
        模型只比较规则动作与建议动作，不下单、不改账本、不取消硬止损；5日均收益 {formatNumber(outcome?.avg_return_5d_pct ?? 0)}%，最大不利 {formatNumber(outcome?.avg_max_adverse_5d_pct ?? 0)}%。
      </Typography.Text>
    </Space>
  );
}

function PaperExitModelMetric({ label, value }: { label: string; value: string }) {
  return (
    <span style={METRIC_STYLE}>
      <Typography.Text type="secondary" style={METRIC_LABEL_STYLE}>{label}</Typography.Text>
      <Typography.Text strong style={METRIC_VALUE_STYLE}>{value}</Typography.Text>
    </span>
  );
}
