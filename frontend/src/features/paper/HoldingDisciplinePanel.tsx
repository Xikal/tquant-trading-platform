import { Alert, Tag, Typography } from "antd";
import { TqEmpty } from "../../ui/feedback/StateViews";
import type { HoldingDisciplineResponse } from "../../types";
import { VirtualCardList } from "../../ui/list/VirtualCardList";

export function HoldingDisciplinePanel({ data, loading }: { data?: HoldingDisciplineResponse; loading: boolean }) {
  if (data && !data.enabled) {
    return <TqEmpty title="持仓纪律未开启" description="功能开关关闭，模拟盘保持既有行为。" />;
  }
  const items = data?.items ?? [];
  return (
    <div className="strategy-tracking-analysis-stack">
      {loading ? <Alert type="info" showIcon message="持仓纪律加载中" /> : null}
      <VirtualCardList
        items={items}
        empty={!loading ? <TqEmpty title="暂无持仓纪律状态" description="有持仓和关键位数据后展示纪律事实。" /> : null}
        estimateSize={96}
        maxHeight={380}
        getItemKey={(item, index) => `${item.account_id}-${item.symbol}-${item.hint_code}-${index}`}
        renderItem={(item) => (
          <article className="trade-journal-card">
            <div className="strategy-tracking-tag-row">
              <strong>{item.symbol}</strong>
              <Tag color={item.level === "warn" ? "orange" : "blue"}>{hintText(item.hint_code)}</Tag>
              <Tag>{item.data_quality}</Tag>
            </div>
            <Typography.Text type="secondary">{item.evidence.join("；") || "暂无证据"}</Typography.Text>
          </article>
        )}
      />
    </div>
  );
}

function hintText(code: string) {
  const labels: Record<string, string> = {
    trailing_stop: "移动防守",
    no_add_down_warning: "下行纪律",
    break_down: "破位事实",
    emotional_pullback: "回撤观察",
    watch_cadence: "观察节奏",
  };
  return labels[code] || code;
}
