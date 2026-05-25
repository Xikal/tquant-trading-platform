import { Col, Row, Space, Statistic, Tag, Timeline, Typography } from "antd";
import type { PaperAgentRun, PaperAutoTradingStatus, RiskEventItem } from "../../types";
import { formatPaperDateTime } from "./paperTradingFormatters";

export function PaperTodayActionPanel({
  autoTradingStatus,
  autoTradingRuns,
  riskEvents,
}: {
  autoTradingStatus: PaperAutoTradingStatus | null;
  autoTradingRuns: PaperAgentRun[];
  riskEvents: RiskEventItem[];
}) {
  const openRisk = riskEvents.find((item) => item.status !== "resolved") ?? null;
  const actions = buildActionTimeline(autoTradingStatus, autoTradingRuns);

  return (
    <Space direction="vertical" size={8} style={{ width: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <Typography.Text strong style={{ fontSize: 13 }}>今日动作</Typography.Text>
        <Tag color={autoTradingStatus?.running ? "green" : "default"}>
          {autoTradingStatus?.running ? "系统自动执行中" : "当前未自动下单"}
        </Tag>
      </div>
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
          label="自动交易触发"
          value={autoTradingStatus?.running ? "已执行" : autoTradingStatus?.trading_time ? "等待下一轮" : "非交易时间"}
          detail={autoTradingStatus?.last_cycle_summary || "自动交易按计划轮询，不依赖人工确认。"}
        />
      </Row>
      {actions.length ? (
        <Timeline
          items={actions.map((item, index) => ({
            key: `${item.time}-${index}`,
            children: (
              <Space orientation="vertical" size={1}>
                <Typography.Text strong>{item.time} {item.title}</Typography.Text>
                <Typography.Text type="secondary">{item.detail}</Typography.Text>
              </Space>
            ),
          }))}
        />
      ) : <Typography.Text type="secondary">今日暂无执行记录。</Typography.Text>}
    </Space>
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
      <div style={{
        background: tone === "success" ? "#f0fbf4" : tone === "warning" ? "#fff8e8" : "#fff",
        border: "1px solid #edf0f5",
        borderRadius: 6,
        padding: 8,
      }}>
        <Space orientation="vertical" size={3}>
          <Statistic title={label} value={value} styles={{ content: { fontSize: 14 } }} />
          <Typography.Text type="secondary" style={{ fontSize: 12, lineHeight: 1.35 }}>{detail}</Typography.Text>
        </Space>
      </div>
    </Col>
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
    };
  });
  if (autoTradingStatus?.last_cycle_at && autoTradingStatus?.last_cycle_summary) {
    items.unshift({
      time: formatPaperDateTime(autoTradingStatus.last_cycle_at).slice(11, 16),
      title: "最近一轮",
      detail: autoTradingStatus.last_cycle_summary,
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
