import { Alert, Button, Card, Col, Flex, Row, Space, Statistic, Typography } from "antd";

import type { PaperLedgerRepairResponse } from "../../types";
import { formatMoneyPlain, plainTradingText } from "../workspace-shared/workspaceFormatters";

interface PaperLedgerRepairPanelProps {
  loading: boolean;
  status: PaperLedgerRepairResponse | null;
  onRefresh: () => void;
  onApply: () => void;
}

export function PaperLedgerRepairPanel({
  loading,
  status,
  onRefresh,
  onApply,
}: PaperLedgerRepairPanelProps) {
  const issueCount = status?.issue_count ?? 0;
  const beforeGap = status?.reconciliation_gap_before ?? 0;
  const afterGap = status?.reconciliation_gap_after ?? 0;
  const actionDisabled = loading || issueCount <= 0;

  return (
    <Card
      title="账户对账修复"
      extra={<Typography.Text type="secondary">仅管理员可见。检查异常多卖、现金漂移或账本不平。</Typography.Text>}
      styles={{ body: { display: "flex", flexDirection: "column", gap: 12 } }}
    >
      <Row gutter={[8, 8]}>
        <SummaryItem label="当前差额" value={formatSignedMoney(beforeGap)} color={amountColor(beforeGap)} />
        <SummaryItem label="异常成交" value={`${issueCount} 条`} />
        <SummaryItem label="修复后差额" value={formatSignedMoney(afterGap)} color={amountColor(afterGap)} />
        <SummaryItem label="重算总资产" value={formatMoneyWithYuan(status?.corrected_total_assets)} />
      </Row>
      {status?.issues?.length ? (
        <Space direction="vertical" size={8}>
          {status.issues.slice(0, 5).map((item) => (
            <Alert
              key={`${item.trade_id}-${item.order_id}`}
              type="warning"
              showIcon
              message={`${item.symbol} ${item.side === "buy" ? "买入" : "卖出"}异常`}
              description={
                <Space direction="vertical" size={2}>
                  <Typography.Text>
                    原数量 {item.original_quantity} 股，保留 {item.valid_quantity} 股，剔除 {item.invalid_quantity} 股
                  </Typography.Text>
                  <Typography.Text type="secondary">{plainTradingText(item.reason)}</Typography.Text>
                </Space>
              }
            />
          ))}
        </Space>
      ) : (
        <Alert
          type="success"
          showIcon
          message="当前未发现异常成交记录"
          description="若顶部总盈亏与个股累计盈亏仍不一致，可点击“重新检查”再次校验。"
        />
      )}
      <Flex gap={10} justify="flex-end" wrap>
        <Button onClick={onRefresh} disabled={loading}>
          {loading ? "检查中..." : "重新检查"}
        </Button>
        <Button type="primary" onClick={onApply} disabled={actionDisabled}>
          {loading ? "重算中..." : issueCount > 0 ? "一键重算并修复" : "账本已平，无需修复"}
        </Button>
      </Flex>
    </Card>
  );
}

function SummaryItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Col xs={24} sm={12} lg={6}>
      <Card size="small">
        <Statistic title={label} value={value} valueStyle={color ? { color } : undefined} />
      </Card>
    </Col>
  );
}

function amountColor(value: number): string | undefined {
  if (value > 0) return "var(--price-up)";
  if (value < 0) return "var(--price-down)";
  return undefined;
}

function formatSignedMoney(value: number | null | undefined) {
  const amount = value ?? 0;
  const prefix = amount > 0 ? "+" : "";
  return `${prefix}${formatMoneyPlain(amount)}`;
}

function formatMoneyWithYuan(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "--";
  }
  return `¥${formatMoneyPlain(value)}`;
}
