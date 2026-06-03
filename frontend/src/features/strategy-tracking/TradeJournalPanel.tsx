import { Alert, Tag, Typography } from "antd";
import { TqEmpty } from "../../ui/feedback/StateViews";
import type { TradeJournalResponse } from "../../types";
import { VirtualCardList } from "../../ui/list/VirtualCardList";
import { useCreateTradeJournal } from "./queries";
import { TradeJournalQuickEntry } from "./TradeJournalQuickEntry";

export function TradeJournalPanel({ accountId, data, loading }: { accountId?: number | null; data?: TradeJournalResponse; loading: boolean }) {
  if (data && !data.enabled) {
    return <TqEmpty title="纪律日志未开启" description="当前功能开关关闭，页面不新增记录入口。" />;
  }
  const createJournal = useCreateTradeJournal(accountId ?? null);
  const items = data?.items ?? [];
  return (
    <div className="strategy-tracking-analysis-stack">
      <TradeJournalQuickEntry
        accountId={accountId}
        submitting={createJournal.isPending}
        errorText={createJournal.error instanceof Error ? createJournal.error.message : ""}
        onSubmit={(payload) => createJournal.mutate(payload)}
      />
      {loading ? <Alert type="info" showIcon message="纪律日志加载中" /> : null}
      <VirtualCardList
        items={items}
        empty={!loading ? <TqEmpty title="暂无纪律记录" description="记录只用于复盘，不改变任何排序。" /> : null}
        estimateSize={96}
        maxHeight={420}
        getItemKey={(item) => item.entry_id}
        renderItem={(item) => (
          <article className="trade-journal-card">
            <div className="strategy-tracking-tag-row">
              <strong>{item.symbol}</strong>
              <Tag>{actionText(item.action || "note")}</Tag>
              <Tag>{item.data_quality}</Tag>
            </div>
            <Typography.Text>{item.reason_text || "未填写理由"}</Typography.Text>
            <Typography.Text type="secondary">
              {Object.entries(item.discipline_flags ?? {}).filter(([, value]) => value).map(([key]) => key).join(" / ") || "未勾选纪律项"}
            </Typography.Text>
          </article>
        )}
      />
    </div>
  );
}

function actionText(action: string) {
  if (action === "trim") return "减量记录";
  if (action === "add") return "仓位变化记录";
  if (action === "t_trade") return "T 记录";
  if (action === "sell") return "退出记录";
  if (action === "buy") return "建仓记录";
  return "备注";
}
