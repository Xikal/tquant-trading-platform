import type { FactorHealthItem } from "../../api/factorMining";

export function FactorHealthDashboard({ items }: { items: FactorHealthItem[] }) {
  const production = items.filter((item) => item.status === "production");
  const decaying = items.filter((item) => item.trend === "decaying");
  return (
    <section className="factor-health-dashboard">
      <div className="factor-section-title">
        <h3>生产因子健康</h3>
        <span>滚动 IC 趋势用于发现失效，不直接自动改生产权重。</span>
      </div>
      <div className="factor-health-summary">
        <article>
          <span>生产因子</span>
          <strong>{production.length}</strong>
        </article>
        <article>
          <span>衰减提醒</span>
          <strong>{decaying.length}</strong>
        </article>
        <article>
          <span>最近评估</span>
          <strong>{items.reduce((sum, item) => sum + (item.run_count || 0), 0)}</strong>
        </article>
      </div>
      <div className="factor-health-list">
        {items.slice(0, 8).map((item) => (
          <article key={item.factor_key}>
            <div>
              <strong>{item.name}</strong>
              <span>{item.factor_key}</span>
            </div>
            <b className={item.trend}>{trendText(item.trend)}</b>
            <small>IC {(Number(item.ic_mean || 0) * 100).toFixed(2)}% · t {Number(item.ic_t_stat || 0).toFixed(2)}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function trendText(trend: string): string {
  if (trend === "improving") return "改善";
  if (trend === "decaying") return "衰减";
  return "稳定";
}
