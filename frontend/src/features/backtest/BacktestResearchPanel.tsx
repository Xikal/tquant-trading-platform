import type {
  BacktestAttributionResponse,
  BacktestCompareResponse,
  BacktestExecutionModel,
  EquityPoint,
  BacktestMonthlyReturnsResponse,
  BacktestOptimizationDetail,
  BacktestOptimizationSummary,
  BacktestParamValue,
  BacktestRunSummary,
  BacktestStrategyCorrelationResponse,
  BacktestValidationDetail,
  BacktestValidationSummary,
} from "../../api/backtests";
import { mlSignalsApi, type MLSignalOnlineLearningStatus, type StrategyCapacityResponse } from "../../api/mlSignals";
import type { ReactNode } from "react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { ErrorBanner } from "../../components/shared/Feedback";
import {
  DateField as SharedDateField,
  SelectField as SharedSelectField,
  SliderField as SharedSliderField,
  TextField as SharedTextField,
} from "../../components/shared/FormFields";
import {
  BACKTEST_EXECUTION_MODELS,
  OPTIMIZATION_TARGET_OPTIONS,
  type BacktestStrategyOption,
  formatBacktestStrategy,
  formatInteger,
  formatMoneyOrPct,
  formatNumber,
  formatPct,
  formatRatioPct,
  pboRiskMeta,
  toneFromNumber,
} from "./backtestDisplay";
import { useBacktestStrategyOptions } from "./useBacktestStrategyOptions";

const LazyBacktestCompareChart = lazy(() => import("./LazyBacktestCompareChart"));
const LazyBacktestMonthlyHeatmap = lazy(() => import("./LazyBacktestMonthlyHeatmap"));
const LazyBacktestReturnDistribution = lazy(() => import("./LazyBacktestReturnDistribution"));

export interface OptimizationFormState {
  name: string;
  strategy: string;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  initial_capital: string;
  execution_model: BacktestExecutionModel;
  optimization_target: string;
  min_score: string;
  max_position_pct: string;
  max_holding_days: string;
  stop_loss_pct: string;
  take_profit_pct: string;
}

export interface ValidationFormState {
  name: string;
  strategy: string;
  start_date: string;
  end_date: string;
  window_count: string;
  train_ratio: string;
  initial_capital: string;
  execution_model: BacktestExecutionModel;
  optimization_target: string;
}

export interface BacktestResearchState {
  optimizationForm: OptimizationFormState;
  optimizations: BacktestOptimizationSummary[];
  selectedOptimizationId: number | null;
  selectedOptimization: BacktestOptimizationDetail | null;
  validationForm: ValidationFormState;
  validations: BacktestValidationSummary[];
  selectedValidationId: number | null;
  selectedValidation: BacktestValidationDetail | null;
  completedRuns: BacktestRunSummary[];
  compareRunIds: string;
  compareResult: BacktestCompareResponse | null;
  monthlyReturns: BacktestMonthlyReturnsResponse | null;
  attribution: BacktestAttributionResponse | null;
  correlation: BacktestStrategyCorrelationResponse | null;
  loading: string;
  error: string;
  notice: string;
}

export interface BacktestResearchActions {
  onOptimizationFormChange: (patch: Partial<OptimizationFormState>) => void;
  onSubmitOptimization: () => void;
  onSelectOptimization: (optimizationId: number) => void;
  onCancelOptimization: (optimizationId: number) => void;
  onDeleteOptimization: (optimizationId: number) => void;
  onValidationFormChange: (patch: Partial<ValidationFormState>) => void;
  onSubmitValidation: () => void;
  onSelectValidation: (validationId: number) => void;
  onCancelValidation: (validationId: number) => void;
  onDeleteValidation: (validationId: number) => void;
  onCompareRunIdsChange: (value: string) => void;
  onRunCompare: () => void;
  onRefreshResearch: () => void;
}

export type BacktestResearchSection = "optimization" | "validation" | "compare" | "attribution" | "capacity";

