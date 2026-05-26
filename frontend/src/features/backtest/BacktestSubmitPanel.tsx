import { Alert, Button, Card, Checkbox, Form, Input, InputNumber, Segmented, Select, Space, Typography } from "antd";
import type { BacktestExecutionModel, BacktestResourceTier } from "../../api/backtests";
import {
  BACKTEST_EXECUTION_MODELS,
  BACKTEST_RESOURCE_TIER_OPTIONS,
  resourceTierHint,
} from "./backtestDisplay";
import type { BacktestFormState } from "./backtestForms";
import {
  BACKTEST_COMPACT_FORM_GRID_STYLE,
  BACKTEST_EXPERT_FIELDS_STYLE,
  BACKTEST_FORM_FULL_ROW_STYLE,
  BACKTEST_FORM_ITEM_STYLE,
  BACKTEST_FORM_STACK_STYLE,
  BACKTEST_HELP_STYLE,
  BACKTEST_LABEL_STYLE,
  BACKTEST_NUMBER_INPUT_STYLE,
  BACKTEST_NUMBER_SETTING_STYLE,
  BACKTEST_SEGMENTED_STYLE,
  BACKTEST_STRATEGY_ITEM_ACTIVE_STYLE,
  BACKTEST_STRATEGY_ITEM_STYLE,
  BACKTEST_STRATEGY_LIST_STYLE,
  BACKTEST_STRATEGY_TITLE_STYLE,
  BACKTEST_SUBMIT_BUTTON_STYLE,
} from "./backtestStyles";

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
      title="提交回测任务"
      extra={<Button size="small" onClick={onRefresh} disabled={loading === "list"}>刷新</Button>}
      variant="borderless"
      styles={{ body: { padding: 10 } }}
    >
      <Space direction="vertical" size={8} style={BACKTEST_FORM_STACK_STYLE}>
        {notice ? <Alert type="info" showIcon message={notice} /> : null}
        {error ? <Alert type="error" showIcon message="回测任务异常" description={error} /> : null}
        <Segmented
          block
          style={BACKTEST_SEGMENTED_STYLE}
          value={mode}
          onChange={(value) => onModeChange(value as BacktestMode)}
          options={[
            { label: "快速模式", value: "quick" },
            { label: "专家模式", value: "expert" },
          ]}
        />
        <Typography.Text type="secondary" style={BACKTEST_HELP_STYLE}>
          {mode === "quick"
            ? "只需要选择策略和日期，系统会用默认仓位、滑点和费用跑出结果。"
            : "专家模式可调整成交模型、仓位上限、现金保留和风控参数。"}
        </Typography.Text>
        <Form layout="vertical" component={false} requiredMark={false}>
          <div style={BACKTEST_COMPACT_FORM_GRID_STYLE}>
            <Form.Item label={<Typography.Text style={BACKTEST_LABEL_STYLE}>任务名称</Typography.Text>} style={BACKTEST_FORM_FULL_ROW_STYLE}>
              <Input value={form.name} onChange={(event) => onFormChange({ name: event.target.value })} />
            </Form.Item>
            <Form.Item label={<Typography.Text style={BACKTEST_LABEL_STYLE}>日期范围</Typography.Text>} style={BACKTEST_FORM_FULL_ROW_STYLE}>
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
            <Form.Item label={<Typography.Text style={BACKTEST_LABEL_STYLE}>策略多选</Typography.Text>} style={BACKTEST_FORM_FULL_ROW_STYLE}>
              <Space direction="vertical" size={8} style={BACKTEST_STRATEGY_LIST_STYLE}>
                {strategyOptions.map(([key, label]) => {
                  const checked = form.strategies.includes(key);
                  return (
                    <Checkbox
                      key={key}
                      checked={checked}
                      onChange={(event) => onFormChange({
                        strategies: event.target.checked
                          ? [...form.strategies, key]
                          : form.strategies.filter((item) => item !== key),
                      })}
                      style={{
                        ...BACKTEST_STRATEGY_ITEM_STYLE,
                        ...(checked ? BACKTEST_STRATEGY_ITEM_ACTIVE_STYLE : null),
                      }}
                    >
                      <span style={{ display: "grid", gap: 2 }}>
                        <strong style={BACKTEST_STRATEGY_TITLE_STYLE}>{label}</strong>
                      </span>
                    </Checkbox>
                  );
                })}
              </Space>
            </Form.Item>
            <Form.Item label={<Typography.Text style={BACKTEST_LABEL_STYLE}>初始资金</Typography.Text>} style={BACKTEST_FORM_ITEM_STYLE}>
              <InputNumber
                stringMode
                value={form.initial_capital}
                onChange={(value) => onFormChange({ initial_capital: String(value ?? "") })}
                min="0"
                style={BACKTEST_NUMBER_INPUT_STYLE}
              />
            </Form.Item>
            <Form.Item label={<Typography.Text style={BACKTEST_LABEL_STYLE}>基准指数</Typography.Text>} style={BACKTEST_FORM_ITEM_STYLE}>
              <Input value={form.benchmark} onChange={(event) => onFormChange({ benchmark: event.target.value })} />
            </Form.Item>
            <Form.Item label={<Typography.Text style={BACKTEST_LABEL_STYLE}>执行模型</Typography.Text>} style={BACKTEST_FORM_FULL_ROW_STYLE}>
              <Select
                value={form.execution_model}
                options={BACKTEST_EXECUTION_MODELS.map(([value, label]) => ({ value, label }))}
                onChange={(value) => onFormChange({ execution_model: value as BacktestExecutionModel })}
              />
            </Form.Item>
            {mode === "expert" ? (
              <>
                <Form.Item label={<Typography.Text style={BACKTEST_LABEL_STYLE}>资源等级</Typography.Text>} extra={resourceTierHint(form.resource_tier)} style={BACKTEST_FORM_FULL_ROW_STYLE}>
                  <Select
                    value={form.resource_tier}
                    options={BACKTEST_RESOURCE_TIER_OPTIONS.map(([value, label]) => ({ value, label }))}
                    onChange={(value) => onFormChange({ resource_tier: value as BacktestResourceTier })}
                  />
                </Form.Item>
                <div style={BACKTEST_EXPERT_FIELDS_STYLE}>
                  <NumberSetting label="单票仓位" suffix="%" value={form.max_position_pct} onChange={(value) => onFormChange({ max_position_pct: value })} />
                  <NumberSetting label="最大持仓数" value={form.max_positions} onChange={(value) => onFormChange({ max_positions: value })} />
                  <NumberSetting label="日亏损暂停" suffix="%" value={form.max_daily_loss_pct} onChange={(value) => onFormChange({ max_daily_loss_pct: value })} />
                  <NumberSetting label="单笔上限" suffix="%" value={form.max_single_order_pct} onChange={(value) => onFormChange({ max_single_order_pct: value })} />
                  <NumberSetting label="最低现金保留" value={form.min_cash_reserve} onChange={(value) => onFormChange({ min_cash_reserve: value })} />
                </div>
              </>
            ) : null}
            <Button
              type="primary"
              block
              onClick={onSubmit}
              loading={loading === "submit"}
              disabled={loading === "submit"}
              style={BACKTEST_SUBMIT_BUTTON_STYLE}
            >
              提交任务
            </Button>
          </div>
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
    <Form.Item label={<Typography.Text style={BACKTEST_LABEL_STYLE}>{label}</Typography.Text>} style={BACKTEST_NUMBER_SETTING_STYLE}>
      <InputNumber
        stringMode
        value={value}
        min="0"
        addonAfter={suffix}
        style={BACKTEST_NUMBER_INPUT_STYLE}
        onChange={(nextValue) => onChange(String(nextValue ?? ""))}
      />
    </Form.Item>
  );
}
