import type { BacktestRunSummary } from "../../api/backtests";
import type { StrategyMeta } from "../../api/strategies";
import { formatDateTime, formatPct } from "../backtest/backtestDisplay";
import { latestFinishedRun, strategyDoctorVerdict, strategyHealthLabel } from "./strategyVerdict";

export function StrategyHubSummaryBar({
  runs,
  strategies,
  loading,
  onStartCheck,
}: {
  runs: BacktestRunSummary[];
  strategies: StrategyMeta[];
  loading: boolean;
  onStartCheck: () => void;
}) {
  const verdict = strategyDoctorVerdict(runs);
  const latestRun = latestFinishedRun(runs);
  const production = strategies.filter((item) => item.visibility === "full" && (item.tier === "core" || item.tier === "auxiliary"));
  const okCount = production.filter((item) => lightTone(item) === "ok").length;
  const warnCount = production.filter((item) => lightTone(item) === "warn").length;
  const badCount = production.filter((item) => lightTone(item) === "bad").length;

  return (
    <section className="panel strategy-summary-bar">
      <div className="strategy-summary-copy">
        <span className="strategy-kicker">策略健康中心</span>
        <h1>现在该不该继续用这些策略</h1>
        <p>{verdict.detail}</p>
        <small>{verdict.action}</small>
      </div>
      <div className="strategy-summary-stats">
        <article>
          <span>当前结论</span>
          <strong className={verdict.tone}>{strategyHealthLabel(verdict.tone)}</strong>
        </article>
        <article>
          <span>最近体检</span>
          <strong>{latestRun ? formatDateTime(latestRun.created_at) : "暂无"}</strong>
        </article>
        <article>
          <span>最近胜率</span>
          <strong>{latestRun?.summary?.win_rate_pct != null ? formatPct(latestRun.summary.win_rate_pct) : "--"}</strong>
        </article>
      </div>
      <div className="strategy-summary-actions">
        <button type="button" className="primary" onClick={onStartCheck} disabled={loading}>
          {loading ? "提交中" : "开始策略体检"}
        </button>
      </div>
      <div className="strategy-summary-lights">
        <article className="strategy-summary-light ok">
          <strong>🟢 {okCount}</strong>
          <span>可继续观察</span>
        </article>
        <article className="strategy-summary-light warn">
          <strong>🟡 {warnCount}</strong>
          <span>小仓验证</span>
        </article>
        <article className="strategy-summary-light bad">
          <strong>🔴 {badCount}</strong>
          <span>建议暂停</span>
        </article>
      </div>
      <div className="strategy-summary-list">
        {production.slice(0, 4).map((strategy) => {
          const tone = lightTone(strategy);
          return (
            <article key={strategy.key} className={`strategy-summary-item ${tone}`}>
              <strong>{strategy.display_name || strategy.name}</strong>
              <span>{strategyHint(strategy)}</span>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function lightTone(strategy: StrategyMeta): "ok" | "warn" | "bad" {
  if (strategy.enabled === false) return "bad";
  if (strategy.probe_status === "failed" || strategy.probe_status === "rejected") return "bad";
  if (strategy.tier === "auxiliary" || strategy.probe_status === "pending") return "warn";
  return "ok";
}

function strategyHint(strategy: StrategyMeta): string {
  if (strategy.enabled === false) return "已停用，不建议继续使用";
  if (strategy.probe_status === "failed" || strategy.probe_status === "rejected") return "验证未通过，先排查原因";
  if (strategy.tier === "auxiliary" || strategy.probe_status === "pending") return "仍在小仓观察，暂不满仓";
  return "当前处于生产可用层";
}
