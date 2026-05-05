import type {
  BacktestAttributionResponse,
  BacktestCompareResponse,
  BacktestMonthlyReturn,
  BacktestExecutionModel,
  BacktestMonthlyReturnsResponse,
  BacktestOptimizationDetail,
  BacktestOptimizationSummary,
  BacktestParamValue,
  BacktestRunSummary,
  BacktestStrategyCorrelationResponse,
  BacktestValidationDetail,
  BacktestValidationSummary,
} from "../../api/backtests";
import { ErrorBanner } from "../../components/shared/Feedback";
import {
  DateField as SharedDateField,
  SelectField as SharedSelectField,
  SliderField as SharedSliderField,
  TextField as SharedTextField,
} from "../../components/shared/FormFields";
import {
  BACKTEST_EXECUTION_MODELS,
  BACKTEST_STRATEGY_OPTIONS,
  OPTIMIZATION_TARGET_OPTIONS,
  formatBacktestStrategy,
  formatInteger,
  formatMoneyOrPct,
  formatNumber,
  formatPct,
  formatRatioPct,
  pboRiskMeta,
  toneFromNumber,
} from "./backtestDisplay";

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

export type BacktestResearchSection = "optimization" | "validation" | "compare" | "attribution";

export function BacktestResearchPanel({
  state,
  actions,
  sections,
}: {
  state: BacktestResearchState;
  actions: BacktestResearchActions;
  sections?: BacktestResearchSection[];
}) {
  const visibleSections = new Set<BacktestResearchSection>(
    sections ?? ["optimization", "validation", "compare", "attribution"]
  );
  return (
    <section className="panel backtest-research">
      <div className="backtest-research-hero">
        <div>
          <span className="backtest-kicker">Research Loop · Phase2</span>
          <h2>回测研究闭环</h2>
          <p>前端按预期 API 接入参数优化、Walk-forward、对比、归因、月度收益和策略相关性；复杂图表后置，当前保持表格和 SVG 轻量展示。</p>
        </div>
        <button type="button" onClick={actions.onRefreshResearch} disabled={state.loading === "research"}>
          {state.loading === "research" ? "刷新中..." : "刷新研究任务"}
        </button>
      </div>

      {state.notice ? <div className="backtest-notice">{state.notice}</div> : null}
      {state.error ? <ErrorBanner message={state.error} onRetry={actions.onRefreshResearch} /> : null}

      <div className="backtest-research-grid">
        {visibleSections.has("optimization") ? <OptimizationPanel state={state} actions={actions} /> : null}
        {visibleSections.has("validation") ? <ValidationPanel state={state} actions={actions} /> : null}
        {visibleSections.has("compare") ? <ComparePanel state={state} actions={actions} /> : null}
        {visibleSections.has("attribution") ? <AttributionPanel state={state} /> : null}
      </div>
    </section>
  );
}

