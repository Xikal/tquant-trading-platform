import { Tag } from "antd";
import type { ReviewWorkspaceResponse } from "../../types";

export function ReviewWorkspaceSummaryCards({ summary }: { summary: ReviewWorkspaceResponse["summary"] }) {
  if (!summary) return null;
  const cards = [
    { key: "pending", label: "待复盘", value: summary.pending_review_count, tone: "warn" },
    { key: "retained", label: "已留存", value: summary.retained_count, tone: "up" },
    { key: "dropped", label: "已剔除", value: summary.dropped_count, tone: "down" },
    { key: "missing", label: "缺日志", value: summary.missing_journal_count, tone: "warn" },
    { key: "completion", label: "完成率", value: `${summary.completion_rate_pct.toFixed(0)}%`, tone: "neutral" },
    {
      key: "discipline",
      label: "7日纪律",
      value: summary.seven_day_discipline_pass_rate_pct == null ? "--" : `${summary.seven_day_discipline_pass_rate_pct.toFixed(0)}%`,
      tone: "neutral",
    },
  ];
  return (
    <div className="strategy-review-summary-cards">
      {cards.map((card) => (
        <section className={`strategy-review-summary-card tone-${card.tone}`} key={card.key}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
        </section>
      ))}
      <Tag>{marketContextText(summary.market_context)}</Tag>
    </div>
  );
}

function marketContextText(value: string) {
  if (value === "market_down_day") return "大跌日背景";
  if (value === "normal_day") return "非大跌日";
  return "市场背景不足";
}
