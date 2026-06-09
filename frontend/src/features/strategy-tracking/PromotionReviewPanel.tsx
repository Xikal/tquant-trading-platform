import { Collapse, Space, Tag, Typography } from "antd";
import type { StrategyPromotionReview } from "../../types";
import { TqEmpty } from "../../ui/feedback/StateViews";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { InfoPill } from "../workspace-shared/WorkspaceComponents";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function PromotionReviewPanel({
  review,
  loading,
  defaultOpen = false,
}: {
  review?: StrategyPromotionReview;
  loading: boolean;
  defaultOpen?: boolean;
}) {
  const evidence = review?.evidence ?? {};
  const rows = review ? [metricRow("样本数", evidence.sample_count), metricRow("利润因子", evidence.profit_factor), metricRow("平均单笔", evidence.average_trade_pct, "pct"), metricRow("最大回撤", evidence.max_drawdown_pct, "pct"), metricRow("max5", evidence.max5_return_pct, "pct"), metricRow("max10", evidence.max10_return_pct, "pct"), metricRow("季度稳定性", Number(evidence.quarterly_stability ?? 0) * 100, "pct")] : [];
  return (
    <Collapse
      size="small"
      defaultActiveKey={defaultOpen ? ["promotion-review"] : []}
      items={[{
        key: "promotion-review",
        label: `晋级审查 · ${review?.strategy_key ?? "n_pattern_long_wash"}`,
        children: (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            {review ? (
              <>
                <Space wrap size={[6, 6]}>
                  <InfoPill compact label="当前层级" value={promotionTierText(review.current_tier)} />
                  <InfoPill compact label="建议层级" value={promotionTierText(review.recommended_tier)} />
                  <InfoPill compact label="自动生效" value={review.can_apply_override ? "允许" : "禁止"} tone={review.can_apply_override ? "down" : "neutral"} />
                  <Tag color={review.recommendation.includes("promote") ? "green" : "default"}>{promotionRecommendationText(review.recommendation)}</Tag>
                </Space>
                <VirtualGrid<PromotionMetricRow>
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
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>阻断：{review.blocking_reasons.map(promotionReasonText).join(" / ")}</Typography.Text>
                ) : (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>仅生成晋级建议，层级变更仍需人工修改策略分层常量并通过守卫测试。</Typography.Text>
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

function promotionTierText(value: string): string {
  const normalized = value.trim();
  if (normalized === "research" || normalized === "research_only") return "研究层";
  if (normalized === "paper_small") return "小仓观察";
  if (normalized === "candidate_production") return "可进入生产候选";
  if (normalized === "production") return "生产层";
  return normalized || "--";
}

function promotionRecommendationText(value: string): string {
  const normalized = value.trim();
  if (normalized === "stay_research") return "继续研究验证";
  if (normalized === "promote_to_paper_small") return "晋级小仓观察候选";
  if (normalized === "promote_to_candidate_production") return "晋级生产候选";
  if (normalized === "keep_current") return "维持当前层级";
  return normalized || "--";
}

function promotionReasonText(value: string): string {
  const normalized = value.trim();
  if (normalized === "needs_validation") return "仍需验证";
  if (normalized === "sample_too_small") return "样本不足";
  if (normalized === "drawdown_too_high") return "回撤偏高";
  if (normalized === "profit_factor_low") return "利润因子不足";
  return normalized || "--";
}
