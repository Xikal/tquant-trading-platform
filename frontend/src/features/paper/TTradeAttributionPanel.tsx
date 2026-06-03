import { Alert, Tag, Typography } from "antd";
import { PercentCell } from "../../ui/table/DataTable";
import { TqEmpty } from "../../ui/feedback/StateViews";
import type { TTradeAttributionResponse } from "../../types";
import { VirtualCardList } from "../../ui/list/VirtualCardList";

export function TTradeAttributionPanel({ data, loading }: { data?: TTradeAttributionResponse; loading: boolean }) {
  if (data && !data.enabled) {
    return <TqEmpty title="T 归因未开启" description="功能开关关闭，模拟盘保持既有行为。" />;
  }
  const items = data?.items ?? [];
  return (
    <div className="strategy-tracking-analysis-stack">
      {loading ? <Alert type="info" showIcon message="T 归因加载中" /> : null}
      <VirtualCardList
        items={items}
        empty={!loading ? <TqEmpty title="暂无 T 归因样本" description="有模拟成交和分钟覆盖后展示成本变化。" /> : null}
        estimateSize={112}
        maxHeight={380}
        getItemKey={(item) => `${item.account_id}-${item.symbol}-${item.period}`}
        renderItem={(item) => (
          <article className="trade-journal-card">
            <div className="strategy-tracking-tag-row">
              <strong>{item.symbol}</strong>
              <Tag>{item.data_quality}</Tag>
              <Tag>覆盖 {Math.round(item.minute_data_coverage * 100)}%</Tag>
              <Tag>{keyLevelText(item.key_level_state)}</Tag>
            </div>
            <Typography.Text>次数 {item.t_trade_count} · 成本变化 </Typography.Text>
            <PercentCell value={item.realized_cost_delta} />
            <Typography.Text type="secondary">
              {" "}· 对照差值 {item.vs_no_t_trade_return_delta === null ? item.data_quality : `${item.vs_no_t_trade_return_delta.toFixed(2)}%`}
            </Typography.Text>
            <Typography.Text type="secondary">
              {item.comparison_method} · {(item.completeness_issues ?? []).join(" / ") || (item.discipline_notes ?? []).slice(0, 2).join("；") || "仅用于归因"}
            </Typography.Text>
          </article>
        )}
      />
    </div>
  );
}

function keyLevelText(value?: string) {
  if (value === "support_broken") return "关键位破位";
  if (value === "near_support") return "靠近支撑";
  if (value === "near_resistance") return "靠近压力";
  if (value === "neutral") return "关键位中性";
  return "关键位不足";
}
