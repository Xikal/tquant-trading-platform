import { Button, Checkbox } from "antd";
import type { BacktestExecutionModel } from "../../api/backtests";
import {
  BACKTEST_EXECUTION_MODELS,
  OPTIMIZATION_TARGET_OPTIONS,
  formatNumber,
  formatPct,
  formatRatioPct,
  pboRiskMeta,
  type BacktestStrategyOption,
} from "./backtestDisplay";
import type { BacktestResearchActions, BacktestResearchState, ValidationFormState } from "./BacktestResearchPanel";
import {
  DateField,
  Empty,
  formatParams,
  Metric,
  PanelTitle,
  SelectField,
  TaskList,
  TextField,
  truthyFlag,
} from "./BacktestResearchShared";
import { formatBacktestStrategy } from "./backtestDisplay";
import {
  BACKTEST_MINI_METRICS_STYLE,
  BACKTEST_RESEARCH_CARD_STYLE,
  BACKTEST_RESEARCH_CARD_WIDE_STYLE,
  BACKTEST_RESEARCH_FORM_STYLE,
  BACKTEST_RESEARCH_NOTE_STYLE,
  BACKTEST_RESULT_BLOCK_STYLE,
  BACKTEST_WINDOW_CARD_BADGE_ROW_STYLE,
  BACKTEST_WINDOW_CARD_BADGE_STYLE,
  BACKTEST_WINDOW_CARD_META_STYLE,
  BACKTEST_WINDOW_CARD_STYLE,
  BACKTEST_WINDOW_PRESET_BUTTON_STYLE,
  BACKTEST_WINDOW_PRESET_GRID_STYLE,
  BACKTEST_WINDOW_PRESET_HINT_STYLE,
  BACKTEST_WINDOW_PRESET_LABEL_STYLE,
  BACKTEST_WINDOW_PRESET_TEXT_STYLE,
  BACKTEST_WINDOW_PRESETS_STYLE,
  BACKTEST_WINDOW_GRID_STYLE,
} from "./backtestResearchStyles";
import {
  BACKTEST_ADVANCED_FIELDS_STYLE,
  BACKTEST_ADVANCED_FIELDS_SUMMARY_STYLE,
  BACKTEST_ADVANCED_GRID_COMPACT_STYLE,
  BACKTEST_ERROR_STYLE,
} from "./backtestPageLayoutStyles";
import { combineBacktestStyles } from "./backtestStyles";

