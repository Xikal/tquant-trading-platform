import { Collapse, Space, Tag, Typography } from "antd";
import type { StrategyPromotionReview } from "../../types";
import { TqEmpty } from "../../ui/feedback/StateViews";
import { DataTable } from "../../ui/table/DataTable";
import { InfoPill } from "../workspace-shared/WorkspaceComponents";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function PromotionReviewPanel({
  review,
  loading,
}: {
  review?: StrategyPromotionReview;
  loading: boolean;
}) {
  const evidence = review?.evidence ?? {};
  const rows = review ? [metricRow("样本数", evidence.sample_count), metricRow("PF", evidence.profit_factor), metricRow("平均单笔", evidence.average_trade_pct, "pct"), metricRow("最大回撤", evidence.max_drawdown_pct, "pct"), metricRow("max5", evidence.max5_return_pct, "pct"), metricRow("max10", evidence.max10_return_pct, "pct"), metricRow("季度稳定性", Number(evidence.quarterly_stability ?? 0) * 100, "pct")] : [];
  return (
    <Collapse
      size="small"
      items={[{
        key: "promotion-review",
        label: `晋级审查 · ${review?.strategy_key ?? "n_pattern_long_wash"}`,
        children: (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            {review ? (
              <>
                <Space wrap size={[6, 6]}>
                  <InfoPill compact label="当前层级" value={review.current_tier} />
                  <InfoPill compact label="建议层级" value={review.recommended_tier} />
                  <InfoPill compact label="自动生效" value={review.can_apply_override ? "允许" : "禁止"} tone={review.can_apply_override ? "down" : "neutral"} />
                  <Tag color={review.recommendation.includes("promote") ? "green" : "default"}>{review.recommendation}</Tag>
                </Space>
                <DataTable<PromotionMetricRow>
                  rowKey={(item) => item.key}
                  loading={loading}
                  dataSource={rows}
                  defaultScrollY={220}
                  columns={[
                    { title: "指标", dataIndex: "label", width: 120 },
                    { title: "数值", dataIndex: "value", width: 120, render: (_value, item) => item.kind === "pct" ? formatPct(Number(item.value || 0)) : String(item.value ?? "--") },
                  ]}
                  scroll={{ x: 360 }}
                />
                {review.blocking_reasons.length ? (
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>阻断：{review.blocking_reasons.join(" / ")}</Typography.Text>
                ) : (
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>仅生成晋级建议，层级变更仍需人工修改策略分层常量并通过守卫测试。</Typography.Text>
                )}
              </>
            ) : (
              <TqEmpty title={loading ? "晋级审查加载中" : "暂无晋级审查"} description="晋级引擎只输出建议，不自动改变生产分层。" />
            )}
          </Space>
        ),
      }]}
    />
  );
}

interface PromotionMetricRow {
  key: string;
  label: string;
  value: unknown;
  kind?: "pct";
}

function metricRow(label: string, value: unknown, kind?: "pct"): PromotionMetricRow {
  return { key: label, label, value, kind };
}
