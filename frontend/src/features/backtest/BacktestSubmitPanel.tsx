import { Alert, Button, Card, Checkbox, Form, Input, InputNumber, Segmented, Select, Space, Typography } from "antd";
import type { BacktestExecutionModel, BacktestResourceTier } from "../../api/backtests";
import {
  BACKTEST_EXECUTION_MODELS,
  BACKTEST_RESOURCE_TIER_OPTIONS,
  resourceTierHint,
} from "./backtestDisplay";
import type { BacktestFormState } from "./backtestForms";

type BacktestMode = "quick" | "expert";

interface BacktestSubmitPanelProps {
  form: BacktestFormState;
  loading: string;
  error: string;
  notice: string;
  mode: BacktestMode;
  strategyOptions: ReadonlyArray<readonly [string, string]>;
  onModeChange: (mode: BacktestMode) => void;
  onFormChange: (patch: Partial<BacktestFormState>) => void;
  onSubmit: () => void;
  onRefresh: () => void;
}

export function BacktestSubmitPanel({
  form,
  loading,
  error,
  notice,
  mode,
  strategyOptions,
  onModeChange,
  onFormChange,
  onSubmit,
  onRefresh,
}: BacktestSubmitPanelProps) {
  return (
    <Card
      className="backtest-submit"
      title="提交回测任务"
      extra={<Button size="small" onClick={onRefresh} disabled={loading === "list"}>刷新</Button>}
      variant="borderless"
    >
      <Space direction="vertical" size={12} className="backtest-ant-form">
        {notice ? <Alert type="info" showIcon message={notice} /> : null}
        {error ? <Alert type="error" showIcon message="回测任务异常" description={error} /> : null}
        <Segmented
          className="backtest-mode-segmented"
          block
          value={mode}
          onChange={(value) => onModeChange(value as BacktestMode)}
          options={[
            { label: "快速模式", value: "quick" },
            { label: "专家模式", value: "expert" },
          ]}
        />
        <Typography.Text type="secondary" className="backtest-helper">
          {mode === "quick"
            ? "只需要选择策略和日期，系统会用默认仓位、滑点和费用跑出结果。"
            : "专家模式可调整成交模型、仓位上限、现金保留和风控参数。"}
        </Typography.Text>
        <Form layout="vertical" component={false} requiredMark={false}>
          <Form.Item label="任务名称">
            <Input value={form.name} onChange={(event) => onFormChange({ name: event.target.value })} />
          </Form.Item>
          <Form.Item label="日期范围">
            <Space.Compact block>
              <Input
                type="date"
                aria-label="开始日期"
                value={form.start_date}
                onChange={(event) => onFormChange({ start_date: event.target.value })}
              />
              <Input
                type="date"
                aria-label="结束日期"
                value={form.end_date}
                onChange={(event) => onFormChange({ end_date: event.target.value })}
              />
            </Space.Compact>
          </Form.Item>
          <Form.Item label="策略多选">
            <Checkbox.Group
              className="backtest-strategy-checkboxes"
              value={form.strategies}
              onChange={(values) => onFormChange({ strategies: values.map(String) })}
              options={strategyOptions.map(([key, label]) => ({
                value: key,
                label: (
                  <span className="backtest-strategy-option">
                    <strong>{label}</strong>
                    <small>{key}</small>
                  </span>
                ),
              }))}
            />
          </Form.Item>
          <Form.Item label="初始资金">
            <InputNumber
              stringMode
              value={form.initial_capital}
              onChange={(value) => onFormChange({ initial_capital: String(value ?? "") })}
              min="0"
              className="full-width"
            />
          </Form.Item>
          <Form.Item label="基准指数">
            <Input value={form.benchmark} onChange={(event) => onFormChange({ benchmark: event.target.value })} />
          </Form.Item>
          <Form.Item label="执行模型">
            <Select
              value={form.execution_model}
              options={BACKTEST_EXECUTION_MODELS.map(([value, label]) => ({ value, label }))}
              onChange={(value) => onFormChange({ execution_model: value as BacktestExecutionModel })}
            />
          </Form.Item>
          {mode === "expert" ? (
            <>
              <Form.Item label="资源等级" extra={resourceTierHint(form.resource_tier)}>
                <Select
                  value={form.resource_tier}
                  options={BACKTEST_RESOURCE_TIER_OPTIONS.map(([value, label]) => ({ value, label }))}
                  onChange={(value) => onFormChange({ resource_tier: value as BacktestResourceTier })}
                />
              </Form.Item>
              <Space size={10} wrap className="backtest-expert-fields">
                <NumberSetting label="单票仓位" suffix="%" value={form.max_position_pct} onChange={(value) => onFormChange({ max_position_pct: value })} />
                <NumberSetting label="最大持仓数" value={form.max_positions} onChange={(value) => onFormChange({ max_positions: value })} />
                <NumberSetting label="日亏损暂停" suffix="%" value={form.max_daily_loss_pct} onChange={(value) => onFormChange({ max_daily_loss_pct: value })} />
                <NumberSetting label="单笔上限" suffix="%" value={form.max_single_order_pct} onChange={(value) => onFormChange({ max_single_order_pct: value })} />
                <NumberSetting label="最低现金保留" value={form.min_cash_reserve} onChange={(value) => onFormChange({ min_cash_reserve: value })} />
              </Space>
            </>
          ) : null}
          <Button
            className="backtest-submit-button"
            type="primary"
            block
            onClick={onSubmit}
            loading={loading === "submit"}
            disabled={loading === "submit"}
          >
            提交任务
          </Button>
        </Form>
      </Space>
    </Card>
  );
}

function NumberSetting({
  label,
  suffix,
  value,
  onChange,
}: {
  label: string;
  suffix?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Form.Item label={label} className="backtest-number-setting">
      <InputNumber
        stringMode
        value={value}
        min="0"
        addonAfter={suffix}
        onChange={(nextValue) => onChange(String(nextValue ?? ""))}
      />
    </Form.Item>
  );
}
