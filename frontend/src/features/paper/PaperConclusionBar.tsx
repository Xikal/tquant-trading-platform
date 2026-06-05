import type { ReactNode } from "react";
import { Button, Space } from "antd";
import type { PaperAccount, PaperAutoTradingStatus } from "../../types";
import { ConclusionBar } from "../../ui/surfaces";
import { formatMoneyPlain, formatPct, toneFromChange } from "../workspace-shared/workspaceFormatters";
import { autoTradingSkipNotice } from "./paperTradingStatus";

export function PaperConclusionBar({
  account,
  autoTradingStatus,
  loading,
  canResumeOrder,
  reviewReportCount = 0,
  pixel,
  positions,
  onTogglePause,
  onOpenReviewHistory,
}: {
  account: PaperAccount | null;
  autoTradingStatus: PaperAutoTradingStatus | null;
  loading: boolean;
  canResumeOrder?: boolean;
  reviewReportCount?: number;
  pixel?: ReactNode;
  positions?: ReactNode;
  onTogglePause?: () => void | Promise<void>;
  onOpenReviewHistory?: () => void;
}) {
  const skipNotice = autoTradingSkipNotice(autoTradingStatus);
  const hasReviewHistoryAction = Boolean(onOpenReviewHistory);
  const hasResumeAction = Boolean(canResumeOrder && onTogglePause);
  const actions = hasReviewHistoryAction || hasResumeAction ? (
    <Space size={6} wrap>
      {hasReviewHistoryAction ? (
        <Button size="small" disabled={loading} onClick={onOpenReviewHistory}>
          {reviewReportCount > 0 ? `复盘历史 · ${reviewReportCount} 条` : "复盘历史"}
        </Button>
      ) : null}
      {hasResumeAction ? (
        <Button size="small" disabled={loading} onClick={() => void onTogglePause?.()}>
          恢复委托
        </Button>
      ) : null}
    </Space>
  ) : null;

  return (
    <section className={`paper-conclusion${pixel ? " paper-conclusion--with-pixel" : ""}`}>
      <div className="paper-conclusion__metrics">
        <ConclusionBar
          title={null}
          summary={skipNotice ? `${skipNotice.title}：${skipNotice.text}` : null}
          actions={actions}
          items={[
            {
              key: "total-assets",
              label: "总资产",
              value: formatMoneyPlain(account?.total_assets),
              tone: "neutral",
            },
            {
              key: "unrealized-pnl",
              label: "浮动盈亏",
              value: formatSignedMoney(account?.unrealized_pnl),
              tone: toneFromChange(account?.unrealized_pnl),
            },
            {
              key: "today-pnl",
              label: "当日盈亏",
              value: formatSignedMoney(account?.today_pnl),
              tone: toneFromChange(account?.today_pnl),
            },
            {
              key: "market-value",
              label: "总市值",
              value: formatMoneyPlain(account?.market_value),
              tone: "neutral",
            },
          ]}
        />
      </div>
      {pixel ? (
        <div className="paper-conclusion__pixel-panel" aria-label="模拟盘角色动画">
          {pixel}
        </div>
      ) : null}
      {positions ? <div className="paper-conclusion__positions">{positions}</div> : null}
    </section>
  );
}

function formatSignedMoney(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${formatMoneyPlain(Math.abs(value))}`;
}
