import type { BacktestRunSummary } from "../../api/backtests";
import { formatBacktestStrategies, formatMoney, formatPct } from "../backtest/backtestDisplay";
import { strategyDoctorVerdict, strategyHealthLabel } from "./strategyVerdict";

export function StrategyDoctorPanel({
  runs,
  loading,
  onQuickCheck,
  onOpenSignals,
  onOpenCompare,
}: {
  runs: BacktestRunSummary[];
  loading: boolean;
  onQuickCheck: () => void;
  onOpenSignals: () => void;
  onOpenCompare: () => void;
}) {
  const verdict = strategyDoctorVerdict(runs);
  const run = verdict.run;
  const summary = run?.summary ?? {};
  const noCompletedTrades = isFinished(run?.status) && tradeCount(summary) === 0;
  return (
    <section className={`panel strategy-doctor strategy-doctor-${verdict.tone}`} aria-label="策略医生结论">
      <div className="strategy-doctor-main">
        <span className="strategy-doctor-kicker">策略医生</span>
        <h2>{strategyHealthLabel(verdict.tone)}</h2>
        <p>{verdict.detail}</p>
        <strong>{verdict.action}</strong>
      </div>
      <div className="strategy-doctor-metrics" aria-label="核心体检指标">
        <DoctorMetric label="收益" value={noCompletedTrades ? "无成交" : formatPct(summary.total_return_pct)} />
        <DoctorMetric label="胜率" value={noCompletedTrades ? "无成交" : formatPct(summary.win_rate_pct)} />
        <DoctorMetric label="最大回撤" value={formatPct(summary.max_drawdown_pct)} />
        <DoctorMetric label="样本" value={sampleText(tradeCount(summary))} />
      </div>
      <div className="strategy-doctor-actions">
        <button type="button" className="primary" onClick={onQuickCheck} disabled={loading}>
          {loading ? "提交中" : "一键体检"}
        </button>
        <button type="button" onClick={onOpenSignals}>看最近信号</button>
        <button type="button" onClick={onOpenCompare}>比较策略</button>
      </div>
      {run ? (
        <div className="strategy-doctor-run">
          <span>最近体检：{run.name || `任务 #${run.id}`}</span>
          <span>{formatBacktestStrategies(run.strategies)}</span>
          <span>资产 {formatMoney(run.final_equity)}</span>
        </div>
      ) : null}
    </section>
  );
}

function DoctorMetric({ label, value }: { label: string; value: string }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value || "--"}</strong>
    </article>
  );
}

function sampleText(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${value.toLocaleString("zh-CN")} 笔`;
}

function tradeCount(summary: { total_trades?: number | null; trade_count?: number | null }): number | null {
  const value = summary.total_trades ?? summary.trade_count;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isFinished(status?: string | null): boolean {
  return status === "completed" || status === "succeeded";
}
