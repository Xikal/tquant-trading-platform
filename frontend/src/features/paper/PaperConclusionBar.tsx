import type { ReactNode } from "react";
import { Button, Space } from "antd";
import type { PaperAccount, PaperAutoTradingStatus, PaperPerformance } from "../../types";
import { ConclusionBar } from "../../ui/surfaces";
import { formatPct, toneFromChange } from "../workspace-shared/workspaceFormatters";
import { autoTradingSkipNotice, resolveAutoManagedStatus } from "./paperTradingStatus";

export function PaperConclusionBar({
  account,
  performance,
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
  performance: PaperPerformance | null;
  autoTradingStatus: PaperAutoTradingStatus | null;
  loading: boolean;
  canResumeOrder?: boolean;
  reviewReportCount?: number;
  pixel?: ReactNode;
  positions?: ReactNode;
  onTogglePause?: () => void | Promise<void>;
  onOpenReviewHistory?: () => void;
}) {
  const status = resolveAutoManagedStatus(account, autoTradingStatus);
  const skipNotice = autoTradingSkipNotice(autoTradingStatus);
  const positionRatio = account?.total_assets ? (account.market_value / account.total_assets) * 100 : null;
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
          title="模拟盘"
          summary={(
            <>
              <strong>{status.label}</strong>
              <span>{skipNotice ? `${skipNotice.title}：${skipNotice.text}` : "真实收益、影子收益和信号收益分区展示；自动交易只在模拟盘口径内执行。"}</span>
            </>
          )}
          actions={actions}
          items={[
            {
              key: "real-return",
              label: "真实收益（总收益率）",
              value: formatPct(account?.total_return_pct),
              tone: toneFromChange(account?.total_return_pct),
            },
            {
              key: "position-risk",
              label: "仓位与风控",
              value: positionRatio === null ? "--" : formatPct(positionRatio),
              tone: toneFromChange(account?.today_return_pct),
            },
            {
              key: "auto",
              label: "自动状态",
              value: autoTradingStatus?.running ? "运行中" : autoTradingStatus?.trading_time ? "待启动" : "非交易时间",
              tone: status.tone === "down" ? "down" : status.tone === "warn" ? "warn" : "neutral",
            },
            {
              key: "signal-return",
              label: "信号收益",
              value: formatPct(performance?.net_win_rate_pct),
              tone: toneFromChange(performance?.net_win_rate_pct),
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
