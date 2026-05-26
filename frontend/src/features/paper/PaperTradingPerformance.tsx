import type { CSSProperties } from "react";
import { Col, List, Row, Space, Typography } from "antd";
import type { PaperAgentRun, PaperGroupedPerformance, PaperPerformance, PaperSectorEtfT0Performance, PaperTagPerformance, RiskEventItem } from "../../types";
import { EmptyState, InfoPill, toneTextStyle } from "../workspace-shared/WorkspaceComponents";
import { formatPaperDateTime } from "./paperTradingFormatters";
import { formatInteger, formatNumber, formatPct, toneFromChange } from "../workspace-shared/workspaceFormatters";
import { DataTable } from "../../ui/table/DataTable";

const FULL_WIDTH_STYLE: CSSProperties = { width: "100%" };
const PERFORMANCE_PILL_ROW_STYLE: CSSProperties = { marginBottom: 6 };
const TAG_PERFORMANCE_STYLE: CSSProperties = {
  marginBottom: 6,
  padding: "6px 8px",
  border: "1px solid rgba(214, 165, 92, 0.22)",
  borderRadius: 8,
  background: "#fffaf0",
  color: "#6b5a3a",
  fontSize: 11,
};
const TRUNCATED_TEXT_STYLE: CSSProperties = {
  display: "block",
  minWidth: 0,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
const RISK_TODO_LIST_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
};
const RISK_TODO_ITEM_STYLE: CSSProperties = {
  display: "grid",
  gap: 3,
  borderRadius: 8,
  padding: 7,
  fontSize: 11,
};
const RISK_TODO_ITEM_HIGH_STYLE: CSSProperties = {
  background: "#fef2f2",
  color: "#991b1b",
};
const RISK_TODO_ITEM_MEDIUM_STYLE: CSSProperties = {
  background: "#fff8e8",
  color: "#8a5a16",
};

