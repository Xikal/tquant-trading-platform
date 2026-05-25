import { Button, Card, Flex, Space, Statistic, Typography, theme } from "antd";
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
    <Card variant="borderless" styles={{ body: { display: "grid", gap: 8, padding: 12 } }}>
      <Flex gap={10} align="center" justify="space-between" wrap>
        <Space orientation="vertical" size={1} style={{ minWidth: 0, flex: "1 1 280px" }}>
          <Typography.Text style={{ fontSize: 11, fontWeight: 700, color: token.colorTextSecondary }}>
            策略健康中心
          </Typography.Text>
          <Typography.Text strong style={{ fontSize: 16 }}>
            {strategyHealthLabel(verdict.tone)} · {verdict.action}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {verdict.detail}
          </Typography.Text>
        </Space>
        <Space size={8} wrap>
          <div style={{ ...SUMMARY_BOX_STYLE, minWidth: 126 }}>
            <Statistic title="最近体检" value={latestRun ? formatDateTime(latestRun.created_at) : "暂无"} />
          </div>
          <div style={{ ...SUMMARY_BOX_STYLE, minWidth: 126 }}>
            <Statistic title="最近胜率" value={latestRun?.summary?.win_rate_pct != null ? formatPct(latestRun.summary.win_rate_pct) : "--"} />
          </div>
          <Button type="primary" onClick={onStartCheck} disabled={loading}>
            {loading ? "提交中" : "体检"}
          </Button>
        </Space>
      </Flex>
      <Flex gap={8} wrap>
        <div style={COUNT_BOX_STYLE}>
          <Typography.Text type="secondary" style={{ fontSize: 11 }}>可用</Typography.Text>
          <div style={{ fontWeight: 700 }}>{okCount}</div>
        </div>
        <div style={COUNT_BOX_STYLE}>
          <Typography.Text type="secondary" style={{ fontSize: 11 }}>观察</Typography.Text>
          <div style={{ fontWeight: 700 }}>{warnCount}</div>
        </div>
        <div style={COUNT_BOX_STYLE}>
          <Typography.Text type="secondary" style={{ fontSize: 11 }}>暂停</Typography.Text>
          <div style={{ fontWeight: 700 }}>{badCount}</div>
        </div>
      </Flex>
    </Card>
  );
}

const SUMMARY_BOX_STYLE = {
  border: "1px solid #eef1f5",
  borderRadius: 8,
  padding: "8px 10px",
};

const COUNT_BOX_STYLE = {
  ...SUMMARY_BOX_STYLE,
  flex: "1 1 90px",
  padding: 8,
};

function lightTone(strategy: StrategyMeta): "ok" | "warn" | "bad" {
  if (strategy.enabled === false) return "bad";
  if (strategy.probe_status === "failed" || strategy.probe_status === "rejected") return "bad";
  if (strategy.tier === "auxiliary" || strategy.probe_status === "pending") return "warn";
  return "ok";
}