export function BacktestResearchPanel({
  state,
  actions,
  sections,
  equity = [],
}: {
  state: BacktestResearchState;
  actions: BacktestResearchActions;
  sections?: BacktestResearchSection[];
  equity?: EquityPoint[];
}) {
  const strategyOptions = useBacktestStrategyOptions();
  const visibleSections = new Set<BacktestResearchSection>(
    sections ?? ["optimization", "validation", "compare", "attribution", "capacity"]
  );
  const focused = Boolean(sections?.length === 1);
  return (
    <section className={`panel backtest-research${focused ? " focused" : ""}`}>
      <div className="backtest-research-hero">
        <div>
          <span className="backtest-kicker">Research Loop · Phase2</span>
          <h2>回测研究闭环</h2>
          <p>按“优化参数 → 样本外验证 → 多任务对比 → 归因复盘”使用。优先看收益、胜率、最大回撤和样本外通过率。</p>
        </div>
        <button type="button" onClick={actions.onRefreshResearch} disabled={state.loading === "research"}>
          {state.loading === "research" ? "刷新中..." : "刷新研究任务"}
        </button>
      </div>

      {state.notice ? <div className="backtest-notice">{state.notice}</div> : null}
      {state.error ? <ErrorBanner message={state.error} onRetry={actions.onRefreshResearch} /> : null}

      <div className="backtest-research-grid">
        {visibleSections.has("optimization") ? <OptimizationPanel state={state} actions={actions} strategyOptions={strategyOptions} /> : null}
        {visibleSections.has("validation") ? <ValidationPanel state={state} actions={actions} strategyOptions={strategyOptions} /> : null}
        {visibleSections.has("compare") ? <ComparePanel state={state} actions={actions} /> : null}
        {visibleSections.has("attribution") ? <AttributionPanel state={state} equity={equity ?? []} /> : null}
        {visibleSections.has("capacity") ? <MLCapacityPanel strategyOptions={strategyOptions} /> : null}
      </div>
    </section>
  );
}

