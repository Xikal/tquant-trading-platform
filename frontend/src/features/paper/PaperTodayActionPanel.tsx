import { Card, Col, Row, Space, Statistic, Tag, Timeline, Typography } from "antd";
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
    <Card
      title="今日动作"
      extra={<Tag color={autoTradingStatus?.running ? "green" : "default"}>{autoTradingStatus?.running ? "系统自动执行中" : "当前未自动下单"}</Tag>}
      styles={{ body: { display: "flex", flexDirection: "column", gap: 12 } }}
    >
      <Row gutter={[8, 8]}>
        <StatusItem
          label="自动交易状态"
          value={autoTradingStatus?.running ? "运行中" : autoTradingStatus?.trading_time ? "待启动" : "非交易时间"}
          detail={autoTradingStatus?.last_cycle_summary || "没有新的自动交易动作。"}
        />
        <StatusItem
          label="当前阻断原因"
          value={openRisk ? "需要处理" : "无阻断"}
          detail={openRisk?.message || autoTradingStatus?.blocking_reason || "可以按计划执行。"}
          tone={openRisk ? "warning" : "success"}
        />
        <StatusItem
          label="盘中确认"
          value={confirmation ? `${confirmation.symbol} ${confirmation.confirmed || confirmation.late_confirmed ? "已确认" : "待观察"}` : "暂无待确认"}
          detail={confirmation?.reason || "没有需要人工确认的信号。"}
        />
      </Row>
      {actions.length ? (
        <Timeline
          items={actions.map((item, index) => ({
            key: `${item.time}-${index}`,
            children: (
              <Space direction="vertical" size={1}>
                <Typography.Text strong>{item.time} {item.title}</Typography.Text>
                <Typography.Text type="secondary">{item.detail}</Typography.Text>
              </Space>
            ),
          }))}
        />
      ) : <Typography.Text type="secondary">今日暂无执行记录。</Typography.Text>}
    </Card>
  );
}

function StatusItem({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "success" | "warning";
}) {
  return (
    <Col xs={24}>
      <Card size="small" style={tone === "success" ? { background: "#f0fbf4" } : tone === "warning" ? { background: "#fff8e8" } : undefined}>
        <Space direction="vertical" size={3}>
          <Statistic title={label} value={value} valueStyle={{ fontSize: 15 }} />
          <Typography.Text type="secondary">{detail}</Typography.Text>
        </Space>
      </Card>
    </Col>
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
