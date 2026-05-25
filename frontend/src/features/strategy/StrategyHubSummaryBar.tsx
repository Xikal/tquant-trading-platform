import { Button, Card, Col, Flex, Row, Space, Statistic, Tag, Typography, theme } from "antd";
import type { BacktestRunSummary } from "../../api/backtests";
import type { StrategyMeta } from "../../api/strategies";
import { formatDateTime, formatPct } from "../backtest/backtestDisplay";
import { latestFinishedRun, strategyDoctorVerdict, strategyHealthLabel } from "./strategyVerdict";

export function StrategyHubSummaryBar({
  runs,
  strategies,
  loading,
  onStartCheck,
}: {
  runs: BacktestRunSummary[];
  strategies: StrategyMeta[];
  loading: boolean;
  onStartCheck: () => void;
}) {
  const { token } = theme.useToken();
  const verdict = strategyDoctorVerdict(runs);
  const latestRun = latestFinishedRun(runs);
  const production = strategies.filter((item) => item.visibility === "full" && (item.tier === "core" || item.tier === "auxiliary"));
  const okCount = production.filter((item) => lightTone(item) === "ok").length;
  const warnCount = production.filter((item) => lightTone(item) === "warn").length;
  const badCount = production.filter((item) => lightTone(item) === "bad").length;

  return (
    <Card variant="borderless" styles={{ body: { display: "grid", gap: 10, padding: 16 } }}>
      <Flex gap={16} align="start" justify="space-between" wrap>
        <Space direction="vertical" size={2} style={{ minWidth: 0, flex: "1 1 420px" }}>
          <Typography.Text style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", color: token.colorTextSecondary }}>
            策略健康中心
          </Typography.Text>
          <Typography.Title level={1}>现在该不该继续用这些策略</Typography.Title>
          <Typography.Paragraph>{verdict.detail}</Typography.Paragraph>
          <Typography.Text type="secondary">{verdict.action}</Typography.Text>
        </Space>
        <Space direction="vertical" size={10} style={{ minWidth: 0, flex: "1 1 440px" }}>
          <Row gutter={[8, 8]}>
            <Col span={8}>
              <Card size="small" styles={{ body: { padding: 10 } }}>
                <Statistic title="当前结论" value={strategyHealthLabel(verdict.tone)} valueStyle={{ color: toneColor(verdict.tone, token) }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" styles={{ body: { padding: 10 } }}>
                <Statistic title="最近体检" value={latestRun ? formatDateTime(latestRun.created_at) : "暂无"} />
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" styles={{ body: { padding: 10 } }}>
                <Statistic title="最近胜率" value={latestRun?.summary?.win_rate_pct != null ? formatPct(latestRun.summary.win_rate_pct) : "--"} />
              </Card>
            </Col>
          </Row>
          <div>
            <Button type="primary" onClick={onStartCheck} disabled={loading}>
              {loading ? "提交中" : "开始策略体检"}
            </Button>
          </div>
          <Row gutter={[8, 8]}>
            <Col span={8}>
              <Card size="small" styles={{ body: { padding: 10 } }}>
                <Tag color="success" style={{ marginBottom: 6 }}>🟢 {okCount}</Tag>
                <div>可继续观察</div>
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" styles={{ body: { padding: 10 } }}>
                <Tag color="warning" style={{ marginBottom: 6 }}>🟡 {warnCount}</Tag>
                <div>小仓验证</div>
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" styles={{ body: { padding: 10 } }}>
                <Tag color="error" style={{ marginBottom: 6 }}>🔴 {badCount}</Tag>
                <div>建议暂停</div>
              </Card>
            </Col>
          </Row>
        </Space>
      </Flex>
      <Row gutter={[8, 8]}>
        {production.slice(0, 4).map((strategy) => {
          const tone = lightTone(strategy);
          return (
            <Col key={strategy.key} xs={24} sm={12} lg={6}>
              <Card size="small" styles={{ body: { padding: 10 } }}>
                <Space direction="vertical" size={2} style={{ display: "flex" }}>
                  <Typography.Text strong style={{ color: toneColor(tone, token) }}>{strategy.display_name || strategy.name}</Typography.Text>
                  <Typography.Text type="secondary">{strategyHint(strategy)}</Typography.Text>
                </Space>
              </Card>
            </Col>
          );
        })}
      </Row>
    </Card>
  );
}

function toneColor(tone: "ok" | "warn" | "bad" | "processing", token: ReturnType<typeof theme.useToken>["token"]) {
  if (tone === "ok") return token.colorSuccess;
  if (tone === "warn") return token.colorWarning;
  if (tone === "bad") return token.colorError;
  return token.colorPrimary;
}

function lightTone(strategy: StrategyMeta): "ok" | "warn" | "bad" {
  if (strategy.enabled === false) return "bad";
  if (strategy.probe_status === "failed" || strategy.probe_status === "rejected") return "bad";
  if (strategy.tier === "auxiliary" || strategy.probe_status === "pending") return "warn";
  return "ok";
}

function strategyHint(strategy: StrategyMeta): string {
  if (strategy.enabled === false) return "已停用，不建议继续使用";
  if (strategy.probe_status === "failed" || strategy.probe_status === "rejected") return "验证未通过，先排查原因";
  if (strategy.tier === "auxiliary" || strategy.probe_status === "pending") return "仍在小仓观察，暂不满仓";
  return "当前处于生产可用层";
}
