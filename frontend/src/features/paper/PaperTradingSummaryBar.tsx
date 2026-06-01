import type { PaperAccount, PaperAutoTradingStatus, PaperPerformance } from "../../types";
import { Alert, Button, Card, Col, Flex, Row, Space, Statistic, Tag, theme } from "antd";
import { formatMoneyPlain, formatPct, toneFromChange } from "../workspace-shared/workspaceFormatters";
import { autoTradingSkipNotice, paperAccountNeedsResume, resolveAutoManagedStatus } from "./paperTradingStatus";
import { formatPaperDateTime } from "./paperTradingFormatters";

export function PaperTradingSummaryBar({
  account,
  performance,
  autoTradingStatus,
  loading,
  canOpenOrder,
  canResumeOrder,
  onOpenOrderEntry,
  onTogglePause,
}: {
  account: PaperAccount | null;
  performance: PaperPerformance | null;
  autoTradingStatus: PaperAutoTradingStatus | null;
  loading: boolean;
  canOpenOrder: boolean;
  canResumeOrder?: boolean;
  onOpenOrderEntry: () => void;
  onTogglePause?: () => void | Promise<void>;
}) {
  const { token } = theme.useToken();
  const status = resolveAutoManagedStatus(account, autoTradingStatus);
  const skipNotice = autoTradingSkipNotice(autoTradingStatus);
  const showResumeOrder = canResumeOrder ?? paperAccountNeedsResume(account, autoTradingStatus);
  const totalTone = toneFromChange(account?.total_return_pct);
  const dayTone = toneFromChange(account?.today_return_pct);

  const metrics = [
    { label: "总资产", value: formatMoneyPlain(account?.total_assets), tone: "neutral" },
    { label: "当日收益", value: formatPct(account?.today_return_pct), tone: dayTone },
    { label: "可用资金", value: formatMoneyPlain(account?.cash_available), tone: "neutral" },
    { label: "持仓市值", value: formatMoneyPlain(account?.market_value), tone: "neutral" },
    { label: "总收益率", value: formatPct(account?.total_return_pct), tone: totalTone },
    { label: "净胜率", value: formatPct(performance?.net_win_rate_pct), tone: toneFromChange(performance?.net_win_rate_pct) },
  ] as const;

  return (
    <Card className="panel" variant="borderless" style={{ gridArea: "summary" }} styles={{ body: { display: "grid", gap: 6, padding: 6, fontSize: 12 } }}>
      <Flex gap={8} align="start" justify="space-between" wrap style={{ minWidth: 0 }}>
        <Space direction="vertical" size={2} style={{ flex: "1 1 180px", minWidth: 0 }}>
          <Tag color={statusTagColor(status.tone)}> {status.label}</Tag>
          {autoTradingStatus?.last_cycle_at ? (
            <span style={{ color: token.colorTextSecondary, fontSize: 12 }}>最近刷新 {formatPaperDateTime(autoTradingStatus.last_cycle_at)}</span>
          ) : (
            <span style={{ color: token.colorTextSecondary, fontSize: 12 }}>交易时间内自动刷新</span>
          )}
        </Space>
        <Row gutter={[6, 6]} style={{ flex: "1 1 560px", minWidth: 0 }}>
          {metrics.map((item) => (
            <Col key={item.label} xs={12} sm={8} lg={4}>
              <Card size="small" styles={{ body: { padding: 6 } }}>
                <Statistic
                  title={item.label}
                  value={item.value}
                  styles={{ content: { color: metricColor(item.tone, token), fontSize: 12, lineHeight: 1.1 } }}
                />
              </Card>
            </Col>
          ))}
        </Row>
        <Space direction="vertical" size={5} style={{ flex: "0 0 auto" }}>
          <Button
            type="primary"
            size="small"
            disabled={!canOpenOrder || loading}
            onClick={onOpenOrderEntry}
          >
            {canOpenOrder ? "委托录入" : "自动交易中"}
          </Button>
          {showResumeOrder && onTogglePause ? (
            <Button type="default" size="small" disabled={loading} onClick={() => void onTogglePause()}>
              恢复委托
            </Button>
          ) : null}
        </Space>
      </Flex>
      {skipNotice ? (
        <Alert
          type={skipTone(skipNotice.tone)}
          showIcon
          message={skipNotice.title}
          description={
            <Flex gap={12} align="center" wrap justify="space-between">
              <span style={{ minWidth: 0, flex: "1 1 auto", fontSize: 12 }}>{skipNotice.text}</span>
              {skipNotice.time ? <span style={{ color: token.colorTextSecondary, fontSize: 12 }}>{formatPaperDateTime(skipNotice.time)}</span> : null}
            </Flex>
          }
        />
      ) : null}
    </Card>
  );
}

function metricColor(tone: string, token: ReturnType<typeof theme.useToken>["token"]) {
  if (tone === "up") return token.colorError;
  if (tone === "down") return token.colorSuccess;
  return token.colorText;
}

function statusTagColor(tone: string) {
  if (tone === "bad") return "error";
  if (tone === "warn") return "warning";
  return "success";
}

function skipTone(tone: string) {
  if (tone === "bad") return "error" as const;
  if (tone === "warn") return "warning" as const;
  return "info" as const;
}
