import type { StrategyMeta } from "../../api/strategies";

export function StrategyTrafficLights({ strategies }: { strategies: StrategyMeta[] }) {
  const production = strategies
    .filter((item) => item.visibility === "full" && (item.tier === "core" || item.tier === "auxiliary"))
    .slice(0, 6);
  if (!production.length) return null;
  return (
    <section className="panel strategy-traffic-lights" aria-label="策略健康交通灯">
      <div className="strategy-panel-title">
        <div>
          <h2>策略健康交通灯</h2>
          <span>绿灯可继续观察，黄灯小仓验证，红灯建议暂停或等待样本。</span>
        </div>
      </div>
      <div className="strategy-light-grid">
        {production.map((strategy) => {
          const state = lightState(strategy);
          return (
            <article key={strategy.key} className={state.tone}>
              <strong>{state.icon} {strategy.display_name || strategy.name}</strong>
              <span>{state.reason}</span>
              <small>{state.action}</small>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function lightState(strategy: StrategyMeta) {
  if (strategy.enabled === false) {
    return { tone: "bad", icon: "🔴", reason: "策略已停用", action: "建议操作：暂停使用" };
  }
  if (strategy.probe_status === "failed" || strategy.probe_status === "rejected") {
    return { tone: "bad", icon: "🔴", reason: "探针或验证未通过", action: "建议操作：等待修复后再用" };
  }
  if (strategy.tier === "auxiliary" || strategy.probe_status === "pending") {
    return { tone: "warn", icon: "🟡", reason: "仍处于小仓或观察验证", action: "建议操作：缩小仓位，继续看样本" };
  }
  return { tone: "ok", icon: "🟢", reason: "当前处于生产可用层", action: "建议操作：按风险提示使用" };
}
