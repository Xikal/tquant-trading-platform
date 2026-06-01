import { Button } from "antd";
import type { BacktestExecutionModel, BacktestOptimizationCandidate } from "../../api/backtests";
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
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import {
  BACKTEST_MINI_METRICS_STYLE,
  BACKTEST_RESEARCH_CARD_STYLE,
  BACKTEST_RESEARCH_CARD_WIDE_STYLE,
  BACKTEST_RESEARCH_FORM_STYLE,
  BACKTEST_RESEARCH_NOTE_STYLE,
  BACKTEST_RESULT_BLOCK_STYLE,
  backtestToneTextStyle,
} from "./backtestResearchStyles";
import {
  BACKTEST_ADVANCED_FIELDS_STYLE,
  BACKTEST_ADVANCED_FIELDS_SUMMARY_STYLE,
  BACKTEST_ADVANCED_GRID_STYLE,
  BACKTEST_ERROR_STYLE,
} from "./backtestPageLayoutStyles";
import { combineBacktestStyles } from "./backtestStyles";

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
    <section style={combineBacktestStyles(BACKTEST_RESEARCH_CARD_STYLE, BACKTEST_RESEARCH_CARD_WIDE_STYLE)}>
      <PanelTitle title="自动找更稳参数" meta={`${state.optimizations.length} 条`} />
      <p style={BACKTEST_RESEARCH_NOTE_STYLE}>专家工具：体检结果有价值后再使用，用来寻找更稳的评分、仓位、止损和止盈组合。</p>
      <div style={BACKTEST_RESEARCH_FORM_STYLE}>
        <TextField label="名称" value={state.optimizationForm.name} onChange={(name) => actions.onOptimizationFormChange({ name })} />
        <SelectField label="策略" value={state.optimizationForm.strategy} options={strategyOptions} onChange={(strategy) => actions.onOptimizationFormChange({ strategy })} />
        <DateField label="训练开始" value={state.optimizationForm.train_start} onChange={(train_start) => actions.onOptimizationFormChange({ train_start })} />
        <DateField label="训练结束" value={state.optimizationForm.train_end} onChange={(train_end) => actions.onOptimizationFormChange({ train_end })} />
        <DateField label="验证开始" value={state.optimizationForm.test_start} onChange={(test_start) => actions.onOptimizationFormChange({ test_start })} />
        <DateField label="验证结束" value={state.optimizationForm.test_end} onChange={(test_end) => actions.onOptimizationFormChange({ test_end })} />
        <SelectField label="优化目标" value={state.optimizationForm.optimization_target} options={OPTIMIZATION_TARGET_OPTIONS} onChange={(optimization_target) => actions.onOptimizationFormChange({ optimization_target })} />
        <details style={BACKTEST_ADVANCED_FIELDS_STYLE}>
          <summary style={BACKTEST_ADVANCED_FIELDS_SUMMARY_STYLE}>高级设置（使用推荐值即可）</summary>
          <div style={BACKTEST_ADVANCED_GRID_STYLE}>
            <TextField type="number" label="初始资金" value={state.optimizationForm.initial_capital} onChange={(initial_capital) => actions.onOptimizationFormChange({ initial_capital })} />
            <SelectField label="执行模型" value={state.optimizationForm.execution_model} options={BACKTEST_EXECUTION_MODELS} onChange={(execution_model) => actions.onOptimizationFormChange({ execution_model: execution_model as BacktestExecutionModel })} />
            <SliderParamField label="最低评分" min={60} max={98} step={1} value={firstNumber(state.optimizationForm.min_score, 80)} onChange={(min_score) => actions.onOptimizationFormChange({ min_score: String(min_score) })} />
            <SliderParamField label="单票仓位上限" min={5} max={50} step={1} suffix="%" value={percentToSlider(state.optimizationForm.max_position_pct, 30)} onChange={(value) => actions.onOptimizationFormChange({ max_position_pct: ratioFromPercent(value) })} />
            <SliderParamField label="最大持有天数" min={1} max={10} step={1} value={firstNumber(state.optimizationForm.max_holding_days, 3)} onChange={(max_holding_days) => actions.onOptimizationFormChange({ max_holding_days: String(max_holding_days) })} />
            <SliderParamField label="止损线" min={2} max={12} step={0.5} suffix="%" value={Math.abs(percentToSlider(state.optimizationForm.stop_loss_pct, -5))} onChange={(value) => actions.onOptimizationFormChange({ stop_loss_pct: ratioFromPercent(-Math.abs(value)) })} />
            <SliderParamField label="止盈线" min={3} max={25} step={0.5} suffix="%" value={percentToSlider(state.optimizationForm.take_profit_pct, 10)} onChange={(value) => actions.onOptimizationFormChange({ take_profit_pct: ratioFromPercent(value) })} />
          </div>
        </details>
        <Button type="primary" onClick={actions.onSubmitOptimization} disabled={state.loading === "optimize-submit"}>
          {state.loading === "optimize-submit" ? "提交中..." : "提交优化"}
        </Button>
      </div>

      <TaskList
        items={state.optimizations}
        selectedId={state.selectedOptimizationId}
        onSelect={actions.onSelectOptimization}
        onCancel={actions.onCancelOptimization}
        onDelete={actions.onDeleteOptimization}
        formatStrategy={formatBacktestStrategy}
      />

      <div style={BACKTEST_RESULT_BLOCK_STYLE}>
        <PanelTitle title="参数排名" meta={detail ? `#${detail.id}` : "等待选择"} />
        {detail ? (
          <>
            {truthyFlag(detail.oos_downgrade) ? <div style={BACKTEST_ERROR_STYLE}>样本外降级：{detail.oos_downgrade_reason || "样本外表现低于阈值"}</div> : null}
            <div style={BACKTEST_MINI_METRICS_STYLE}>
              <Metric label="历史内评分" value={formatNumber(detail.best_is_score)} />
              <Metric label="样本外评分" value={formatNumber(detail.best_oos_score)} />
              <Metric label="最优参数" value={formatParams(detail.best_params)} />
            </div>
            <VirtualGrid<BacktestOptimizationCandidate>
              className="backtest-data-table"
              rowKey={(item, index) => `${item.rank ?? index}-${formatParams(item.params)}`}
              dataSource={detail.candidates ?? []}
              locale={{ emptyText: <Empty text="优化完成后显示参数组合排名。" /> }}
              scroll={{ x: 980 }}
              columns={[
                { title: "Rank", render: (_value, item, index) => item.rank ?? index + 1 },
                { title: "参数", render: (_value, item) => formatParams(item.params) },
                { title: "样本", render: (_value, item) => sampleScopeText(item.sample, item.is_oos) },
                { title: "收益", align: "right", render: (_value, item) => <span style={backtestToneTextStyle(toneFromNumber(item.total_return_pct))}>{formatPct(item.total_return_pct)}</span> },
                { title: "胜率", align: "right", render: (_value, item) => formatPct(item.win_rate_pct) },
                { title: "止损率", align: "right", render: (_value, item) => formatPct(item.stop_loss_rate_pct) },
                { title: "最大回撤", align: "right", render: (_value, item) => <span style={backtestToneTextStyle("down")}>{formatPct(item.max_drawdown_pct)}</span> },
                { title: "利润因子", align: "right", render: (_value, item) => formatNumber(item.profit_factor) },
                { title: "Sharpe", align: "right", render: (_value, item) => formatNumber(item.sharpe ?? item.sharpe_ratio) },
              ]}
            />
          </>
        ) : <Empty text="选择一条优化任务查看历史内/样本外对比和候选排名。" />}
      </div>
    </section>
  );
}

function sampleScopeText(sample?: string | null, isOos?: boolean | null): string {
  if (sample === "oos" || isOos) return "样本外";
  if (sample === "is") return "历史内";
  return sample || "历史内";
}
