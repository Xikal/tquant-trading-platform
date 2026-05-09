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
    <section className="backtest-research-card span-2">
      <PanelTitle title="Walk-forward 验证" meta={`${state.validations.length} 条`} />
      <div className="backtest-research-form compact">
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
        <details className="backtest-advanced-fields">
          <summary>高级设置（使用推荐值即可）</summary>
          <div className="backtest-advanced-grid compact">
            <TextField type="number" label="初始资金" value={state.validationForm.initial_capital} onChange={(initial_capital) => actions.onValidationFormChange({ initial_capital })} />
            <SelectField label="执行模型" value={state.validationForm.execution_model} options={BACKTEST_EXECUTION_MODELS} onChange={(execution_model) => actions.onValidationFormChange({ execution_model: execution_model as BacktestExecutionModel })} />
          </div>
        </details>
        <button type="button" className="primary" onClick={actions.onSubmitValidation} disabled={state.loading === "validate-submit"}>
          {state.loading === "validate-submit" ? "提交中..." : "提交验证"}
        </button>
      </div>

      <TaskList
        items={state.validations}
        selectedId={state.selectedValidationId}
        onSelect={actions.onSelectValidation}
        onCancel={actions.onCancelValidation}
        onDelete={actions.onDeleteValidation}
        formatStrategy={formatBacktestStrategy}
      />

      <div className="backtest-result-block">
        <PanelTitle title="PBO / 稳定性" meta={detail?.pbo_risk ? `PBO ${detail.pbo_risk}` : "等待结果"} />
        {detail ? (
          <>
            <div className="backtest-mini-metrics">
              <Metric label="OOS Sharpe" value={formatNumber(detail.avg_oos_sharpe)} />
              <Metric label="IS Sharpe" value={formatNumber(detail.avg_is_sharpe)} />
              <Metric label="样本外通过率" value={formatRatioPct(detail.oos_pass_rate)} />
              <Metric label="PBO" value={pboRiskMeta(detail.pbo_risk).label} className={`pbo-${pboRiskMeta(detail.pbo_risk).tone}`} />
            </div>
            {truthyFlag(detail.downgrade_review ?? detail.downgrade_review_required) ? <div className="backtest-error">存在样本外 Sharpe 小于 0 的窗口，建议进入降级复核。</div> : null}
            {detail.stability_conclusion ? <div className="backtest-research-note">{detail.stability_conclusion}</div> : null}
            <div className="backtest-window-grid">
              {(detail.windows ?? []).map((window, index) => (
                <article className="backtest-window-card" key={`${window.index ?? window.window_index ?? index}`}>
                  <strong>窗口 {window.index ?? window.window_index ?? index + 1}</strong>
                  <span>{window.train_start ?? "--"} → {window.train_end ?? "--"}</span>
                  <span>{window.test_start ?? "--"} → {window.test_end ?? "--"}</span>
                  <div>
                    <b>IS {formatNumber(window.train_sharpe ?? window.is_sharpe)}</b>
                    <b>OOS {formatNumber(window.test_sharpe ?? window.oos_sharpe)}</b>
                    <b>{formatPct(window.test_return_pct ?? window.oos_return_pct)}</b>
                  </div>
                  <small>{formatParams(window.best_params)}</small>
                </article>
              ))}
              {detail.windows?.length ? null : <Empty text="验证完成后显示滚动窗口结果。" />}
            </div>
          </>
        ) : <Empty text="选择一条验证任务查看 PBO、稳定性结论和窗口卡片。" />}
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
    <div className="backtest-window-presets">
      <span>验证窗口</span>
      <div>
        {presets.map((preset) => {
          const active = windowCount === preset.window_count && trainRatio === preset.train_ratio;
          return (
            <button
              key={preset.label}
              type="button"
              className={active ? "active" : ""}
              onClick={() => onChange({ window_count: preset.window_count, train_ratio: preset.train_ratio })}
            >
              <strong>{preset.label}</strong>
              <small>{preset.hint}</small>
            </button>
          );
        })}
      </div>
    </div>
  );
}
