import { Tag } from "antd";
import { PercentCell } from "../../ui/table/DataTable";
import type { ReviewWorkspaceItem } from "../../types";

export function ReviewWorkspaceRelativeStrengthCard({ item }: { item: ReviewWorkspaceItem }) {
  const rs = item.relative_strength;
  if (!rs) {
    return (
      <section className="strategy-review-relative-card status-insufficient">
        <strong>抗跌事实不足</strong>
        <p>当前没有匹配到相对强度数据。</p>
      </section>
    );
  }
  const fallback = rs.index_code === "market_average_fallback" || rs.data_quality !== "ok";
  return (
    <section className="strategy-review-relative-card">
      <div className="strategy-tracking-tag-row">
        <strong>抗跌事实</strong>
        <Tag>{flagText(rs.resilience_flag)}</Tag>
        <Tag>{rs.index_code}</Tag>
        <Tag>{rs.sector_code}</Tag>
      </div>
      <div className="strategy-review-relative-grid">
        <span>个股 <PercentCell value={rs.stock_pct} /></span>
        <span>市场 <PercentCell value={rs.index_pct} /></span>
        <span>板块 <PercentCell value={rs.sector_pct} /></span>
        <span>相对市场 <PercentCell value={rs.rs_vs_index} /></span>
        <span>相对板块 <PercentCell value={rs.rs_vs_sector} /></span>
      </div>
      <p>
        抗跌事实：相对市场 {formatPct(rs.rs_vs_index)}，相对板块 {formatPct(rs.rs_vs_sector)}。
        仅用于观察和复盘，不预测后续涨跌。
      </p>
      {fallback ? <p>市场指数不足，当前只展示全市场均值对照。</p> : null}
    </section>
  );
}

function flagText(value: string) {
  if (value === "resilient") return "抗跌";
  if (value === "follow_down") return "跟随下行";
  return "中性";
}

function formatPct(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}
