import type { PaperAgentRun, PaperGroupedPerformance, PaperPerformance, PaperSectorEtfT0Performance, PaperTagPerformance, RiskEventItem } from "../../types";
import { EmptyState, InfoPill } from "./WorkspaceComponents";
import { formatInteger, formatNumber, formatPct, toneFromChange } from "./workspaceFormatters";
import { formatPaperDateTime } from "./paperTradingFormatters";

export function RiskEventList({ items }: { items: RiskEventItem[] }) {
  if (!items.length) return null;
  return (
    <div className="context-row paper-context-row">
      {items.slice(0, 2).map((item) => (
        <span key={item.id}>{item.severity === "high" ? "高风险" : "提醒"}：{item.message}</span>
      ))}
    </div>
  );
}

export function PerformancePills({ performance }: { performance: PaperPerformance | null }) {
  return (
    <div className="context-row paper-context-row">
      <InfoPill label="成交笔数" value={String(performance?.total_trades ?? 0)} />
      <InfoPill label="胜率" value={formatPct(performance?.win_rate_pct)} />
      <InfoPill label="平均单笔" value={formatPct(performance?.avg_trade_return_pct)} tone={toneFromChange(performance?.avg_trade_return_pct)} />
      <InfoPill label="最大回撤" value={formatPct(performance?.max_drawdown_pct)} tone={toneFromChange(performance?.max_drawdown_pct)} />
    </div>
  );
}

export function TagPerformanceStrip({ items }: { items: PaperTagPerformance[] }) {
  if (!items.length) return null;
  return (
    <div className="paper-tag-performance">
      {items.slice(0, 4).map((item) => (
        <span key={item.tag}>
          {item.tag} {item.trades} 笔 · 均收 <b className={toneFromChange(item.avg_return_pct)}>{formatPct(item.avg_return_pct)}</b>
        </span>
      ))}
    </div>
  );
}

export function SectorEtfT0PerformancePanel({ item }: { item: PaperSectorEtfT0Performance | null }) {
  if (!item) return <EmptyState text="暂无 ETF T+0 自动交易绩效" />;
  return (
    <div className="paper-performance-table paper-etf-t0-table">
      <div className="context-row paper-context-row">
        <InfoPill label="自动委托" value={`${formatInteger(item.simulated_trades)} 笔`} />
        <InfoPill label="已闭合" value={`${formatInteger(item.simulated_closed_trades)} 笔`} />
        <InfoPill label="成交胜率" value={formatPct(item.simulated_win_rate_pct)} />
        <InfoPill label="平均收益" value={formatPct(item.simulated_avg_return_pct)} tone={toneFromChange(item.simulated_avg_return_pct)} />
      </div>
      <div className="paper-performance-head">
        <span>跟踪样本</span>
        <span>已结算</span>
        <span>待结算</span>
        <span>影子胜率</span>
        <span>1日均收</span>
        <span>3日均收</span>
      </div>
      <div className="paper-performance-row">
        <strong>{formatInteger(item.shadow_sample_count)}</strong>
        <span>{formatInteger(item.shadow_settled_count)}</span>
        <span>{formatInteger(item.shadow_pending_count)}</span>
        <span>{formatPct(item.shadow_success_rate_pct)}</span>
        <span className={toneFromChange(item.shadow_avg_return_1d_pct)}>{formatPct(item.shadow_avg_return_1d_pct)}</span>
        <span className={toneFromChange(item.shadow_avg_return_3d_pct)}>{formatPct(item.shadow_avg_return_3d_pct)}</span>
      </div>
      <p className="muted">
        {item.notes?.[0] || "只统计 strategy_key=sector_etf_t0 的模拟成交，并和 ETF 机会池影子跟踪对账。"}
      </p>
    </div>
  );
}

export function GroupedPerformanceTable({ items, emptyText }: { items: PaperGroupedPerformance[]; emptyText: string }) {
  if (!items.length) return <EmptyState text={emptyText} />;
  return (
    <div className="paper-performance-table">
      <div className="paper-performance-head">
        <span>分组</span>
        <span>成交</span>
        <span>胜率</span>
        <span>净胜率</span>
        <span>均收</span>
        <span>PF</span>
      </div>
      {items.map((item) => {
        const avgTone = toneFromChange(item.avg_return_pct);
        const pfTone = typeof item.profit_factor === "number" && item.profit_factor > 1 ? "up" : "neutral";
        return (
          <div className="paper-performance-row" key={item.key || "unlabeled"}>
            <strong>{item.key || "未标注"}</strong>
            <span>{formatInteger(item.trades)}</span>
            <span>{formatPct(item.win_rate_pct)}</span>
            <span>{formatPct(item.net_win_rate_pct)}</span>
            <span className={avgTone}>{formatPct(item.avg_return_pct)}</span>
            <span className={pfTone}>{formatNumber(item.profit_factor)}</span>
          </div>
        );
      })}
    </div>
  );
}

export function AgentRunList({ items }: { items: PaperAgentRun[] }) {
  if (!items.length) return <EmptyState text="暂无自动交易日志" />;
  return (
    <div className="line-list">
      {items.slice(0, 5).map((item) => {
        const response = item.response || {};
        const executed = Number(response.executed_count ?? (Array.isArray(response.executed) ? response.executed.length : 0));
        const skipped = Number(response.skipped_count ?? (Array.isArray(response.skipped) ? response.skipped.length : 0));
        const etfOrders = Number(response.sector_etf_t0_order_count ?? 0);
        const summary = String(response.summary || item.error_message || "--");
        const skipReason = agentRunSkipReason(response);
        return (
          <article className="paper-row paper-agent-run-row" key={item.id}>
            <div className="paper-stock-name">
              <strong>{runStatusText(item.status)}</strong>
              <span>{formatPaperDateTime(item.created_at)}</span>
            </div>
            <span>执行 {executed} / 跳过 {skipped}{etfOrders ? ` / ETF ${etfOrders}` : ""}</span>
            <span>{summary}</span>
            {skipReason ? <span className="paper-run-reason">未买原因：{skipReason}</span> : null}
          </article>
        );
      })}
    </div>
  );
}

function agentRunSkipReason(response: Record<string, unknown>): string {
  const skipped = response.skipped;
  if (Array.isArray(skipped)) {
    for (const item of skipped) {
      if (!item || typeof item !== "object") continue;
      const row = item as Record<string, unknown>;
      const reason = String(row.reason || "").trim();
      if (!reason) continue;
      const symbol = String(row.symbol || "").trim();
      return symbol ? `${symbol}：${reason}` : reason;
    }
  }
  const filtered = response.filtered_reasons;
  if (Array.isArray(filtered)) {
    for (const item of filtered) {
      if (!item || typeof item !== "object") continue;
      const row = item as Record<string, unknown>;
      const reason = String(row.reason || "").trim();
      if (!reason) continue;
      const symbol = String(row.symbol || "").trim();
      return symbol ? `${symbol}：${reason}` : reason;
    }
  }
  return "";
}

function runStatusText(status: string): string {
  if (status === "succeeded") return "已完成";
  if (status === "failed") return "失败";
  if (status === "skipped") return "跳过";
  if (status === "running") return "运行中";
  return status || "--";
}
