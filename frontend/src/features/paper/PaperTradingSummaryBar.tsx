import type { PaperAccount, PaperAutoTradingStatus, PaperPerformance } from "../../types";
import { Button } from "antd";
import { formatMoneyPlain, formatPct, toneFromChange } from "../workspace-shared/workspaceFormatters";
import { autoTradingSkipNotice, resolveAutoManagedStatus } from "./paperTradingStatus";
import { formatPaperDateTime } from "./paperTradingFormatters";

export function PaperTradingSummaryBar({
  account,
  performance,
  autoTradingStatus,
  loading,
  canOpenOrder,
  onOpenOrderEntry,
  onTogglePause,
}: {
  account: PaperAccount | null;
  performance: PaperPerformance | null;
  autoTradingStatus: PaperAutoTradingStatus | null;
  loading: boolean;
  canOpenOrder: boolean;
  onOpenOrderEntry: () => void;
  onTogglePause?: () => void | Promise<void>;
}) {
  const status = resolveAutoManagedStatus(account, autoTradingStatus);
  const skipNotice = autoTradingSkipNotice(autoTradingStatus);
  const totalTone = toneFromChange(account?.total_return_pct);
  const dayTone = toneFromChange(account?.today_return_pct);

  const metrics = [
    { label: "总资产", value: formatMoneyPlain(account?.total_assets), tone: "neutral" },
    { label: "当日收益", value: formatPct(account?.today_return_pct), tone: dayTone },
    { label: "可用资金", value: formatMoneyPlain(account?.cash_available), tone: "neutral" },
    { label: "持仓市值", value: formatMoneyPlain(account?.market_value), tone: "neutral" },
    { label: "总收益率", value: formatPct(account?.total_return_pct), tone: totalTone },
    { label: "净胜率", value: formatPct(performance?.net_win_rate_pct), tone: toneFromChange(performance?.net_win_rate_pct) },
  ] as const;

  return (
    <section className="panel paper-summary-bar">
      <div className="paper-summary-main">
        <div className="paper-summary-status">
          <span className={`status-chip ${status.tone}`}>{status.label}</span>
          {autoTradingStatus?.last_cycle_at ? (
            <small>最近刷新 {formatPaperDateTime(autoTradingStatus.last_cycle_at)}</small>
          ) : (
            <small>交易时间内自动刷新</small>
          )}
        </div>
        <div className="paper-summary-metrics">
          {metrics.map((item) => (
            <article key={item.label} className={`paper-summary-metric ${item.tone}`}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </article>
          ))}
        </div>
        <div className="paper-summary-actions">
          <Button
            type="primary"
            disabled={!canOpenOrder || loading}
            onClick={onOpenOrderEntry}
          >
            {canOpenOrder ? "录入委托" : "自动交易中"}
          </Button>
          {account?.status === "paused" && onTogglePause ? (
            <Button type="default" disabled={loading} onClick={() => void onTogglePause()}>
              恢复自动委托
            </Button>
          ) : null}
        </div>
      </div>
      {skipNotice ? (
        <div className={`paper-summary-alert ${skipNotice.tone}`}>
          <strong>{skipNotice.title}</strong>
          <span>{skipNotice.text}</span>
          {skipNotice.time ? <em>{formatPaperDateTime(skipNotice.time)}</em> : null}
        </div>
      ) : null}
    </section>
  );
}
