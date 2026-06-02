import type { PaperAgentRun, PaperAutoTradingStatus, RiskEventItem } from "../../types";
import { formatPaperDateTime } from "./paperTradingFormatters";

export function PaperTodayActionPanel({
  autoTradingStatus,
  autoTradingRuns,
}: {
  autoTradingStatus: PaperAutoTradingStatus | null;
  autoTradingRuns: PaperAgentRun[];
  riskEvents: RiskEventItem[];
}) {
  const actions = buildActionTimeline(autoTradingStatus, autoTradingRuns);

  return (
    <section className="paper-action-hud" aria-label="今日动作与自动交易状态">
      <div className="paper-action-hud__monitor">
        <div className="paper-action-hud__panel-title paper-action-hud__panel-title--split">
          <span>
            <span className="paper-action-hud__title-mark paper-action-hud__title-mark--pulse" />
            实时同步监控日志
          </span>
          <strong>SYS_FLOW: OK</strong>
        </div>
        <div className="paper-action-hud__console" role="log">
          {actions.map((item, index) => (
            <p key={`${item.time}-${index}`}>
              <span>[{item.time}] </span>
              <strong className={`paper-action-hud__log-tag paper-action-hud__log-tag--${item.tone}`}>{item.title}:</strong>
              <span> {item.detail}</span>
            </p>
          ))}
        </div>
      </div>
    </section>
  );
}

function buildActionTimeline(
  autoTradingStatus: PaperAutoTradingStatus | null,
  autoTradingRuns: PaperAgentRun[],
) {
  const items = autoTradingRuns.slice(0, 3).map((item) => {
    const response = item.response || {};
    const summary = String(response.summary || item.error_message || runStatusText(item.status));
    return {
      time: formatPaperDateTime(item.created_at).slice(11, 16),
      title: runStatusText(item.status),
      detail: summary,
      tone: runStatusTone(item.status),
    };
  });
  if (autoTradingStatus?.last_cycle_at && autoTradingStatus?.last_cycle_summary) {
    items.unshift({
      time: formatPaperDateTime(autoTradingStatus.last_cycle_at).slice(11, 16),
      title: "INFO",
      detail: autoTradingStatus.last_cycle_summary,
      tone: "info",
    });
  }
  if (!items.length) {
    items.push(
      { time: "09:30:00", title: "SYSTEM_INIT", detail: "维斯量化终端同步启动", tone: "init" },
      { time: "09:30:05", title: "LINK", detail: "神经元连接（1st Pilot）同步率稳定在 84.2%", tone: "link" },
      { time: "09:31:24", title: "INFO", detail: "A股沪深两市指数馈入开始...", tone: "info" },
    );
  }
  return items.slice(0, 4);
}

function runStatusText(status: string): string {
  if (status === "succeeded") return "SELL";
  if (status === "failed") return "RISK";
  if (status === "skipped") return "INFO";
  if (status === "running") return "AUTO";
  return "LINK";
}

function runStatusTone(status: string): string {
  if (status === "succeeded") return "sell";
  if (status === "failed") return "risk";
  if (status === "running") return "auto";
  return "info";
}
