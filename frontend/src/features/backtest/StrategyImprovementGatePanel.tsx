import { useEffect } from "react";
import { Alert, Button, Space, Tag, Typography } from "antd";
import { backtestsApi, type StrategyImprovementReportResponse } from "../../api/backtests";
import { DataTable } from "../../ui/table/DataTable";
import { useBacktestResearchUiStore } from "../../stores/backtestResearchUiStore";
import { useServerState } from "../../state/serverState";
import { Metric, PanelHeader } from "./BacktestDashboard.components";
import { formatInteger, formatNumber } from "./backtestDisplay";
import { BACKTEST_METRIC_GRID_STYLE } from "./backtestStyles";
import { BACKTEST_PANEL_SURFACE_STYLE, BACKTEST_SECTION_META_STYLE } from "./backtestPageLayoutStyles";

export const STRATEGY_IMPROVEMENT_REPORT_KEY = ["backtest", "research", "strategy-improvement-report"] as const;

export function StrategyImprovementGatePanel() {
  const [report, setReport] = useServerState<StrategyImprovementReportResponse | null>(STRATEGY_IMPROVEMENT_REPORT_KEY, null);
  const loading = useBacktestResearchUiStore((state) => state.strategyImprovementLoading);
  const error = useBacktestResearchUiStore((state) => state.strategyImprovementError);
  const setStrategyImprovement = useBacktestResearchUiStore((state) => state.setStrategyImprovement);

  const load = () => {
    setStrategyImprovement({ strategyImprovementLoading: true, strategyImprovementError: "" });
    backtestsApi.getStrategyImprovementReport()
      .then(setReport)
      .catch((err) => setStrategyImprovement({ strategyImprovementError: err instanceof Error ? err.message : "策略闭环报告加载失败" }))
      .finally(() => setStrategyImprovement({ strategyImprovementLoading: false }));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <section className="panel" style={BACKTEST_PANEL_SURFACE_STYLE}>
      <PanelHeader
        title="上线门禁"
        action={<Button size="small" onClick={load} loading={loading}>刷新</Button>}
      />
      {error ? <Alert type="warning" showIcon title="策略闭环报告暂不可用" description={error} /> : null}
      {report ? <StrategyImprovementGateContent report={report} /> : <Typography.Text type="secondary">正在读取策略闭环报告。</Typography.Text>}
    </section>
  );
}

export function StrategyImprovementGateContent({ report }: { report: StrategyImprovementReportResponse }) {
  const dailyGap = report.data_coverage.missing_detail_sample?.[0] as Record<string, unknown> | undefined;
  const missingEtfs = report.minute_coverage.missing_etf_symbols?.slice(0, 6).map((item) => {
    const pct = typeof item.trade_day_coverage_pct === "number" ? ` ${formatNumber(item.trade_day_coverage_pct)}%` : "";
    return `${item.symbol}${pct}`;
  }).join(", ") || "--";
  const minuteCoverage = report.minute_coverage.eligible_etf_minute_coverage_pct ?? 0;
  const anyMinuteCoverage = report.minute_coverage.eligible_etf_any_minute_coverage_pct ?? 0;
  const metadata = report.data_quality?.metadata_coverage;
  const metadataGaps = metadata?.blocking_gaps?.slice(0, 4).join(", ") || "--";
  const diagnostics = report.minute_coverage.provider_diagnostics;
  const providerFailures = diagnostics?.provider_errors_sample
    ?.slice(0, 3)
    .map((item) => `${item.symbol ?? "--"} ${item.source ?? "--"}: ${item.message ?? "--"}`)
    .join("; ");
  return (
    <Space orientation="vertical" size={12} style={{ width: "100%" }}>
      <Alert
        type={report.summary.formal_backtest_allowed ? "success" : "warning"}
        showIcon
        title={report.summary.formal_backtest_allowed ? "允许正式回测" : "正式回测已阻断"}
        description={report.summary.reason || "数据、Walk-forward 和模型 Shadow 需要继续验证。"}
      />
      <div style={BACKTEST_METRIC_GRID_STYLE}>
        <Metric label="全市场覆盖" value={`${formatNumber(report.data_coverage.full_market_trade_day_coverage_pct ?? report.data_coverage.coverage_pct)}%`} />
        <Metric label="完整交易日" value={`${formatInteger(report.data_coverage.complete_trade_day_count ?? 0)} / ${formatInteger(report.data_coverage.trade_day_count ?? 0)}`} />
        <Metric label="ETF 验收分钟线" value={`${formatNumber(minuteCoverage)}%`} />
        <Metric label="候选策略" value={formatInteger(report.walk_forward?.candidate_strategy_count ?? 0)} />
        <Metric label="WF窗口" value={formatInteger(report.walk_forward?.window_count ?? 0)} />
        <Metric label="Shadow样本" value={`${formatInteger(report.auxiliary_model_shadow?.record_count ?? 0)} / ${formatInteger(report.auxiliary_model_shadow?.settled_count ?? 0)}`} />
      </div>
      <Typography.Text style={BACKTEST_SECTION_META_STYLE}>
        日线缺口：{String(dailyGap?.trade_date ?? "--")}，当前 {String(dailyGap?.symbol_count ?? 0)} / {String(dailyGap?.threshold ?? 0)}；ETF 分钟线状态 {report.minute_coverage.status} / {report.minute_coverage.raw_data_status ?? "--"}，阻断 {report.minute_coverage.blocked_reason ?? "--"}；ETF 任意分钟线 {formatNumber(anyMinuteCoverage)}%，验收交易日 {formatInteger(report.minute_coverage.expected_trade_day_count ?? 0)}，缺口：{missingEtfs}
      </Typography.Text>
      <Typography.Text style={BACKTEST_SECTION_META_STYLE}>
        交易元数据：{metadata?.status ?? "--"}，阻断 {formatInteger(metadata?.blocking_gap_count ?? 0)}，缺口：{metadataGaps}
      </Typography.Text>
      {diagnostics?.status && diagnostics.status !== "not_found" ? (
        <Typography.Text style={BACKTEST_SECTION_META_STYLE}>
          ETF补数诊断：{diagnostics.report_path ?? "--"}，状态 {diagnostics.status}，写入 {diagnostics.write_effect ?? "--"}，造数策略 {diagnostics.fake_data_policy ?? "--"}；Provider失败：{providerFailures || "--"}
        </Typography.Text>
      ) : null}
      <AuditSummary report={report} />
      <DataTable
        rowKey="key"
        size="small"
        pagination={false}
        dataSource={report.gates}
        columns={[
          { title: "门禁", dataIndex: "key" },
          { title: "状态", dataIndex: "status", render: (value) => <Tag color={value === "pass" ? "green" : value === "warn" ? "gold" : "red"}>{String(value)}</Tag> },
          { title: "说明", dataIndex: "message" },
        ]}
      />
    </Space>
  );
}

