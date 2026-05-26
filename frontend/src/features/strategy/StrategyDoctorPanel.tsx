import type { BacktestRunSummary } from "../../api/backtests";
import { Button, Card, Col, Flex, Row, Space, Statistic, Tag, Typography } from "antd";
import { formatBacktestStrategies, formatMoney, formatPct } from "../backtest/backtestDisplay";
import { strategyDoctorVerdict, strategyHealthLabel } from "./strategyVerdict";

export function StrategyDoctorPanel({
  runs,
  loading,
  onQuickCheck,
  onOpenSignals,
  onOpenCompare,
}: {
  runs: BacktestRunSummary[];
  loading: boolean;
  onQuickCheck: () => void;
  onOpenSignals: () => void;
  onOpenCompare: () => void;
}) {
  const verdict = strategyDoctorVerdict(runs);
  const run = verdict.run;
  const summary = run?.summary ?? {};
  const noCompletedTrades = isFinished(run?.status) && tradeCount(summary) === 0;
  return (
    <Card size="small" style={{ borderLeft: `6px solid ${toneColor(verdict.tone)}` }} aria-label="策略医生结论">
      <Space direction="vertical" size={14} style={{ width: "100%" }}>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} xl={9}>
            <Space direction="vertical" size={4}>
              <Tag color={toneTagColor(verdict.tone)}>策略医生</Tag>
              <Typography.Title level={3} style={{ margin: 0, fontSize: 12 }}>{strategyHealthLabel(verdict.tone)}</Typography.Title>
              <Typography.Text type="secondary">{verdict.detail}</Typography.Text>
              <Typography.Text strong style={{ color: toneColor(verdict.tone) }}>{verdict.action}</Typography.Text>
            </Space>
          </Col>
          <Col xs={24} xl={10}>
            <Row gutter={[8, 8]} aria-label="核心体检指标">
              <Col xs={12} md={6}><DoctorMetric label="收益" value={noCompletedTrades ? "无成交" : formatPct(summary.total_return_pct)} /></Col>
              <Col xs={12} md={6}><DoctorMetric label="胜率" value={noCompletedTrades ? "无成交" : formatPct(summary.win_rate_pct)} /></Col>
              <Col xs={12} md={6}><DoctorMetric label="最大回撤" value={formatPct(summary.max_drawdown_pct)} /></Col>
              <Col xs={12} md={6}><DoctorMetric label="样本" value={sampleText(tradeCount(summary))} /></Col>
            </Row>
          </Col>
          <Col xs={24} xl={5}>
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
              <Button block type="primary" onClick={onQuickCheck} loading={loading}>
                {loading ? "提交中" : "一键体检"}
              </Button>
              <Button block type="default" onClick={onOpenSignals}>看最近信号</Button>
              <Button block type="default" onClick={onOpenCompare}>比较策略</Button>
            </Space>
          </Col>
        </Row>
        {run ? (
          <Flex wrap gap={12} align="center">
            <Tag>最近体检</Tag>
            <Typography.Text type="secondary">{run.name || `任务 #${run.id}`}</Typography.Text>
            <Typography.Text type="secondary">{formatBacktestStrategies(run.strategies)}</Typography.Text>
            <Typography.Text type="secondary">资产 {formatMoney(run.final_equity)}</Typography.Text>
          </Flex>
        ) : null}
      </Space>
    </Card>
  );
}

function DoctorMetric({ label, value }: { label: string; value: string }) {
  return (
    <Card size="small" styles={{ body: { padding: "8px 10px" } }}>
      <Statistic title={label} value={value || "--"} styles={{ content: { fontSize: 12, fontWeight: 600, lineHeight: 1.15 } }} />
    </Card>
  );
}

function sampleText(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${value.toLocaleString("zh-CN")} 笔`;
}

function tradeCount(summary: { total_trades?: number | null; trade_count?: number | null }): number | null {
  const value = summary.total_trades ?? summary.trade_count;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isFinished(status?: string | null): boolean {
  return status === "completed" || status === "succeeded";
}

function toneColor(tone: string): string {
  if (tone === "good") return "#178a5e";
  if (tone === "bad") return "#c34a36";
  return "#a16207";
}

function toneTagColor(tone: string): string {
  if (tone === "good") return "green";
  if (tone === "bad") return "red";
  return "gold";
}
