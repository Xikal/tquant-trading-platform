import type { PaperAgentRun, PaperGroupedPerformance, PaperPerformance, PaperSectorEtfT0Performance, PaperTagPerformance, RiskEventItem } from "../../types";
import { EmptyState, InfoPill } from "../workspace-shared/WorkspaceComponents";
import { formatPaperDateTime } from "./paperTradingFormatters";
import { formatInteger, formatNumber, formatPct, toneFromChange } from "../workspace-shared/workspaceFormatters";
import { DataTable } from "../../ui/table/DataTable";

export function RiskEventList({ items }: { items: RiskEventItem[] }) {
  if (!items.length) return null;
  return (
    <div className="paper-risk-todo-list">
      {items.slice(0, 2).map((item) => (
        <article className={item.severity === "high" ? "high" : "medium"} key={item.id}>
          <strong>{item.severity === "high" ? "需要立即处理" : "需要关注"}</strong>
          <span>{item.message}</span>
          <small>{item.symbol || "账户"} · {item.status === "resolved" ? "已处理" : "待处理"}</small>
        </article>
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
      <DataTable<PaperSectorEtfT0Performance>
        rowKey={() => "sector-etf-t0"}
        dataSource={[item]}
        columns={[
          { title: "跟踪样本", dataIndex: "shadow_sample_count", render: (value) => <strong>{formatInteger(value)}</strong> },
          { title: "已结算", dataIndex: "shadow_settled_count", render: (value) => formatInteger(value) },
          { title: "待结算", dataIndex: "shadow_pending_count", render: (value) => formatInteger(value) },
          { title: "影子胜率", dataIndex: "shadow_success_rate_pct", render: (value) => formatPct(value) },
          { title: "1日均收", dataIndex: "shadow_avg_return_1d_pct", render: (value) => <span className={toneFromChange(value)}>{formatPct(value)}</span> },
          { title: "3日均收", dataIndex: "shadow_avg_return_3d_pct", render: (value) => <span className={toneFromChange(value)}>{formatPct(value)}</span> },
        ]}
      />
      <p className="muted">
        {item.notes?.[0] || "只统计 strategy_key=sector_etf_t0 的模拟成交，并和 ETF 机会池影子跟踪对账。"}
      </p>
    </div>
  );
}

export function GroupedPerformanceTable({ items, emptyText }: { items: PaperGroupedPerformance[]; emptyText: string }) {
  if (!items.length) return <EmptyState text={emptyText} />;
  return (
    <DataTable<PaperGroupedPerformance>
      className="paper-performance-table"
      rowKey={(item) => item.key || "unlabeled"}
      dataSource={items}
      columns={[
        { title: "分组", render: (_value, item) => <strong>{item.key || "未标注"}</strong> },
        { title: "成交", dataIndex: "trades", align: "right", render: (value) => formatInteger(value) },
        { title: "胜率", dataIndex: "win_rate_pct", align: "right", render: (value) => formatPct(value) },
        { title: "净胜率", dataIndex: "net_win_rate_pct", align: "right", render: (value) => formatPct(value) },
        { title: "均收", dataIndex: "avg_return_pct", align: "right", render: (value) => <span className={toneFromChange(value)}>{formatPct(value)}</span> },
        {
          title: "PF",
          dataIndex: "profit_factor",
          align: "right",
          render: (value) => <span className={typeof value === "number" && value > 1 ? "up" : "neutral"}>{formatNumber(value)}</span>,
        },
      ]}
    />
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
