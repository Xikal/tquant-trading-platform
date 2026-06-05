import { Alert, Button, Checkbox, Form, Input, Select, Space } from "antd";
import type { TradeJournalEntryCreate } from "../../types";

const ACTION_OPTIONS = [
  { label: "建仓记录", value: "buy" },
  { label: "退出记录", value: "sell" },
  { label: "减量记录", value: "trim" },
  { label: "仓位变化记录", value: "add" },
  { label: "T 记录", value: "t_trade" },
  { label: "备注", value: "note" },
];

const DISCIPLINE_OPTIONS = [
  { label: "顺势", value: "trend_follow" },
  { label: "防守线已设", value: "stop_loss_set" },
  { label: "下行不扩张", value: "no_add_down" },
  { label: "不追流动性弱", value: "no_chase_noliquidity" },
  { label: "不逆主线", value: "not_against_mainline" },
  { label: "仓位有计划", value: "planned_position" },
];

const MISTAKE_OPTIONS = [
  { label: "计划滞后", value: "late_plan" },
  { label: "情绪波动", value: "emotional" },
  { label: "未等确认", value: "early_action" },
  { label: "纪律遗漏", value: "discipline_miss" },
];

export function TradeJournalQuickEntry({
  accountId,
  onSubmit,
  submitting,
  errorText,
  initialSymbol = "",
  initialReasonText = "",
  initialSignalSource = "manual_review",
}: {
  accountId?: number | null;
  onSubmit: (payload: TradeJournalEntryCreate) => void;
  submitting: boolean;
  errorText?: string;
  initialSymbol?: string;
  initialReasonText?: string;
  initialSignalSource?: string;
}) {
  return (
    <Form
      className="trade-journal-quick-entry"
      layout="vertical"
      initialValues={{
        symbol: initialSymbol,
        action: "note",
        reason_text: initialReasonText,
        discipline_keys: [],
        mistake_tags: [],
      }}
      onFinish={(values) => {
        const disciplineKeys = Array.isArray(values.discipline_keys) ? values.discipline_keys : [];
        onSubmit({
          account_id: accountId ?? undefined,
          symbol: String(values.symbol || "").trim(),
          action: values.action || "note",
          reason_text: String(values.reason_text || "").trim(),
          signal_source: initialSignalSource,
          discipline_flags: Object.fromEntries(DISCIPLINE_OPTIONS.map((item) => [item.value, disciplineKeys.includes(item.value)])),
          mistake_tags: Array.isArray(values.mistake_tags) ? values.mistake_tags : [],
        });
      }}
    >
      {errorText ? <Alert type="error" showIcon message={errorText} /> : null}
      <Space align="start" wrap>
        <Form.Item name="symbol" label="代码" rules={[{ required: true, message: "请填写代码" }]}>
          <Input className="trade-journal-code-input" placeholder="600000" />
        </Form.Item>
        <Form.Item name="action" label="记录类型">
          <Select className="trade-journal-action-select" options={ACTION_OPTIONS} />
        </Form.Item>
        <Form.Item name="reason_text" label="复盘理由">
          <Input.TextArea className="trade-journal-reason-input" autoSize={{ minRows: 1, maxRows: 3 }} placeholder="记录当时依据和纪律状态" />
        </Form.Item>
      </Space>
      <Form.Item name="discipline_keys" label="纪律项">
        <Checkbox.Group options={DISCIPLINE_OPTIONS} />
      </Form.Item>
      <Form.Item name="mistake_tags" label="复盘标签">
        <Checkbox.Group options={MISTAKE_OPTIONS} />
      </Form.Item>
      <Button type="primary" htmlType="submit" loading={submitting}>保存记录</Button>
    </Form>
  );
}