function OptimizationPanel({ state, actions }: { state: BacktestResearchState; actions: BacktestResearchActions }) {
  const detail = state.selectedOptimization;
  return (
    <section className="backtest-research-card span-2">
      <PanelTitle title="优化任务" meta={`${state.optimizations.length} 条`} />
      <div className="backtest-research-form compact">
        <TextField label="名称" value={state.optimizationForm.name} onChange={(name) => actions.onOptimizationFormChange({ name })} />
        <SelectField label="策略" value={state.optimizationForm.strategy} options={BACKTEST_STRATEGY_OPTIONS} onChange={(strategy) => actions.onOptimizationFormChange({ strategy })} />
        <DateField label="训练开始" value={state.optimizationForm.train_start} onChange={(train_start) => actions.onOptimizationFormChange({ train_start })} />
        <DateField label="训练结束" value={state.optimizationForm.train_end} onChange={(train_end) => actions.onOptimizationFormChange({ train_end })} />
        <DateField label="验证开始" value={state.optimizationForm.test_start} onChange={(test_start) => actions.onOptimizationFormChange({ test_start })} />
        <DateField label="验证结束" value={state.optimizationForm.test_end} onChange={(test_end) => actions.onOptimizationFormChange({ test_end })} />
        <TextField type="number" label="初始资金" value={state.optimizationForm.initial_capital} onChange={(initial_capital) => actions.onOptimizationFormChange({ initial_capital })} />
        <SelectField label="执行模型" value={state.optimizationForm.execution_model} options={BACKTEST_EXECUTION_MODELS} onChange={(execution_model) => actions.onOptimizationFormChange({ execution_model: execution_model as BacktestExecutionModel })} />
        <SelectField label="优化目标" value={state.optimizationForm.optimization_target} options={OPTIMIZATION_TARGET_OPTIONS} onChange={(optimization_target) => actions.onOptimizationFormChange({ optimization_target })} />
        <SliderParamField label="最低评分" min={60} max={98} step={1} value={firstNumber(state.optimizationForm.min_score, 80)} onChange={(min_score) => actions.onOptimizationFormChange({ min_score: String(min_score) })} />
        <SliderParamField label="单票仓位上限" min={5} max={50} step={1} suffix="%" value={percentToSlider(state.optimizationForm.max_position_pct, 30)} onChange={(value) => actions.onOptimizationFormChange({ max_position_pct: ratioFromPercent(value) })} />
        <SliderParamField label="最大持有天数" min={1} max={10} step={1} value={firstNumber(state.optimizationForm.max_holding_days, 3)} onChange={(max_holding_days) => actions.onOptimizationFormChange({ max_holding_days: String(max_holding_days) })} />
        <SliderParamField label="止损线" min={2} max={12} step={0.5} suffix="%" value={Math.abs(percentToSlider(state.optimizationForm.stop_loss_pct, -5))} onChange={(value) => actions.onOptimizationFormChange({ stop_loss_pct: ratioFromPercent(-Math.abs(value)) })} />
        <SliderParamField label="止盈线" min={3} max={25} step={0.5} suffix="%" value={percentToSlider(state.optimizationForm.take_profit_pct, 10)} onChange={(value) => actions.onOptimizationFormChange({ take_profit_pct: ratioFromPercent(value) })} />
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

function ValidationPanel({ state, actions }: { state: BacktestResearchState; actions: BacktestResearchActions }) {
  const detail = state.selectedValidation;
  return (
    <section className="backtest-research-card span-2">
      <PanelTitle title="Walk-forward 验证" meta={`${state.validations.length} 条`} />
      <div className="backtest-research-form compact">
        <TextField label="名称" value={state.validationForm.name} onChange={(name) => actions.onValidationFormChange({ name })} />
        <SelectField label="策略" value={state.validationForm.strategy} options={BACKTEST_STRATEGY_OPTIONS} onChange={(strategy) => actions.onValidationFormChange({ strategy })} />
        <DateField label="开始日期" value={state.validationForm.start_date} onChange={(start_date) => actions.onValidationFormChange({ start_date })} />
        <DateField label="结束日期" value={state.validationForm.end_date} onChange={(end_date) => actions.onValidationFormChange({ end_date })} />
        <TextField type="number" label="窗口数" value={state.validationForm.window_count} onChange={(window_count) => actions.onValidationFormChange({ window_count })} />
        <TextField type="number" label="训练比例" value={state.validationForm.train_ratio} onChange={(train_ratio) => actions.onValidationFormChange({ train_ratio })} />
        <TextField type="number" label="初始资金" value={state.validationForm.initial_capital} onChange={(initial_capital) => actions.onValidationFormChange({ initial_capital })} />
        <SelectField label="执行模型" value={state.validationForm.execution_model} options={BACKTEST_EXECUTION_MODELS} onChange={(execution_model) => actions.onValidationFormChange({ execution_model: execution_model as BacktestExecutionModel })} />
        <SelectField label="优化目标" value={state.validationForm.optimization_target} options={OPTIMIZATION_TARGET_OPTIONS} onChange={(optimization_target) => actions.onValidationFormChange({ optimization_target })} />
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

function ComparePanel({ state, actions }: { state: BacktestResearchState; actions: BacktestResearchActions }) {
  const selectedRunIds = parseRunIdsLoose(state.compareRunIds);
  const toggleRunId = (runId: number) => {
    const next = selectedRunIds.includes(runId)
      ? selectedRunIds.filter((item) => item !== runId)
      : [...selectedRunIds, runId];
    actions.onCompareRunIdsChange(next.join(","));
  };
  return (
    <section className="backtest-research-card">
      <PanelTitle title="回测对比" meta="指标表 + SVG" />
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
      <label className="backtest-field">
        <span>Run IDs</span>
        <input value={state.compareRunIds} placeholder="42,45,47" onChange={(event) => actions.onCompareRunIdsChange(event.target.value)} />
      </label>
      <button type="button" onClick={actions.onRunCompare} disabled={state.loading === "compare"}>
        {state.loading === "compare" ? "对比中..." : "运行对比"}
      </button>
      <div className="backtest-data-table narrow" role="table" aria-label="回测对比指标">
        <div className="row head" role="row">
          <span>Run</span>
          <span>收益</span>
          <span>Sharpe</span>
          <span>MaxDD</span>
        </div>
        {(state.compareResult?.items ?? []).map((item) => (
          <div className="row" role="row" key={item.run_id}>
            <span>#{item.run_id} {item.name ?? ""}</span>
            <span className={toneFromNumber(item.metrics?.total_return_pct)}>{formatPct(item.metrics?.total_return_pct)}</span>
            <span>{formatNumber(item.metrics?.sharpe ?? item.metrics?.sharpe_ratio)}</span>
            <span className="down">{formatPct(item.metrics?.max_drawdown_pct)}</span>
          </div>
        ))}
        {state.compareResult?.items?.length ? null : <Empty text="输入 run ids 后展示多回测指标对比。" />}
      </div>
      <MultiEquitySvg result={state.compareResult} />
      <PanelTitle title="月度收益" meta="按月聚合" />
      <MonthlyHeatmapSvg items={state.monthlyReturns?.items ?? []} />
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

function AttributionPanel({ state }: { state: BacktestResearchState }) {
  const attribution = state.attribution;
  const correlation = state.correlation;
  const strategy = attribution?.strategy ?? attribution?.by_strategy ?? [];
  return (
    <section className="backtest-research-card">
      <PanelTitle title="归因面板" meta="策略 / 行业 / 市场 / 质量" />
      <AttributionTable title="策略归因" items={strategy} />
      <AttributionTable title="行业归因" items={attribution?.industry ?? []} />
      <AttributionTable title="市场状态归因" items={attribution?.market_state ?? []} />
      <AttributionTable title="质量分桶" items={attribution?.data_quality ?? []} />
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

function MultiEquitySvg({ result }: { result: BacktestCompareResponse | null }) {
  const series = (result?.items ?? []).filter((item) => (item.equity ?? []).length >= 2).slice(0, 4);
  if (!series.length) {
    return null;
  }
  const values = series.flatMap((item) => (item.equity ?? []).map((point) => point.nav));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const colors = ["#67e8f9", "#d6a55c", "#f97316", "#22c55e"];
  return (
    <div className="backtest-compare-chart">
      <svg viewBox="0 0 520 160" role="img" aria-label="回测对比净值曲线">
        {[36, 72, 108, 144].map((y) => <line x1="18" x2="502" y1={y} y2={y} key={y} />)}
        {series.map((item, index) => (
          <path d={buildLinePath((item.equity ?? []).map((point) => point.nav), min, max, 520, 160)} key={item.run_id} stroke={colors[index]} />
        ))}
      </svg>
      <div className="backtest-chart-legend">
        {series.map((item, index) => <span key={item.run_id}><i style={{ background: colors[index] }} />#{item.run_id}</span>)}
      </div>
    </div>
  );
}

function MonthlyHeatmapSvg({ items }: { items: BacktestMonthlyReturn[] }) {
  if (!items.length) {
    return null;
  }
  const years = Array.from(new Set(items.map((item) => item.month.slice(0, 4)))).sort();
  const months = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"];
  const values = items.map((item) => Number(item.return_pct ?? 0)).filter(Number.isFinite);
  const maxAbs = Math.max(1, ...values.map((value) => Math.abs(value)));
  const cellW = 38;
  const cellH = 24;
  const width = 64 + months.length * cellW;
  const height = 26 + years.length * cellH;
  const itemMap = new Map(items.map((item) => [item.month, item]));

  return (
    <div className="backtest-monthly-heatmap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="月度收益热力图">
        {months.map((month, index) => (
          <text key={month} x={64 + index * cellW + cellW / 2} y={16} textAnchor="middle">{month}</text>
        ))}
        {years.map((year, row) => (
          <g key={year}>
            <text x={8} y={36 + row * cellH} textAnchor="start">{year}</text>
            {months.map((month, col) => {
              const item = itemMap.get(`${year}-${month}`);
              const value = Number(item?.return_pct ?? 0);
              return (
                <g key={`${year}-${month}`}>
                  <rect
                    x={64 + col * cellW}
                    y={24 + row * cellH}
                    width={cellW - 4}
                    height={cellH - 4}
                    rx={5}
                    fill={heatmapColor(value, maxAbs)}
                  />
                  {item ? <text x={64 + col * cellW + cellW / 2 - 2} y={39 + row * cellH} textAnchor="middle">{value.toFixed(1)}</text> : null}
                </g>
              );
            })}
          </g>
        ))}
      </svg>
    </div>
  );
}

function heatmapColor(value: number, maxAbs: number): string {
  if (!Number.isFinite(value) || value === 0) return "#f8fafc";
  const strength = Math.min(Math.abs(value) / maxAbs, 1);
  const alpha = 0.18 + strength * 0.62;
  return value > 0 ? `rgba(220, 38, 38, ${alpha})` : `rgba(22, 163, 74, ${alpha})`;
}

function PanelTitle({ title, meta }: { title: string; meta?: string }) {
  return (
    <div className="backtest-research-title">
      <h3>{title}</h3>
      {meta ? <span>{meta}</span> : null}
    </div>
  );
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

function buildLinePath(values: Array<number | null | undefined>, min: number, max: number, width: number, height: number): string {
  const range = max - min || 1;
  return values.map((value, index) => {
    const x = 18 + (values.length === 1 ? 0 : (index / (values.length - 1)) * (width - 36));
    const y = height - 16 - (((value ?? min) - min) / range) * (height - 32);
    return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}
