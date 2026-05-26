import { Button } from "antd";
import type {
  BacktestAttributionResponse,
  BacktestCompareResponse,
  EquityPoint,
  BacktestMonthlyReturnsResponse,
  BacktestOptimizationDetail,
  BacktestOptimizationSummary,
  BacktestRunSummary,
  BacktestStrategyCorrelationResponse,
  BacktestValidationDetail,
  BacktestValidationSummary,
} from "../../api/backtests";
import { ErrorBanner } from "../../components/shared/Feedback";
import { useBacktestStrategyOptions } from "./useBacktestStrategyOptions";
import { AttributionPanel } from "./AttributionPanel";
import { ComparePanel } from "./ComparePanel";
import { MLCapacityPanel } from "./MLCapacityPanel";
import { OptimizationPanel } from "./OptimizationPanel";
import { ValidationPanel } from "./ValidationPanel";
import type { OptimizationFormState, ValidationFormState } from "./backtestForms";
import {
  BACKTEST_HERO_TEXT_STYLE,
  BACKTEST_HERO_TITLE_STYLE,
  BACKTEST_KICKER_STYLE,
  BACKTEST_NOTICE_STYLE,
} from "./backtestPageLayoutStyles";
import {
  BACKTEST_RESEARCH_GRID_STYLE,
  BACKTEST_RESEARCH_HERO_STYLE,
  backtestResearchPanelStyle,
} from "./backtestResearchStyles";

export type { OptimizationFormState, ValidationFormState } from "./backtestForms";

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
  onPromoteValidationStateParams: (validationId: number) => void;
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
    <section className="panel" style={backtestResearchPanelStyle(focused)}>
      <div style={BACKTEST_RESEARCH_HERO_STYLE}>
        <div style={{ minWidth: 0 }}>
          <span style={BACKTEST_KICKER_STYLE}>Research Loop · Phase2</span>
          <h2 style={BACKTEST_HERO_TITLE_STYLE}>回测研究闭环</h2>
          <p style={BACKTEST_HERO_TEXT_STYLE}>按“优化参数 → 样本外验证 → 多任务对比 → 归因复盘”使用。优先看收益、胜率、最大回撤和样本外通过率。</p>
        </div>
        <Button onClick={actions.onRefreshResearch} disabled={state.loading === "research"}>
          {state.loading === "research" ? "刷新中..." : "刷新研究任务"}
        </Button>
      </div>

      {state.notice ? <div style={BACKTEST_NOTICE_STYLE}>{state.notice}</div> : null}
      {state.error ? <ErrorBanner message={state.error} onRetry={actions.onRefreshResearch} /> : null}

      <div style={BACKTEST_RESEARCH_GRID_STYLE}>
        {visibleSections.has("optimization") ? <OptimizationPanel state={state} actions={actions} strategyOptions={strategyOptions} /> : null}
        {visibleSections.has("validation") ? <ValidationPanel state={state} actions={actions} strategyOptions={strategyOptions} /> : null}
        {visibleSections.has("compare") ? <ComparePanel state={state} actions={actions} /> : null}
        {visibleSections.has("attribution") ? <AttributionPanel state={state} equity={equity ?? []} /> : null}
        {visibleSections.has("capacity") ? <MLCapacityPanel strategyOptions={strategyOptions} /> : null}
      </div>
    </section>
  );
}