function MLCapacityPanel({ strategyOptions }: { strategyOptions: BacktestStrategyOption[] }) {
  const defaultStrategies = strategyOptions.slice(0, 2).map(([key]) => key).join(",");
  const [status, setStatus] = useState<MLSignalOnlineLearningStatus | null>(null);
  const [capacity, setCapacity] = useState<StrategyCapacityResponse | null>(null);
  const [strategies, setStrategies] = useState(defaultStrategies || "first_board,volume_shrink");
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  const selectedStrategies = useMemo(
    () => strategies.split(",").map((item) => item.trim()).filter(Boolean),
    [strategies],
  );

  const loadStatus = async () => {
    setLoading("status");
    setError("");
    try {
      setStatus(await mlSignalsApi.getOnlineLearningStatus(100));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading("");
    }
  };

  const runCapacity = async () => {
    setLoading("capacity");
    setError("");
    try {
      setCapacity(await mlSignalsApi.evaluateCapacity({
        strategies: selectedStrategies,
        capital_levels: [500000, 1000000, 5000000],
      }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading("");
    }
  };

  const runIncrementalTrain = async () => {
    setLoading("train");
    setError("");
    try {
      await mlSignalsApi.incrementalTrain({ model_type: "logistic", min_samples: 100, promote: false });
      await loadStatus();
    } catch (err) {
      setError(errorMessage(err));
      setLoading("");
    }
  };

  useEffect(() => {
    void loadStatus();
  }, []);

  return (
    <section className="backtest-research-card span-2">
      <PanelTitle title="ML 在线学习 / 策略容量" meta="模拟盘闭环 + 资金容量" />
      {error ? <div className="backtest-error">{error}</div> : null}
      <div className="backtest-mini-metrics">
        <Metric label="Paper 样本" value={formatInteger(status?.paper_sample_count)} />
        <Metric label="平仓样本" value={formatInteger(status?.closed_trade_sample_count)} />
        <Metric label="正/负样本" value={`${formatInteger(status?.positive_sample_count)} / ${formatInteger(status?.negative_sample_count)}`} />
        <Metric label="训练状态" value={status?.ready_for_training ? "可训练" : "样本不足"} className={status?.ready_for_training ? "pbo-low" : "pbo-medium"} />
      </div>
      <div className="backtest-research-note">
        {status?.next_training_rule ?? "每周一 16:00 后自动触发增量训练；模型仍受样本量、AUC、K-fold 和生产门槛限制。"}
        {status?.latest_incremental_task_id ? ` 最近任务 #${status.latest_incremental_task_id}：${status.latest_incremental_task_status || "--"}。` : ""}
        {status?.production_model_key ? ` 当前生产模型：${status.production_model_key}。` : " 暂无生产模型。"}
      </div>
      {status?.warnings?.length ? (
        <div className="backtest-warning-list">
          {status.warnings.slice(0, 3).map((item) => <span key={item}>{item}</span>)}
        </div>
      ) : null}
      <div className="backtest-capacity-controls">
        <TextField label="容量评估策略" value={strategies} hint="英文逗号分隔" onChange={setStrategies} />
        <button type="button" onClick={loadStatus} disabled={loading === "status"}>{loading === "status" ? "刷新中..." : "刷新 ML 状态"}</button>
        <button type="button" onClick={runCapacity} disabled={loading === "capacity" || !selectedStrategies.length}>{loading === "capacity" ? "评估中..." : "评估容量"}</button>
        <button type="button" className="secondary" onClick={runIncrementalTrain} disabled={loading === "train"}>{loading === "train" ? "训练中..." : "手动增量训练"}</button>
      </div>
      <div className="backtest-data-table capacity" role="table" aria-label="策略容量评估">
        <div className="row head" role="row">
          <span>策略</span>
          <span>样本</span>
          <span>成交额</span>
          <span>50万</span>
          <span>100万</span>
          <span>500万</span>
          <span>提示</span>
        </div>
        {(capacity?.items ?? []).map((item) => (
          <div className="row" role="row" key={item.strategy_key}>
            <span>{formatBacktestStrategy(item.strategy_key)}</span>
            <span>{formatInteger(item.sample_count)} / {formatInteger(item.symbol_count)}</span>
            <span>{formatMoneyCompact(item.avg_daily_amount)}</span>
            {item.curve.slice(0, 3).map((point) => (
              <span className={capacityTone(point.capacity_status)} key={`${item.strategy_key}-${point.capital}`}>
                {point.capacity_status} · {formatPct(point.net_edge_pct)}
              </span>
            ))}
            <span>{item.notes?.[0] || "容量评估完成"}</span>
          </div>
        ))}
        {capacity?.items?.length ? null : <Empty text="点击“评估容量”后显示 Kyle Lambda 与资金冲击曲线。" />}
      </div>
    </section>
  );
}

function OptimizationPanel({
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

function ValidationPanel({
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

function ComparePanel({ state, actions }: { state: BacktestResearchState; actions: BacktestResearchActions }) {
  const [sortKey, setSortKey] = useState<"return" | "sharpe" | "drawdown">("return");
  const selectedRunIds = parseRunIdsLoose(state.compareRunIds);
  const compareItems = useMemo(
    () => sortCompareItems(state.compareResult?.items ?? [], sortKey),
    [state.compareResult?.items, sortKey],
  );
  const toggleRunId = (runId: number) => {
    const next = selectedRunIds.includes(runId)
      ? selectedRunIds.filter((item) => item !== runId)
      : [...selectedRunIds, runId];
    actions.onCompareRunIdsChange(next.join(","));
  };
  return (
    <section className="backtest-research-card">
      <PanelTitle title="回测对比" meta="复选运行 + 可排序指标 + ECharts" />
      <div className="backtest-run-picker" aria-label="已完成回测快捷选择">
        {state.completedRuns.slice(0, 8).map((run) => (
          <button
            type="button"
            className={selectedRunIds.includes(run.id) ? "selected" : ""}
            onClick={() => toggleRunId(run.id)}
            key={run.id}
          >
            #{run.id} {formatBacktestStrategy(run.strategies?.[0] ?? run.strategy_keys?.[0])}
          </button>
        ))}
      </div>
      <div className="backtest-compare-actions">
        <span>已选 {selectedRunIds.length} 个回测</span>
        <button type="button" onClick={actions.onRunCompare} disabled={state.loading === "compare" || selectedRunIds.length < 2}>
          {state.loading === "compare" ? "对比中..." : "运行对比"}
        </button>
      </div>
      <div className="backtest-data-table narrow" role="table" aria-label="回测对比指标">
        <div className="row head" role="row">
          <span>Run</span>
          <button type="button" onClick={() => setSortKey("return")}>收益</button>
          <button type="button" onClick={() => setSortKey("sharpe")}>Sharpe</button>
          <button type="button" onClick={() => setSortKey("drawdown")}>MaxDD</button>
        </div>
        {compareItems.map((item) => (
          <div className="row" role="row" key={item.run_id}>
            <span>#{item.run_id} {item.name ?? ""}</span>
            <span className={toneFromNumber(item.metrics?.total_return_pct)}>{formatPct(item.metrics?.total_return_pct)}</span>
            <span>{formatNumber(item.metrics?.sharpe ?? item.metrics?.sharpe_ratio)}</span>
            <span className="down">{formatPct(item.metrics?.max_drawdown_pct)}</span>
          </div>
        ))}
        {compareItems.length ? null : <Empty text="选择至少 2 个已完成回测后运行对比。" />}
      </div>
      <Suspense fallback={<div className="backtest-chart-fallback">对比图加载中...</div>}>
        <LazyBacktestCompareChart result={state.compareResult} />
      </Suspense>
      <PanelTitle title="月度收益" meta="按月聚合" />
      <Suspense fallback={<div className="backtest-chart-fallback">热力图加载中...</div>}>
        <LazyBacktestMonthlyHeatmap items={state.monthlyReturns?.items ?? []} />
      </Suspense>
      <div className="backtest-data-table narrow" role="table" aria-label="月度收益">
        <div className="row head" role="row">
          <span>月份</span>
          <span>策略</span>
          <span>基准</span>
          <span>交易</span>
        </div>
        {(state.monthlyReturns?.items ?? []).map((item) => (
          <div className="row" role="row" key={item.month}>
            <span>{item.month}</span>
            <span className={toneFromNumber(item.return_pct)}>{formatPct(item.return_pct)}</span>
            <span>{formatPct(item.benchmark_return_pct)}</span>
            <span>{formatInteger(item.trade_count)}</span>
          </div>
        ))}
        {state.monthlyReturns?.items?.length ? null : <Empty text="选择已完成回测后读取月度收益。" />}
      </div>
    </section>
  );
}

function AttributionPanel({ state, equity }: { state: BacktestResearchState; equity: EquityPoint[] }) {
  const attribution = state.attribution;
  const correlation = state.correlation;
  const strategy = attribution?.strategy ?? attribution?.by_strategy ?? [];
  const canExport = Boolean(
    strategy.length ||
    attribution?.industry?.length ||
    attribution?.market_state?.length ||
    attribution?.data_quality?.length ||
    attribution?.failure_reasons?.length
  );
  return (
    <section className="backtest-research-card">
      <PanelTitle
        title="归因面板"
        meta="策略 / 行业 / 市场 / 质量"
        action={canExport ? <button type="button" onClick={() => exportAttributionCsv(attribution)}>导出 CSV</button> : null}
      />
      <AttributionTable title="策略归因" items={strategy} />
      <AttributionTable title="行业归因" items={attribution?.industry ?? []} />
      <AttributionTable title="市场状态归因" items={attribution?.market_state ?? []} />
      <AttributionTable title="质量分桶" items={attribution?.data_quality ?? []} />
      <AttributionTable title="失败原因" items={attribution?.failure_reasons ?? []} />
      <StrategyDecompositionTable attribution={attribution} />
      <PanelTitle title="收益分布" meta="日收益直方图 + 正态拟合" />
      <Suspense fallback={<div className="backtest-chart-fallback">收益分布加载中...</div>}>
        <LazyBacktestReturnDistribution points={equity} />
      </Suspense>
      <PanelTitle title="相关性矩阵" meta="Pearson" />
      <div
        className="backtest-correlation"
        role="table"
        aria-label="策略相关性矩阵"
        style={correlation?.strategies?.length ? { gridTemplateColumns: `repeat(${correlation.strategies.length + 1}, minmax(82px, 1fr))` } : undefined}
      >
        {correlation?.strategies?.length ? (
          <>
            <div className="cell head">策略</div>
            {correlation.strategies.map((strategyName) => <div className="cell head" key={strategyName}>{strategyName}</div>)}
            {correlation.strategies.map((strategyName, rowIndex) => (
              <MatrixRow correlation={correlation} strategyName={strategyName} rowIndex={rowIndex} key={strategyName} />
            ))}
          </>
        ) : <Empty text="选择多策略回测后显示策略相关性矩阵。" />}
      </div>
    </section>
  );
}

function MatrixRow({
  correlation,
  strategyName,
  rowIndex,
}: {
  correlation: BacktestStrategyCorrelationResponse;
  strategyName: string;
  rowIndex: number;
}) {
  return (
    <>
      <div className="cell head">{strategyName}</div>
      {correlation.strategies.map((target, columnIndex) => (
        <div className="cell" key={`${strategyName}-${target}`}>{formatNumber(correlation.matrix?.[rowIndex]?.[columnIndex])}</div>
      ))}
    </>
  );
}

function AttributionTable({ title, items }: { title: string; items: NonNullable<BacktestAttributionResponse["industry"]> }) {
  return (
    <div className="backtest-data-table narrow" role="table" aria-label={title}>
      <div className="row caption" role="row">{title}</div>
      <div className="row head" role="row">
        <span>分桶</span>
        <span>交易</span>
        <span>胜率</span>
        <span>收益贡献</span>
      </div>
      {items.slice(0, 6).map((item) => (
        <div className="row" role="row" key={`${title}-${item.bucket}`}>
          <span>{item.label || item.bucket}</span>
          <span>{formatInteger(item.trade_count)}</span>
          <span>{formatPct(item.win_rate_pct)}</span>
          <span className={toneFromNumber(item.net_pnl ?? item.contribution_pct ?? item.return_pct)}>{formatMoneyOrPct(item.net_pnl, item.contribution_pct ?? item.return_pct)}</span>
        </div>
      ))}
      {items.length ? null : <Empty text={`${title} 等待接口返回。`} />}
    </div>
  );
}

function StrategyDecompositionTable({ attribution }: { attribution: BacktestAttributionResponse | null }) {
  const rows = [
    ...normalizeAttributionRows("策略", attribution?.strategy ?? attribution?.by_strategy ?? []),
    ...normalizeAttributionRows("行业", attribution?.industry ?? []),
    ...normalizeAttributionRows("市场", attribution?.market_state ?? []),
    ...normalizeAttributionRows("质量", attribution?.data_quality ?? []),
    ...normalizeAttributionRows("失败", attribution?.failure_reasons ?? []),
  ]
    .sort((a, b) => Math.abs(b.returnValue) - Math.abs(a.returnValue))
    .slice(0, 10);
  return (
    <div className="backtest-data-table decomposition" role="table" aria-label="策略拆解对比">
      <div className="row caption" role="row">策略拆解对比</div>
      <div className="row head" role="row">
        <span>类型</span>
        <span>分桶</span>
        <span>样本</span>
        <span>胜率</span>
        <span>收益贡献</span>
      </div>
      {rows.map((item) => (
        <div className="row" role="row" key={`${item.group}-${item.label}`}>
          <span>{item.group}</span>
          <span>{item.label}</span>
          <span>{formatInteger(item.tradeCount)}</span>
          <span>{formatPct(item.winRate)}</span>
          <span className={toneFromNumber(item.returnValue)}>{formatMoneyOrPct(item.netPnl, item.returnValue)}</span>
        </div>
      ))}
      {rows.length ? null : <Empty text="暂无可拆解的策略归因数据。" />}
    </div>
  );
}

function normalizeAttributionRows(group: string, rows: NonNullable<BacktestAttributionResponse["industry"]>) {
  return rows.map((item) => ({
    group,
    label: item.label || item.bucket || "--",
    tradeCount: Number(item.trade_count ?? 0),
    winRate: Number(item.win_rate_pct ?? 0),
    netPnl: item.net_pnl,
    returnValue: Number(item.contribution_pct ?? item.return_pct ?? item.net_pnl ?? 0),
  }));
}

function TaskList<T extends { id: number; name: string; status: string; progress?: number | null; progress_pct?: number | null; strategy?: string }>({
  items,
  selectedId,
  onSelect,
  onCancel,
  onDelete,
}: {
  items: T[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onCancel: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="backtest-task-list">
      {items.map((item) => (
        <div className={`backtest-task-row${selectedId === item.id ? " active" : ""}`} key={item.id}>
          <button type="button" onClick={() => onSelect(item.id)}>
            <strong>{item.name || `任务 #${item.id}`}</strong>
            <span>{formatBacktestStrategy(item.strategy)} · {item.status} · {formatProgress(item.progress ?? item.progress_pct, item.status)}</span>
          </button>
          <button type="button" onClick={() => onCancel(item.id)} disabled={!isCancellable(item.status)}>取消</button>
          <button type="button" className="danger subtle" onClick={() => onDelete(item.id)}>删除</button>
        </div>
      ))}
      {items.length ? null : <Empty text="暂无研究任务。" />}
    </div>
  );
}

function PanelTitle({ title, meta, action }: { title: string; meta?: string; action?: ReactNode }) {
  return (
    <div className="backtest-research-title">
      <h3>{title}</h3>
      {meta ? <span>{meta}</span> : null}
      {action}
    </div>
  );
}

function exportAttributionCsv(attribution: BacktestAttributionResponse | null) {
  const rows = [
    ["类型", "分桶", "样本", "胜率", "收益贡献"],
    ...normalizeAttributionRows("策略", attribution?.strategy ?? attribution?.by_strategy ?? []).map(csvRow),
    ...normalizeAttributionRows("行业", attribution?.industry ?? []).map(csvRow),
    ...normalizeAttributionRows("市场", attribution?.market_state ?? []).map(csvRow),
    ...normalizeAttributionRows("质量", attribution?.data_quality ?? []).map(csvRow),
    ...normalizeAttributionRows("失败", attribution?.failure_reasons ?? []).map(csvRow),
  ];
  const csv = rows.map((row) => row.map(escapeCsvCell).join(",")).join("\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `backtest-attribution-${new Date().toISOString().slice(0, 10)}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function csvRow(item: ReturnType<typeof normalizeAttributionRows>[number]) {
  return [
    item.group,
    item.label,
    String(item.tradeCount),
    `${item.winRate}`,
    `${item.returnValue}`,
  ];
}

function escapeCsvCell(value: string) {
  return `"${String(value).replace(/"/g, '""')}"`;
}

function TextField({ label, value, hint, type = "text", onChange }: { label: string; value: string; hint?: string; type?: string; onChange: (value: string) => void }) {
  return <SharedTextField label={label} value={value} hint={hint} type={type} onChange={(event) => onChange(event.target.value)} />;
}

function DateField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <SharedDateField label={label} value={value} onChange={(event) => onChange(event.target.value)} />;
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: ReadonlyArray<readonly [string, string]>; onChange: (value: string) => void }) {
  return <SharedSelectField label={label} value={value} options={options.map(([optionValue, optionLabel]) => ({ value: optionValue, label: optionLabel }))} onChange={(event) => onChange(event.target.value)} />;
}

function SliderParamField({
  label,
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  onChange: (value: number) => void;
}) {
  return (
    <SharedSliderField
      label={label}
      min={min}
      max={max}
      step={step}
      value={value}
      suffix={suffix}
      onValueChange={(next) => onChange(Number(next))}
    />
  );
}

function Metric({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className={className}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="backtest-empty">{text}</div>;
}

function formatParams(params?: Record<string, BacktestParamValue> | null): string {
  if (!params || !Object.keys(params).length) return "--";
  return Object.entries(params).map(([key, value]) => `${key}=${String(value)}`).join(", ");
}

function formatProgress(progress: number | null | undefined, status: string): string {
  if (status === "completed" || status === "succeeded") return "100%";
  if (typeof progress !== "number" || !Number.isFinite(progress)) return status === "running" ? "运行中" : "--";
  return `${Math.round(progress)}%`;
}

function isCancellable(status: string): boolean {
  return status === "pending" || status === "queued" || status === "running";
}

function truthyFlag(value: unknown): boolean {
  return value === true || value === 1;
}

function parseRunIdsLoose(value: string): number[] {
  return value
    .split(/[,\s]+/)
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item) && item > 0);
}

function formatMoneyCompact(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return "--";
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)}亿`;
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toFixed(0);
}

function capacityTone(status: string): string {
  if (status === "可承载") return "up";
  if (status === "谨慎") return "pbo-medium";
  if (status === "过载") return "down";
  return "";
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err || "操作失败");
}

function sortCompareItems(items: NonNullable<BacktestCompareResponse["items"]>, sortKey: "return" | "sharpe" | "drawdown") {
  return [...items].sort((a, b) => compareMetric(b, sortKey) - compareMetric(a, sortKey));
}

function compareMetric(item: NonNullable<BacktestCompareResponse["items"]>[number], sortKey: "return" | "sharpe" | "drawdown") {
  if (sortKey === "sharpe") return Number(item.metrics?.sharpe ?? item.metrics?.sharpe_ratio ?? -Infinity);
  if (sortKey === "drawdown") return -Math.abs(Number(item.metrics?.max_drawdown_pct ?? Infinity));
  return Number(item.metrics?.total_return_pct ?? -Infinity);
}

function firstNumber(value: string, fallback: number): number {
  const first = Number(String(value || "").split(",")[0]?.trim());
  return Number.isFinite(first) ? first : fallback;
}

function percentToSlider(value: string, fallbackPct: number): number {
  const parsed = firstNumber(value, fallbackPct / 100);
  return Math.abs(parsed) <= 1 ? parsed * 100 : parsed;
}

function ratioFromPercent(value: number): string {
  return String(Number((value / 100).toFixed(4)));
}
