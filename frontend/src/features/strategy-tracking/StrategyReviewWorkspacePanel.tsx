import { Button } from "antd";
import { useMemo } from "react";
import { useStrategyTrackingStore } from "../../stores/strategyTrackingStore";
import type { ReviewWorkspaceResponse, TradeJournalEntryCreate, TradeJournalEntryUpdate } from "../../types";
import { TqEmpty } from "../../ui/feedback/StateViews";
import type { BoardFilter } from "./boardFilters";
import { nextBoardFilter } from "./boardFilters";
import { ReviewWorkspaceDetail } from "./ReviewWorkspaceDetail";
import { ReviewWorkspacePerfStatus } from "./ReviewWorkspacePerfStatus";
import { ReviewWorkspaceQueue } from "./ReviewWorkspaceQueue";
import { ReviewWorkspaceReminderStatus } from "./ReviewWorkspaceReminderStatus";
import { ReviewWorkspaceSummaryCards } from "./ReviewWorkspaceSummaryCards";

export function StrategyReviewWorkspacePanel({
  data,
  loading,
  boardFilter,
  onBoardFilterChange,
  onCreateJournal,
  onUpdateJournal,
  onDeleteJournal,
  creatingJournal,
  updatingJournal = false,
  deletingJournal = false,
  professional = false,
}: {
  data?: ReviewWorkspaceResponse;
  loading: boolean;
  boardFilter: BoardFilter;
  onBoardFilterChange: (boardFilter: BoardFilter) => void;
  onCreateJournal: (payload: TradeJournalEntryCreate) => void;
  onUpdateJournal?: (entryId: number, payload: TradeJournalEntryUpdate) => void;
  onDeleteJournal?: (entryId: number) => void;
  creatingJournal: boolean;
  updatingJournal?: boolean;
  deletingJournal?: boolean;
  professional?: boolean;
}) {
  const selectedKey = useStrategyTrackingStore((state) => state.reviewWorkspaceSelectedKey);
  const setSelectedKey = useStrategyTrackingStore((state) => state.setReviewWorkspaceSelectedKey);
  const items = data?.items ?? [];
  const selected = useMemo(() => items.find((item) => item.review_key === selectedKey) ?? items[0], [items, selectedKey]);

  if (data && !data.enabled) {
    return <TqEmpty title="复盘中心未开启" description="当前功能开关关闭，策略跟踪保持既有展示。" />;
  }

  return (
    <div className="strategy-tracking-analysis-stack">
      <div className="strategy-tracking-tab-toolbar">
        <div>
          <strong>复盘中心</strong>
          <span>复盘队列、纪律日志、抗跌事实串成一个闭环；仅用于观察和复盘。</span>
        </div>
        <Button
          size="small"
          type={boardFilter === "main_only" ? "primary" : "default"}
          onClick={() => onBoardFilterChange(nextBoardFilter(boardFilter))}
        >
          只看主板
        </Button>
      </div>
      <ReviewWorkspaceReminderStatus reminder={data?.reminder} />
      <ReviewWorkspacePerfStatus data={data} professional={professional} />
      {data?.summary ? <ReviewWorkspaceSummaryCards summary={data.summary} /> : null}
      {data?.data_quality && data.data_quality !== "ok" ? <p className="strategy-review-data-quality">复盘中心数据状态：{data.data_quality}</p> : null}
      <div className="strategy-review-workspace-grid">
        <ReviewWorkspaceQueue
          items={items}
          loading={loading}
          selectedKey={selected?.review_key ?? null}
          onSelect={(item) => setSelectedKey(item.review_key)}
        />
        <ReviewWorkspaceDetail
          item={selected}
          creatingJournal={creatingJournal}
          updatingJournal={updatingJournal}
          deletingJournal={deletingJournal}
          onCreateJournal={onCreateJournal}
          onUpdateJournal={onUpdateJournal}
          onDeleteJournal={onDeleteJournal}
        />
      </div>
    </div>
  );
}