export function RiskEventList({ items }: { items: RiskEventItem[] }) {
  if (!items.length) return null;
  return (
    <div style={RISK_TODO_LIST_STYLE}>
      {items.slice(0, 2).map((item) => (
        <article key={item.id} style={item.severity === "high" ? { ...RISK_TODO_ITEM_STYLE, ...RISK_TODO_ITEM_HIGH_STYLE } : { ...RISK_TODO_ITEM_STYLE, ...RISK_TODO_ITEM_MEDIUM_STYLE }}>
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
    <Row gutter={[8, 8]} style={PERFORMANCE_PILL_ROW_STYLE}>
      <Col xs={24} sm={12} xl={6}>
        <InfoPill compact label="成交笔数" value={String(performance?.total_trades ?? 0)} />
      </Col>
      <Col xs={24} sm={12} xl={6}>
        <InfoPill compact label="胜率" value={formatPct(performance?.win_rate_pct)} />
      </Col>
      <Col xs={24} sm={12} xl={6}>
        <InfoPill compact label="平均单笔" value={formatPct(performance?.avg_trade_return_pct)} tone={toneFromChange(performance?.avg_trade_return_pct)} />
      </Col>
      <Col xs={24} sm={12} xl={6}>
        <InfoPill compact label="最大回撤" value={formatPct(performance?.max_drawdown_pct)} tone={toneFromChange(performance?.max_drawdown_pct)} />
      </Col>
    </Row>
  );
}

export function TagPerformanceStrip({ items }: { items: PaperTagPerformance[] }) {
  if (!items.length) return null;
  return (
    <Space wrap size={[5, 5]} style={TAG_PERFORMANCE_STYLE}>
      {items.slice(0, 4).map((item) => (
        <Typography.Text key={item.tag} style={{ color: "#6b5a3a", fontSize: 11 }}>
          {item.tag} {item.trades} 笔 · 均收 <Typography.Text strong style={toneTextStyle(toneFromChange(item.avg_return_pct))}>{formatPct(item.avg_return_pct)}</Typography.Text>
        </Typography.Text>
      ))}
    </Space>
  );
}

export function SectorEtfT0PerformancePanel({ item }: { item: PaperSectorEtfT0Performance | null }) {
  if (!item) return <EmptyState text="暂无 ETF T+0 自动交易绩效" />;
  return (
    <Space direction="vertical" size={6} style={FULL_WIDTH_STYLE}>
      <Row gutter={[8, 8]}>
        <Col xs={24} sm={12} xl={6}>
          <InfoPill compact label="自动委托" value={`${formatInteger(item.simulated_trades)} 笔`} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <InfoPill compact label="已闭合" value={`${formatInteger(item.simulated_closed_trades)} 笔`} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <InfoPill compact label="成交胜率" value={formatPct(item.simulated_win_rate_pct)} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <InfoPill compact label="平均收益" value={formatPct(item.simulated_avg_return_pct)} tone={toneFromChange(item.simulated_avg_return_pct)} />
        </Col>
      </Row>
      <DataTable<PaperSectorEtfT0Performance>
        rowKey={() => "sector-etf-t0"}
        dataSource={[item]}
        scroll={{ x: 680 }}
        columns={[
          { title: "跟踪样本", dataIndex: "shadow_sample_count", render: (value) => <strong>{formatInteger(value)}</strong> },
          { title: "已结算", dataIndex: "shadow_settled_count", render: (value) => formatInteger(value) },
          { title: "待结算", dataIndex: "shadow_pending_count", render: (value) => formatInteger(value) },
          { title: "影子胜率", dataIndex: "shadow_success_rate_pct", render: (value) => formatPct(value) },
          { title: "1日均收", dataIndex: "shadow_avg_return_1d_pct", render: (value) => <span className={toneFromChange(value)}>{formatPct(value)}</span> },
          { title: "3日均收", dataIndex: "shadow_avg_return_3d_pct", render: (value) => <span className={toneFromChange(value)}>{formatPct(value)}</span> },
        ]}
      />
      <Typography.Text type="secondary" style={{ fontSize: 11 }}>
        {item.notes?.[0] || "只统计 strategy_key=sector_etf_t0 的模拟成交，并和 ETF 机会池影子跟踪对账。"}
      </Typography.Text>
    </Space>
  );
}

export function GroupedPerformanceTable({ items, emptyText }: { items: PaperGroupedPerformance[]; emptyText: string }) {
  if (!items.length) return <EmptyState text={emptyText} />;
  return (
    <DataTable<PaperGroupedPerformance>
      rowKey={(item) => item.key || "unlabeled"}
      dataSource={items}
      scroll={{ x: 680 }}
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
    <List
      size="small"
      dataSource={items.slice(0, 5)}
      renderItem={(item) => {
        const response = item.response || {};
        const executed = Number(response.executed_count ?? (Array.isArray(response.executed) ? response.executed.length : 0));
        const skipped = Number(response.skipped_count ?? (Array.isArray(response.skipped) ? response.skipped.length : 0));
        const etfOrders = Number(response.sector_etf_t0_order_count ?? 0);
        const summary = String(response.summary || item.error_message || "--");
        const skipReason = agentRunSkipReason(response);
        return (
          <List.Item>
            <Row gutter={[8, 4]} align="middle" style={FULL_WIDTH_STYLE}>
              <Col xs={24} md={6}>
                <Space direction="vertical" size={0}>
                  <Typography.Text strong style={{ fontSize: 11 }}>{runStatusText(item.status)}</Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>{formatPaperDateTime(item.created_at)}</Typography.Text>
                </Space>
              </Col>
              <Col xs={24} md={5}>
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  执行 {executed} / 跳过 {skipped}{etfOrders ? ` / ETF ${etfOrders}` : ""}
                </Typography.Text>
              </Col>
              <Col xs={24} md={skipReason ? 8 : 13}>
                <Typography.Text type="secondary" style={{ ...TRUNCATED_TEXT_STYLE, fontSize: 11 }} title={summary}>{summary}</Typography.Text>
              </Col>
              {skipReason ? (
                <Col xs={24} md={5}>
                  <Typography.Text type="secondary" style={{ ...TRUNCATED_TEXT_STYLE, fontSize: 11 }} title={skipReason}>未买原因：{skipReason}</Typography.Text>
                </Col>
              ) : null}
            </Row>
          </List.Item>
        );
      }}
    />
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
