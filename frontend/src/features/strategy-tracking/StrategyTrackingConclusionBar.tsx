import { Tooltip } from "antd";
import { InfoCircleOutlined } from "../../ui/icons";
import type { StrategyTrackingItem, StrategyTrackingListResponse } from "../../types";
import { ConclusionBar } from "../../ui/surfaces";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function StrategyTrackingConclusionBar({
  result,
  range,
  activeStatus,
  snapshotMeta,
  onSelectStatus,
}: {
  result: StrategyTrackingListResponse;
  range: number;
  activeStatus: string;
  snapshotMeta: string;
  onSelectStatus: (status: string) => void;
}) {
  const summary = result.summary;
  const focusCount = countStatus(result.items, "focus");
  const waitEntryCount = countStatus(result.items, "wait_entry");
  const weakeningCount = countStatus(result.items, "weakening");
  const reviewCount = summary.needs_review_count + summary.abnormal_return_count;
  const rangeText = range === 1 ? "今日" : `近 ${range} 日`;
  const buyClassCount = result.items.filter((item) => item.signal_state === "buy_now" || item.signal_state === "soft_buy_now").length;
  const observeClassCount = Math.max(0, result.items.length - buyClassCount);
  const focusHelp = "已到计划买点且风险线未破，仍需看仓位和风控。";
  const waitEntryHelp = "还没到计划买点，只能提醒观察，不是买入动作。";
  const weakeningHelp = "跌破风险线或支撑，优先复盘失败原因。";
  const sampleHelp = `${snapshotMeta} · 平均涨跌 ${formatPct(summary.avg_current_return_pct)} · 复核 ${reviewCount}`;

  return (
    <section className="strategy-tracking-conclusion strategy-tracking-conclusion--compact">
      <ConclusionBar
        title="策略跟踪"
        summary={(
          <>
            <strong>{rangeText}共有 {summary.tracking_count} 条跟踪信号，买入类和观察类分开看。</strong>
            <span>买入类仅含确定可买/小仓试买；接近买点、观察确认等观察类只提醒复盘。</span>
          </>
        )}
        items={[
          {
            key: "focus",
            label: helpLabel("重点跟踪", focusHelp),
            value: focusCount,
            tone: focusCount ? "up" : "neutral",
            active: activeStatus === "focus",
            onClick: () => onSelectStatus(activeStatus === "focus" ? "" : "focus"),
          },
          {
            key: "wait_entry",
            label: helpLabel("观察等待", waitEntryHelp),
            value: waitEntryCount,
            tone: waitEntryCount ? "warn" : "neutral",
            active: activeStatus === "wait_entry",
            onClick: () => onSelectStatus(activeStatus === "wait_entry" ? "" : "wait_entry"),
          },
          {
            key: "weakening",
            label: helpLabel("已走弱", weakeningHelp),
            value: weakeningCount,
            tone: weakeningCount ? "down" : "neutral",
            active: activeStatus === "weakening",
            onClick: () => onSelectStatus(activeStatus === "weakening" ? "" : "weakening"),
          },
          {
            key: "sample",
            label: helpLabel("样本与口径", sampleHelp),
            value: `${buyClassCount} 买入类 / ${observeClassCount} 观察类`,
            tone: reviewCount ? "warn" : "neutral",
          },
        ]}
      />
    </section>
  );
}

function countStatus(items: StrategyTrackingItem[], status: string): number {
  return items.filter((item) => item.user_friendly_status === status).length;
}

function helpLabel(label: string, help: string) {
  return (
    <span className="strategy-tracking-metric-label">
      <span>{label}</span>
      <Tooltip title={help}>
        <InfoCircleOutlined
          aria-label={`${label}说明`}
          className="strategy-tracking-help-icon"
        />
      </Tooltip>
    </span>
  );
}
