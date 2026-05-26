import type { FactorEvalResult } from "../../api/factorMining";
import { Alert, Card, Col, Row, Space, Statistic, Tag, Typography } from "antd";
import { formatPct } from "../backtest/backtestDisplay";

export function EvalResultCard({ result }: { result: FactorEvalResult | null | undefined }) {
  if (!result) {
    return (
      <Card size="small">
        <Space direction="vertical" size={2}>
          <Typography.Text strong>暂无评估结果</Typography.Text>
          <Typography.Text type="secondary">先选择因子并点击“评估因子”，系统会展示 IC、Walk-forward 和生产门槛。</Typography.Text>
        </Space>
      </Card>
    );
  }
  const items = [
    { label: "IC 均值", value: pct(result.ic_mean), tone: result.ic_mean > 0.03 ? "ok" : "warn" },
    { label: "ICIR", value: result.icir.toFixed(2), tone: result.icir > 0.4 ? "ok" : "warn" },
    { label: "OOS IC", value: pct(result.oos_ic_mean), tone: result.is_oos_consistent ? "ok" : "warn" },
    { label: "滚动 OOS", value: pct(result.walk_forward_oos_ic_mean ?? 0), tone: result.walk_forward_no_negative_windows ? "ok" : "warn" },
    { label: "Top20%收益", value: formatPct((result.top_quintile_return ?? 0) * 100), tone: result.top_quintile_return > 0.005 ? "ok" : "warn" },
    { label: "生产门槛", value: result.passed_production_gate ? "通过" : "未通过", tone: result.passed_production_gate ? "ok" : "bad" },
  ];
  return (
    <Card
      size="small"
      title="评估结果"
      extra={<Typography.Text type="secondary">样本 {result.observation_count} 条 · 交易日 {result.sample_days} 天 · Walk-forward {result.walk_forward_window_count ?? 0} 窗口</Typography.Text>}
    >
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <Row gutter={[8, 8]}>
        {items.map((item) => (
          <Col key={item.label} xs={12} md={8}>
            <Card size="small" styles={{ body: { padding: "8px 10px" } }}>
              <Statistic title={item.label} value={item.value} valueStyle={{ fontSize: 12, color: metricColor(item.tone) }} />
            </Card>
          </Col>
        ))}
        </Row>
        {result.warnings?.length ? (
          <Alert
            type="warning"
            showIcon
            message="评估提醒"
            description={<Space direction="vertical" size={2}>{result.warnings.map((warning) => <Typography.Text key={warning}>{warning}</Typography.Text>)}</Space>}
          />
        ) : <Tag color="green">未发现门槛警告</Tag>}
      </Space>
    </Card>
  );
}

function pct(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function metricColor(tone: string): string {
  if (tone === "ok") return "#178a5e";
  if (tone === "bad") return "#c34a36";
  return "#a16207";
}