function AuditSummary({ report }: { report: StrategyImprovementReportResponse }) {
  const firstWindow = report.walk_forward?.windows?.[0];
  const gridSummary = report.walk_forward?.controlled_parameter_grid
    ?.map((item) => `${item.name}:${item.values.length}`)
    .slice(0, 5)
    .join(", ") || "--";
  const shadow = report.auxiliary_model_shadow;
  const diff = shadow?.action_diff;
  const outcome = shadow?.outcome_summary;
  const stability = report.walk_forward?.stability_checks?.map((item) => item.key).join(", ") || "--";
  const shadowBlockers = shadow?.promotion_blockers?.slice(0, 4).join(", ") || "--";
  return (
    <Space orientation="vertical" size={4} style={{ width: "100%" }}>
      <Typography.Text style={BACKTEST_SECTION_META_STYLE}>
        Walk-forward：{formatInteger(report.walk_forward?.window_count ?? 0)} 个窗口，随机切分{report.walk_forward?.random_split_allowed ? "允许" : "禁止"}，参数网格：{gridSummary}，过拟合检查：{stability}
      </Typography.Text>
      <Typography.Text style={BACKTEST_SECTION_META_STYLE}>
        首个窗口：训练 {firstWindow?.train_start ?? "--"} 至 {firstWindow?.train_end ?? "--"}，验证 {firstWindow?.validation_start ?? "--"} 至 {firstWindow?.validation_end ?? "--"}，OOS {firstWindow?.oos_start ?? "--"} 至 {firstWindow?.oos_end ?? "--"}。
      </Typography.Text>
      <Typography.Text style={BACKTEST_SECTION_META_STYLE}>
        约束审计：{report.constraint_policy?.status ?? "--"}，问题 {formatInteger(report.constraint_policy?.issue_count ?? 0)}，防未来函数：{report.temporal_guard?.status ?? "--"}。
      </Typography.Text>
      <Typography.Text style={BACKTEST_SECTION_META_STYLE}>
        模型Shadow：{shadow?.status ?? "--"}，Shadow-only {shadow?.shadow_only ? "是" : "否"}，可晋级 {shadow?.promotion_ready ? "是" : "否"}；动作差异 一致 {formatInteger(diff?.same_as_rule ?? 0)} / 更激进 {formatInteger(diff?.more_aggressive_than_rule ?? 0)} / 更保守 {formatInteger(diff?.less_aggressive_than_rule ?? 0)} / fallback {formatInteger(diff?.fallback ?? 0)}；5日均收益 {formatNumber(outcome?.avg_return_5d_pct ?? 0)}%，卖飞率 {formatNumber(outcome?.sell_flying_rate_pct ?? 0)}%；阻断：{shadowBlockers}
      </Typography.Text>
    </Space>
  );
}
