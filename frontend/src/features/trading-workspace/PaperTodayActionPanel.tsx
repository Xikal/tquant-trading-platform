import type { IntradayConfirmationItem, PaperAgentRun, PaperAutoTradingStatus, RiskEventItem } from "../../types";
import { formatPaperDateTime } from "./paperTradingFormatters";

export function PaperTodayActionPanel({
  autoTradingStatus,
  autoTradingRuns,
  riskEvents,
  intradayConfirmations,
}: {
  autoTradingStatus: PaperAutoTradingStatus | null;
  autoTradingRuns: PaperAgentRun[];
  riskEvents: RiskEventItem[];
  intradayConfirmations: IntradayConfirmationItem[];
}) {
  const openRisk = riskEvents.find((item) => item.status !== "resolved") ?? null;
  const confirmation = intradayConfirmations[0] ?? null;
  const actions = buildActionTimeline(autoTradingStatus, autoTradingRuns, confirmation);

  return (
    <section className="panel paper-today-actions">
      <div className="panel-title">
        <h2>今日动作</h2>
        <span className="hint">{autoTradingStatus?.running ? "系统自动执行中" : "当前未自动下单"}</span>
      </div>
      <div className="paper-today-status-row">
        <article className="paper-today-card">
          <span>自动交易状态</span>
          <strong>{autoTradingStatus?.running ? "运行中" : autoTradingStatus?.trading_time ? "待启动" : "非交易时间"}</strong>
          <small>{autoTradingStatus?.last_cycle_summary || "没有新的自动交易动作。"}</small>
        </article>
        <article className={`paper-today-card ${openRisk ? "warn" : "ok"}`}>
          <span>当前阻断原因</span>
          <strong>{openRisk ? "需要处理" : "无阻断"}</strong>
          <small>{openRisk?.message || autoTradingStatus?.blocking_reason || "可以按计划执行。"} </small>
        </article>
        <article className="paper-today-card">
          <span>盘中确认</span>
          <strong>{confirmation ? `${confirmation.symbol} ${confirmation.confirmed || confirmation.late_confirmed ? "已确认" : "待观察"}` : "暂无待确认"}</strong>
          <small>{confirmation?.reason || "没有需要人工确认的信号。"} </small>
        </article>
      </div>
      <div className="paper-action-timeline">
        {actions.length ? actions.map((item, index) => (
          <article key={`${item.time}-${index}`} className="paper-action-line">
            <time>{item.time}</time>
            <div>
              <strong>{item.title}</strong>
              <span>{item.detail}</span>
            </div>
          </article>
        )) : (
          <div className="paper-action-empty">今日暂无执行记录。</div>
        )}
      </div>
    </section>
  );
}

function buildActionTimeline(
  autoTradingStatus: PaperAutoTradingStatus | null,
  autoTradingRuns: PaperAgentRun[],
  confirmation: IntradayConfirmationItem | null,
) {
  const items = autoTradingRuns.slice(0, 3).map((item) => {
    const response = item.response || {};
    const summary = String(response.summary || item.error_message || runStatusText(item.status));
    return {
      time: formatPaperDateTime(item.created_at).slice(11, 16),
      title: runStatusText(item.status),
      detail: summary,
    };
  });
  if (autoTradingStatus?.last_cycle_at && autoTradingStatus?.last_cycle_summary) {
    items.unshift({
      time: formatPaperDateTime(autoTradingStatus.last_cycle_at).slice(11, 16),
      title: "最近一轮",
      detail: autoTradingStatus.last_cycle_summary,
    });
  }
  if (confirmation) {
    items.unshift({
      time: formatPaperDateTime(confirmation.updated_at || confirmation.trade_date).slice(11, 16),
      title: "分时确认",
      detail: `${confirmation.symbol} ${confirmation.confirmed || confirmation.late_confirmed ? "已确认" : "待观察"} · ${confirmation.reason || "等待盘中承接确认"}`,
    });
  }
  return items.slice(0, 3);
}

function runStatusText(status: string): string {
  if (status === "succeeded") return "已执行";
  if (status === "failed") return "执行失败";
  if (status === "skipped") return "本轮跳过";
  if (status === "running") return "执行中";
  return "已记录";
}
