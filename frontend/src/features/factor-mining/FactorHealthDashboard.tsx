import type { FactorHealthItem } from "../../api/factorMining";
import { Card, Col, Row, Space, Statistic, Tag, Typography } from "antd";

export function FactorHealthDashboard({ items }: { items: FactorHealthItem[] }) {
  const production = items.filter((item) => item.status === "production");
  const decaying = items.filter((item) => item.trend === "decaying");
  return (
    <Card size="small" title="生产因子健康" extra={<Typography.Text type="secondary">滚动 IC 趋势仅用于发现失效，不直接改变权重。</Typography.Text>}>
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <Row gutter={[8, 8]}>
          <Col xs={8}><Statistic title="生产因子" value={production.length} /></Col>
          <Col xs={8}><Statistic title="衰减提醒" value={decaying.length} /></Col>
          <Col xs={8}><Statistic title="最近评估" value={items.reduce((sum, item) => sum + (item.run_count || 0), 0)} /></Col>
        </Row>
        <Space direction="vertical" size={8} style={{ width: "100%", maxHeight: 360, overflowY: "auto" }}>
        {items.slice(0, 8).map((item) => (
          <Card key={item.factor_key} size="small">
            <Space direction="vertical" size={3} style={{ width: "100%" }}>
              <Space style={{ display: "flex", justifyContent: "space-between" }}>
                <Typography.Text strong>{item.name}</Typography.Text>
                <Tag color={trendColor(item.trend)}>{trendText(item.trend)}</Tag>
              </Space>
              <Typography.Text type="secondary">{item.factor_key}</Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                IC {(Number(item.ic_mean || 0) * 100).toFixed(2)}% · t {Number(item.ic_t_stat || 0).toFixed(2)}
              </Typography.Text>
            </Space>
          </Card>
        ))}
        </Space>
      </Space>
    </Card>
  );
}

function trendText(trend: string): string {
  if (trend === "improving") return "改善";
  if (trend === "decaying") return "衰减";
  return "稳定";
}

function trendColor(trend: string): string {
  if (trend === "improving") return "green";
  if (trend === "decaying") return "red";
  return "gold";
}
