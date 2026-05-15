import {
  formatInteger,
  formatMoneyPlain,
  formatPct,
  formatPrice,
} from "../features/trading-workspace/workspaceFormatters";
import type {
  PaperAgentRun,
  PaperAutoTradingStatus,
  PaperStockPnlResponse,
} from "../types";
import type { RiskEventItem } from "../types";

export function MobileAutoTradingStatusCard({
  status,
}: {
  status: PaperAutoTradingStatus | null;
}) {
  const title = autoTitle(status);
  const note = autoNote(status);
  const tone = autoTone(status);

  return (
    <section className={`mobile-paper-card mobile-paper-status-card tone-${tone}`}>
      <div className="mobile-paper-section-head">
        <strong>自动交易状态</strong>
        <small>{status?.last_cycle_at ? `最近执行 ${formatClock(status.last_cycle_at)}` : "等待下一轮扫描"}</small>
      </div>
      <div className="mobile-paper-status-main">
        <strong>{title}</strong>
        <p>{note}</p>
      </div>
      <div className="mobile-paper-status-grid">
        <span>交易时段 <b>{status?.trading_time ? "是" : "否"}</b></span>
        <span>本轮通过 <b>{formatInteger(status?.last_cycle_passed)}</b></span>
        <span>已执行 <b>{formatInteger(status?.last_cycle_executed)}</b></span>
        <span>最近跳过 <b>{formatInteger(status?.last_cycle_skipped)}</b></span>
      </div>
    </section>
  );
}

export function MobilePaperStockPnlCard({
  stockPnl,
}: {
  stockPnl: PaperStockPnlResponse | null;
}) {
  const rows = stockPnl?.items?.slice(0, 5) ?? [];
  const summary = stockPnl?.summary;
  return (
    <section className="mobile-paper-card">
      <div className="mobile-paper-section-head">
        <strong>个股盈亏</strong>
        <small>{rows.length ? "按总盈亏排序前 5" : "暂无个股盈亏"}</small>
      </div>
      <div className="mobile-paper-pills">
        <span>总盈亏 <b className={`tone-${moneyTone(summary?.account_total_pnl)}`}>{formatMoneyPlain(summary?.account_total_pnl)}</b></span>
        <span>已实现 <b className={`tone-${moneyTone(summary?.realized_pnl)}`}>{formatMoneyPlain(summary?.realized_pnl)}</b></span>
        <span>浮动 <b className={`tone-${moneyTone(summary?.unrealized_pnl)}`}>{formatMoneyPlain(summary?.unrealized_pnl)}</b></span>
      </div>
      <div className="mobile-paper-scroll mobile-paper-three-scroll">
        {rows.length ? rows.map((item) => (
          <article className="mobile-paper-line mobile-paper-stock-line" key={item.symbol}>
            <strong>{item.name || item.symbol}</strong>
            <span>{item.symbol}</span>
            <b>{formatMoneyPlain(item.total_pnl)}</b>
            <span>持仓 {formatInteger(item.current_quantity)}</span>
            <span>费用 {formatMoneyPlain(item.total_fees)}</span>
          </article>
        )) : <div className="mobile-app-empty">暂无个股盈亏数据</div>}
      </div>
    </section>
  );
}

export function MobilePaperRiskEventsCard({
  items,
}: {
  items: RiskEventItem[];
}) {
  return (
    <section className="mobile-paper-card">
      <div className="mobile-paper-section-head">
        <strong>风险待办</strong>
        <small>{items.length ? "需要先处理，再考虑继续委托" : "当前没有风险待办"}</small>
      </div>
      <div className="mobile-paper-scroll mobile-paper-three-scroll">
        {items.length ? items.slice(0, 5).map((item) => (
          <article className={`mobile-paper-risk-item tone-${riskTone(item.severity)}`} key={item.id}>
            <strong>{riskTitle(item)}</strong>
            <p>{item.message}</p>
            <small>{formatClock(item.triggered_at)}</small>
          </article>
        )) : <div className="mobile-app-empty">当前没有触发风险事件</div>}
      </div>
    </section>
  );
}

export function MobilePaperRecentRunsCard({
  items,
}: {
  items: PaperAgentRun[];
}) {
  return (
    <section className="mobile-paper-card">
      <div className="mobile-paper-section-head">
        <strong>最近执行</strong>
        <small>{items.length ? "看系统刚刚做了什么" : "暂无执行记录"}</small>
      </div>
      <div className="mobile-paper-scroll mobile-paper-three-scroll">
        {items.length ? items.slice(0, 5).map((item) => (
          <article className="mobile-paper-risk-item mobile-paper-run-item" key={item.id}>
            <strong>{runTitle(item)}</strong>
            <p>{runSummary(item)}</p>
            <small>{formatClock(item.created_at)}</small>
          </article>
        )) : <div className="mobile-app-empty">暂无系统执行记录</div>}
      </div>
    </section>
  );
}

function autoTitle(status: PaperAutoTradingStatus | null) {
  if (!status) return "状态读取中";
  if (status.blocking_reason) return "当前暂停新增委托";
  if (!status.trading_time) return "非交易时段，保持静默";
  if (status.running) return "交易时段自动运行中";
  return status.reason || "自动交易暂未运行";
}

function autoNote(status: PaperAutoTradingStatus | null) {
  if (!status) return "正在读取自动交易状态。";
  if (status.blocking_reason) return status.blocking_reason;
  if (status.last_skip_reason) return `最近未买原因：${status.last_skip_reason}`;
  if (status.last_cycle_summary) return status.last_cycle_summary;
  return status.reason || "当前没有额外说明。";
}

function autoTone(status: PaperAutoTradingStatus | null): "positive" | "negative" | "warning" | "neutral" {
  if (!status) return "neutral";
  if (status.blocking_reason || status.circuit_open) return "warning";
  if (status.running) return "positive";
  if (!status.trading_time) return "neutral";
  return "warning";
}

function riskTone(severity: string): "positive" | "negative" | "warning" | "neutral" {
  if (severity === "high") return "negative";
  if (severity === "medium") return "warning";
  if (severity === "low") return "positive";
  return "neutral";
}

function riskTitle(item: RiskEventItem) {
  if (item.symbol) {
    return `${item.symbol} 需要处理`;
  }
  return "账户风险提醒";
}

function runTitle(item: PaperAgentRun) {
  const statusText =
    item.status === "completed"
      ? "已完成"
      : item.status === "skipped"
        ? "已跳过"
        : item.status === "failed"
          ? "执行失败"
          : item.status;
  return `${item.run_type} · ${statusText}`;
}

function runSummary(item: PaperAgentRun) {
  const response = item.response ?? {};
  const summary =
    typeof response.summary === "string"
      ? response.summary
      : typeof response.message === "string"
        ? response.message
        : "";
  return summary || item.error_message || "本轮没有额外说明。";
}

function moneyTone(value?: number | null): "positive" | "negative" | "neutral" {
  if (typeof value !== "number" || !Number.isFinite(value) || value === 0) return "neutral";
  return value > 0 ? "positive" : "negative";
}

function formatClock(value?: string | null) {
  if (!value) return "--";
  return value.replace("T", " ").slice(5, 16);
}

export function defaultPaperOrderSeed(status: PaperAutoTradingStatus | null) {
  return {
    defaultSymbol: status?.last_skip_symbol || "",
    defaultPrice: null as number | null,
  };
}
