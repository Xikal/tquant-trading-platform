import { Button, Tag } from "antd";
import type { ReviewWorkspaceItem, TradeJournalEntryCreate, TradeJournalEntryUpdate } from "../../types";
import { TqEmpty } from "../../ui/feedback/StateViews";
import { ReviewWorkspaceRelativeStrengthCard } from "./ReviewWorkspaceRelativeStrengthCard";
import { TradeJournalQuickEntry } from "./TradeJournalQuickEntry";

export function ReviewWorkspaceDetail({
  item,
  creatingJournal,
  updatingJournal,
  deletingJournal,
  onCreateJournal,
  onUpdateJournal,
  onDeleteJournal,
}: {
  item?: ReviewWorkspaceItem;
  creatingJournal: boolean;
  updatingJournal?: boolean;
  deletingJournal?: boolean;
  onCreateJournal: (payload: TradeJournalEntryCreate) => void;
  onUpdateJournal?: (entryId: number, payload: TradeJournalEntryUpdate) => void;
  onDeleteJournal?: (entryId: number) => void;
}) {
  if (!item) {
    return <TqEmpty title="选择一条复盘队列" description="先点左侧股票，再补充纪律记录和查看抗跌事实。" />;
  }
  const reason = [item.pool_item.drop_reason, ...(item.pool_item.evidence ?? [])].filter(Boolean).join("；");
  return (
    <div className="strategy-review-detail">
      <div className="strategy-tracking-tag-row">
        <strong>{item.pool_item.name || item.pool_item.symbol}</strong>
        <Tag>{item.pool_item.board_name}</Tag>
        <Tag>{item.pool_item.status === "dropped" ? "已剔除" : item.pool_item.status === "retained" ? "已留存" : "观察池"}</Tag>
      </div>
      <p>{reason || "暂无复盘证据。"}</p>
      <ReviewWorkspaceRelativeStrengthCard item={item} />
      <TradeJournalQuickEntry
        key={item.review_key}
        accountId={null}
        submitting={creatingJournal}
        initialSymbol={item.pool_item.symbol}
        initialReasonText={reason}
        initialSignalSource="review_workspace"
        onSubmit={onCreateJournal}
      />
      <div className="strategy-review-journal-list">
        {(item.journal_entries ?? []).length ? (
          (item.journal_entries ?? []).map((entry) => (
            <div className="strategy-review-journal-row" key={entry.entry_id}>
              <div>
                <span>{entry.reason_text || "未填写理由"}</span>
                <Tag>{entry.signal_source || "manual_review"}</Tag>
              </div>
              <div className="strategy-review-journal-actions">
                <Button
                  size="small"
                  loading={updatingJournal}
                  onClick={() => onUpdateJournal?.(entry.entry_id, { reason_text: `${entry.reason_text || ""}（已修正）`.trim() })}
                >
                  修正记录
                </Button>
                <Button size="small" danger loading={deletingJournal} onClick={() => onDeleteJournal?.(entry.entry_id)}>
                  删除记录
                </Button>
              </div>
            </div>
          ))
        ) : (
          <p className="strategy-review-journal-empty">暂无纪律日志</p>
        )}
      </div>
    </div>
  );
}
