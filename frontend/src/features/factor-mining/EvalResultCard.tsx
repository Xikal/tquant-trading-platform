import type { FactorEvalResult } from "../../api/factorMining";
import { formatPct } from "../backtest/backtestDisplay";

export function EvalResultCard({ result }: { result: FactorEvalResult | null | undefined }) {
  if (!result) {
    return (
      <section className="factor-eval-card empty">
        <strong>暂无评估结果</strong>
        <span>先选择因子并点击“评估因子”，系统会展示 IC、Walk-forward 和生产门槛。</span>
      </section>
    );
  }
  const items = [
    { label: "IC 均值", value: pct(result.ic_mean), tone: result.ic_mean > 0.03 ? "ok" : "warn" },
    { label: "ICIR", value: result.icir.toFixed(2), tone: result.icir > 0.4 ? "ok" : "warn" },
    { label: "OOS IC", value: pct(result.oos_ic_mean), tone: result.is_oos_consistent ? "ok" : "warn" },
    { label: "滚动 OOS", value: pct(result.walk_forward_oos_ic_mean ?? 0), tone: result.walk_forward_no_negative_windows ? "ok" : "warn" },
    { label: "Top20%收益", value: formatPct((result.top_quintile_return ?? 0) * 100), tone: result.top_quintile_return > 0.005 ? "ok" : "warn" },
    { label: "生产门槛", value: result.passed_production_gate ? "通过" : "未通过", tone: result.passed_production_gate ? "ok" : "bad" },
  ];
  return (
    <section className="factor-eval-card">
      <div className="factor-section-title">
        <h3>评估结果</h3>
        <span>样本 {result.observation_count} 条 · 交易日 {result.sample_days} 天 · Walk-forward {result.walk_forward_window_count ?? 0} 窗口</span>
      </div>
      <div className="factor-metric-grid">
        {items.map((item) => (
          <article key={item.label} className={item.tone}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </div>
      {result.warnings?.length ? (
        <ul className="factor-warnings">
          {result.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function pct(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}
