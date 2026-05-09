import type { BacktestExecutionModel } from "../../api/backtests";
import {
  BACKTEST_EXECUTION_MODELS,
  OPTIMIZATION_TARGET_OPTIONS,
  formatBacktestStrategy,
  formatNumber,
  formatPct,
  toneFromNumber,
  type BacktestStrategyOption,
} from "./backtestDisplay";
import type { BacktestResearchActions, BacktestResearchState } from "./BacktestResearchPanel";
import {
  DateField,
  Empty,
  firstNumber,
  formatParams,
  Metric,
  PanelTitle,
  percentToSlider,
  ratioFromPercent,
  SelectField,
  SliderParamField,
  TaskList,
  TextField,
  truthyFlag,
} from "./BacktestResearchShared";

export function OptimizationPanel({
  state,
  actions,
  strategyOptions,
}: {
  state: BacktestResearchState;
  actions: BacktestResearchActions;
  strategyOptions: BacktestStrategyOption[];
}) {
  const detail = state.selectedOptimization;
  return (
    <section className="backtest-research-card span-2">
      <PanelTitle title="优化任务" meta={`${state.optimizations.length} 条`} />
      <div className="backtest-research-form compact">
        <TextField label="名称" value={state.optimizationForm.name} onChange={(name) => actions.onOptimizationFormChange({ name })} />
        <SelectField label="策略" value={state.optimizationForm.strategy} options={strategyOptions} onChange={(strategy) => actions.onOptimizationFormChange({ strategy })} />
        <DateField label="训练开始" value={state.optimizationForm.train_start} onChange={(train_start) => actions.onOptimizationFormChange({ train_start })} />
        <DateField label="训练结束" value={state.optimizationForm.train_end} onChange={(train_end) => actions.onOptimizationFormChange({ train_end })} />
        <DateField label="验证开始" value={state.optimizationForm.test_start} onChange={(test_start) => actions.onOptimizationFormChange({ test_start })} />
        <DateField label="验证结束" value={state.optimizationForm.test_end} onChange={(test_end) => actions.onOptimizationFormChange({ test_end })} />
        <SelectField label="优化目标" value={state.optimizationForm.optimization_target} options={OPTIMIZATION_TARGET_OPTIONS} onChange={(optimization_target) => actions.onOptimizationFormChange({ optimization_target })} />
        <details className="backtest-advanced-fields">
          <summary>高级设置（使用推荐值即可）</summary>
          <div className="backtest-advanced-grid">
            <TextField type="number" label="初始资金" value={state.optimizationForm.initial_capital} onChange={(initial_capital) => actions.onOptimizationFormChange({ initial_capital })} />
            <SelectField label="执行模型" value={state.optimizationForm.execution_model} options={BACKTEST_EXECUTION_MODELS} onChange={(execution_model) => actions.onOptimizationFormChange({ execution_model: execution_model as BacktestExecutionModel })} />
            <SliderParamField label="最低评分" min={60} max={98} step={1} value={firstNumber(state.optimizationForm.min_score, 80)} onChange={(min_score) => actions.onOptimizationFormChange({ min_score: String(min_score) })} />
            <SliderParamField label="单票仓位上限" min={5} max={50} step={1} suffix="%" value={percentToSlider(state.optimizationForm.max_position_pct, 30)} onChange={(value) => actions.onOptimizationFormChange({ max_position_pct: ratioFromPercent(value) })} />
            <SliderParamField label="最大持有天数" min={1} max={10} step={1} value={firstNumber(state.optimizationForm.max_holding_days, 3)} onChange={(max_holding_days) => actions.onOptimizationFormChange({ max_holding_days: String(max_holding_days) })} />
            <SliderParamField label="止损线" min={2} max={12} step={0.5} suffix="%" value={Math.abs(percentToSlider(state.optimizationForm.stop_loss_pct, -5))} onChange={(value) => actions.onOptimizationFormChange({ stop_loss_pct: ratioFromPercent(-Math.abs(value)) })} />
            <SliderParamField label="止盈线" min={3} max={25} step={0.5} suffix="%" value={percentToSlider(state.optimizationForm.take_profit_pct, 10)} onChange={(value) => actions.onOptimizationFormChange({ take_profit_pct: ratioFromPercent(value) })} />
          </div>
        </details>
        <button type="button" className="primary" onClick={actions.onSubmitOptimization} disabled={state.loading === "optimize-submit"}>
          {state.loading === "optimize-submit" ? "提交中..." : "提交优化"}
        </button>
      </div>

      <TaskList
        items={state.optimizations}
        selectedId={state.selectedOptimizationId}
        onSelect={actions.onSelectOptimization}
        onCancel={actions.onCancelOptimization}
        onDelete={actions.onDeleteOptimization}
        formatStrategy={formatBacktestStrategy}
      />

      <div className="backtest-result-block">
        <PanelTitle title="参数排名" meta={detail ? `#${detail.id}` : "等待选择"} />
        {detail ? (
          <>
            {truthyFlag(detail.oos_downgrade) ? <div className="backtest-error">OOS 降级：{detail.oos_downgrade_reason || "样本外表现低于阈值"}</div> : null}
            <div className="backtest-mini-metrics">
              <Metric label="IS Score" value={formatNumber(detail.best_is_score)} />
              <Metric label="OOS Score" value={formatNumber(detail.best_oos_score)} />
              <Metric label="最优参数" value={formatParams(detail.best_params)} />
            </div>
            <div className="backtest-data-table" role="table" aria-label="参数优化排名">
              <div className="row head" role="row">
                <span>Rank</span>
                <span>参数</span>
                <span>样本</span>
                <span>收益</span>
                <span>胜率</span>
                <span>止损率</span>
                <span>MaxDD</span>
                <span>PF</span>
                <span>Sharpe</span>
              </div>
              {(detail.candidates ?? []).slice(0, 8).map((item, index) => (
                <div className="row" role="row" key={`${item.rank ?? index}-${formatParams(item.params)}`}>
                  <span>{item.rank ?? index + 1}</span>
                  <span>{formatParams(item.params)}</span>
                  <span>{item.sample ?? (item.is_oos ? "oos" : "is")}</span>
                  <span className={toneFromNumber(item.total_return_pct)}>{formatPct(item.total_return_pct)}</span>
                  <span>{formatPct(item.win_rate_pct)}</span>
                  <span>{formatPct(item.stop_loss_rate_pct)}</span>
                  <span className="down">{formatPct(item.max_drawdown_pct)}</span>
                  <span>{formatNumber(item.profit_factor)}</span>
                  <span>{formatNumber(item.sharpe ?? item.sharpe_ratio)}</span>
                </div>
              ))}
              {detail.candidates?.length ? null : <Empty text="优化完成后显示参数组合排名。" />}
            </div>
          </>
        ) : <Empty text="选择一条优化任务查看 IS/OOS 对比和候选排名。" />}
      </div>
    </section>
  );
}