export function ValidationPanel({
  state,
  actions,
  strategyOptions,
}: {
  state: BacktestResearchState;
  actions: BacktestResearchActions;
  strategyOptions: BacktestStrategyOption[];
}) {
  const detail = state.selectedValidation;
  return (
    <section style={combineBacktestStyles(BACKTEST_RESEARCH_CARD_STYLE, BACKTEST_RESEARCH_CARD_WIDE_STYLE)}>
      <PanelTitle title="防过拟合检查" meta={`${state.validations.length} 条`} />
      <p style={BACKTEST_RESEARCH_NOTE_STYLE}>专家工具：检查策略是不是只在历史里好看。样本外不通过，就不要进入生产或自动交易。</p>
      <div style={BACKTEST_RESEARCH_FORM_STYLE}>
        <TextField label="名称" value={state.validationForm.name} onChange={(name) => actions.onValidationFormChange({ name })} />
        <SelectField label="策略" value={state.validationForm.strategy} options={strategyOptions} onChange={(strategy) => actions.onValidationFormChange({ strategy })} />
        <DateField label="开始日期" value={state.validationForm.start_date} onChange={(start_date) => actions.onValidationFormChange({ start_date })} />
        <DateField label="结束日期" value={state.validationForm.end_date} onChange={(end_date) => actions.onValidationFormChange({ end_date })} />
        <WindowPresetPicker
          windowCount={state.validationForm.window_count}
          trainRatio={state.validationForm.train_ratio}
          onChange={(patch) => actions.onValidationFormChange(patch)}
        />
        <SelectField label="优化目标" value={state.validationForm.optimization_target} options={OPTIMIZATION_TARGET_OPTIONS} onChange={(optimization_target) => actions.onValidationFormChange({ optimization_target })} />
        <details style={BACKTEST_ADVANCED_FIELDS_STYLE}>
          <summary style={BACKTEST_ADVANCED_FIELDS_SUMMARY_STYLE}>高级设置（使用推荐值即可）</summary>
          <div style={BACKTEST_ADVANCED_GRID_COMPACT_STYLE}>
            <TextField type="number" label="初始资金" value={state.validationForm.initial_capital} onChange={(initial_capital) => actions.onValidationFormChange({ initial_capital })} />
            <SelectField label="执行模型" value={state.validationForm.execution_model} options={BACKTEST_EXECUTION_MODELS} onChange={(execution_model) => actions.onValidationFormChange({ execution_model: execution_model as BacktestExecutionModel })} />
            <Checkbox
                checked={Boolean(state.validationForm.auto_promote_state_params)}
              onChange={(event) => actions.onValidationFormChange({ auto_promote_state_params: event.target.checked })}
            >
              验证通过后自动生成市场状态参数版本
            </Checkbox>
          </div>
        </details>
        <Button type="primary" onClick={actions.onSubmitValidation} disabled={state.loading === "validate-submit"}>
          {state.loading === "validate-submit" ? "提交中..." : "提交验证"}
        </Button>
      </div>

      <TaskList
        items={state.validations}
        selectedId={state.selectedValidationId}
        onSelect={actions.onSelectValidation}
        onCancel={actions.onCancelValidation}
        onDelete={actions.onDeleteValidation}
        formatStrategy={formatBacktestStrategy}
      />

      <div style={BACKTEST_RESULT_BLOCK_STYLE}>
        <PanelTitle title="过拟合风险 / 稳定性" meta={detail?.pbo_risk ? pboRiskMeta(detail.pbo_risk).label : "等待结果"} />
        {detail ? (
          <>
            <div style={BACKTEST_MINI_METRICS_STYLE}>
              <Metric label="样本外表现" value={formatNumber(detail.avg_oos_sharpe)} />
              <Metric label="历史内表现" value={formatNumber(detail.avg_is_sharpe)} />
              <Metric label="样本外通过率" value={formatRatioPct(detail.oos_pass_rate)} />
              <Metric label="过拟合风险" value={pboRiskMeta(detail.pbo_risk).label} className={`pbo-${pboRiskMeta(detail.pbo_risk).tone}`} />
            </div>
            {truthyFlag(detail.downgrade_review ?? detail.downgrade_review_required) ? <div style={BACKTEST_ERROR_STYLE}>存在样本外 Sharpe 小于 0 的窗口，建议进入降级复核。</div> : null}
            {detail.stability_conclusion ? <div style={BACKTEST_RESEARCH_NOTE_STYLE}>{detail.stability_conclusion}</div> : null}
            <Button
              onClick={() => actions.onPromoteValidationStateParams(detail.id)}
              disabled={state.loading === "validation-promote" || detail.status !== "succeeded"}
            >
              {state.loading === "validation-promote" ? "晋级中..." : "生成市场状态参数版本（专家）"}
            </Button>
            <div style={BACKTEST_WINDOW_GRID_STYLE}>
              {(detail.windows ?? []).map((window, index) => (
                <article style={BACKTEST_WINDOW_CARD_STYLE} key={`${window.index ?? window.window_index ?? index}`}>
                  <strong>窗口 {window.index ?? window.window_index ?? index + 1}</strong>
                  <span style={BACKTEST_WINDOW_CARD_META_STYLE}>{window.train_start ?? "--"} → {window.train_end ?? "--"}</span>
                  <span style={BACKTEST_WINDOW_CARD_META_STYLE}>{window.test_start ?? "--"} → {window.test_end ?? "--"}</span>
                  <div style={BACKTEST_WINDOW_CARD_BADGE_ROW_STYLE}>
                    <b style={BACKTEST_WINDOW_CARD_BADGE_STYLE}>历史内 {formatNumber(window.train_sharpe ?? window.is_sharpe)}</b>
                    <b style={BACKTEST_WINDOW_CARD_BADGE_STYLE}>样本外 {formatNumber(window.test_sharpe ?? window.oos_sharpe)}</b>
                    <b style={BACKTEST_WINDOW_CARD_BADGE_STYLE}>{formatPct(window.test_return_pct ?? window.oos_return_pct)}</b>
                  </div>
                  <small style={BACKTEST_WINDOW_CARD_META_STYLE}>{formatParams(window.best_params)}</small>
                </article>
              ))}
              {detail.windows?.length ? null : <Empty text="验证完成后显示滚动窗口结果。" />}
            </div>
          </>
        ) : <Empty text="选择一条验证任务查看过拟合风险、稳定性结论和窗口卡片。" />}
      </div>
    </section>
  );
}

function WindowPresetPicker({
  windowCount,
  trainRatio,
  onChange,
}: {
  windowCount: string;
  trainRatio: string;
  onChange: (patch: Pick<ValidationFormState, "window_count" | "train_ratio">) => void;
}) {
  const presets = [
    { label: "稳健", hint: "4 窗口 · 75% 训练", window_count: "4", train_ratio: "0.75" },
    { label: "滚动", hint: "6 窗口 · 70% 训练", window_count: "6", train_ratio: "0.70" },
    { label: "严检", hint: "8 窗口 · 65% 训练", window_count: "8", train_ratio: "0.65" },
  ];
  return (
    <div style={BACKTEST_WINDOW_PRESETS_STYLE}>
      <span style={BACKTEST_WINDOW_PRESET_LABEL_STYLE}>验证窗口</span>
      <div style={BACKTEST_WINDOW_PRESET_GRID_STYLE}>
        {presets.map((preset) => {
          const active = windowCount === preset.window_count && trainRatio === preset.train_ratio;
          return (
            <Button
              key={preset.label}
              type={active ? "primary" : "default"}
              onClick={() => onChange({ window_count: preset.window_count, train_ratio: preset.train_ratio })}
              style={BACKTEST_WINDOW_PRESET_BUTTON_STYLE}
            >
              <strong style={BACKTEST_WINDOW_PRESET_TEXT_STYLE}>{preset.label}</strong>
              <small style={BACKTEST_WINDOW_PRESET_HINT_STYLE}>{preset.hint}</small>
            </Button>
          );
        })}
      </div>
    </div>
  );
}
