import { useEffect, useMemo, useState } from "react";
import { factorMiningApi, type FactorDefinition, type FactorHypothesis } from "../../api/factorMining";
import { ErrorBanner, EmptyPlaceholder, SkeletonBlock } from "../../components/shared/Feedback";
import { formatPct } from "../backtest/backtestDisplay";

export function FactorMiningTab() {
  const [topic, setTopic] = useState("A股低吸量价结构与情绪温度交叉因子");
  const [hypotheses, setHypotheses] = useState<FactorHypothesis[]>([]);
  const [factors, setFactors] = useState<FactorDefinition[]>([]);
  const [selected, setSelected] = useState<FactorHypothesis | null>(null);
  const [formulaCode, setFormulaCode] = useState("");
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    void loadFactors();
  }, []);

  async function loadFactors() {
    setError("");
    try {
      const payload = await factorMiningApi.listFactors();
      setFactors(payload.items ?? []);
    } catch (err) {
      setError(toMessage(err));
    }
  }

  async function generateHypotheses() {
    setLoading("hypotheses");
    setError("");
    setNotice("");
    try {
      const payload = await factorMiningApi.generateHypotheses(topic, 20);
      setHypotheses(payload.items ?? []);
      setNotice(payload.warning || `已使用 ${payload.provider} 生成候选假设`);
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setLoading("");
    }
  }

  async function synthesize(item: FactorHypothesis) {
    setSelected(item);
    setLoading("synth");
    setError("");
    try {
      const payload = await factorMiningApi.synthesizeCode(item);
      setFormulaCode(payload.formula_code);
      setNotice(payload.warning || "因子代码已生成并通过安全检查。");
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setLoading("");
    }
  }

  async function createAndEvaluate() {
    if (!selected || !formulaCode.trim()) return;
    setLoading("evaluate");
    setError("");
    try {
      await factorMiningApi.createFactor({
        factor_key: selected.factor_key,
        name: selected.factor_name,
        hypothesis: selected.hypothesis,
        formula_code: formulaCode,
        data_deps: selected.data_deps,
        direction: selected.direction,
        category: selected.category,
        source: "llm_generated",
      });
      await factorMiningApi.evaluateFactor(selected.factor_key, { limit_symbols: 500, holding_days: 5 });
      setNotice("因子已创建并完成评估。");
      await loadFactors();
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setLoading("");
    }
  }

  return (
    <div className="factor-lab">
      <section className="panel factor-lab-hero">
        <div>
          <h2>因子实验室</h2>
          <p>DeepSeek 生成假设，沙盒执行代码，统计引擎验证 IC/ICIR/OOS。未通过生产门槛的因子不会进入交易建议。</p>
        </div>
        <div className="factor-topic-row">
          <input value={topic} onChange={(event) => setTopic(event.target.value)} />
          <button type="button" onClick={generateHypotheses} disabled={loading === "hypotheses"}>
            {loading === "hypotheses" ? "生成中" : "生成 20 个因子假设"}
          </button>
        </div>
      </section>
      {error ? <ErrorBanner message={`因子实验室错误：${error}`} /> : null}
      {notice ? <div className="panel strategy-notice">{notice}</div> : null}
      <div className="factor-lab-grid">
        <section className="panel">
          <PanelHead title="候选假设" hint="先看经济逻辑，再合成代码。" />
          {loading === "hypotheses" ? <SkeletonBlock rows={4} title /> : null}
          {!loading && !hypotheses.length ? <EmptyPlaceholder title="暂无候选" description="输入研究主题后生成候选因子。" /> : null}
          <div className="factor-card-list">
            {hypotheses.map((item) => (
              <article key={item.factor_key} className={selected?.factor_key === item.factor_key ? "active" : ""}>
                <strong>{item.factor_name}</strong>
                <span>{item.hypothesis}</span>
                <small>字段：{item.data_deps.join("、")}</small>
                <button type="button" onClick={() => synthesize(item)}>合成代码</button>
              </article>
            ))}
          </div>
        </section>
        <section className="panel">
          <PanelHead title="安全代码预览" hint="只能执行 pandas / numpy / math，禁止 IO 和网络。" />
          <textarea value={formulaCode} onChange={(event) => setFormulaCode(event.target.value)} rows={16} />
          <button type="button" className="primary" onClick={createAndEvaluate} disabled={!selected || !formulaCode || loading === "evaluate"}>
            {loading === "evaluate" ? "评估中" : "创建并评估"}
          </button>
        </section>
      </div>
      <section className="panel">
        <PanelHead title="因子库与评估结果" hint="production 必须通过显著性、样本外和人工审批。" />
        <FactorTable factors={factors} onPromote={loadFactors} onError={setError} onNotice={setNotice} />
      </section>
    </div>
  );
}

function FactorTable({
  factors,
  onPromote,
  onError,
  onNotice,
}: {
  factors: FactorDefinition[];
  onPromote: () => void;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}) {
  const rows = useMemo(() => factors, [factors]);
  if (!rows.length) return <EmptyPlaceholder title="暂无因子" description="生成候选并评估后会显示在这里。" />;
  return (
    <div className="factor-table">
      {rows.map((factor) => (
        <article key={factor.factor_key}>
          <div>
            <strong>{factor.name}</strong>
            <span>{factor.factor_key}</span>
          </div>
          <b className={`factor-status ${factor.status}`}>{statusText(factor.status)}</b>
          <span>IC {metric(factor.eval_result?.ic_mean)}</span>
          <span>t {metric(factor.eval_result?.ic_t_stat)}</span>
          <span>Top {returnPct(factor.eval_result?.top_quintile_return)}</span>
          <span>{factor.eval_result?.passed_production_gate ? "可申请生产" : "研究观察"}</span>
          <button type="button" onClick={() => promote(factor, onPromote, onError, onNotice)}>晋级</button>
        </article>
      ))}
    </div>
  );
}

async function promote(
  factor: FactorDefinition,
  onDone: () => void,
  onError: (message: string) => void,
  onNotice: (message: string) => void,
) {
  const target = factor.eval_result?.passed_production_gate ? "production" : "validated";
  try {
    onError("");
    await factorMiningApi.promoteFactor(factor.factor_key, target, "因子实验室人工审批");
    onNotice(`已将 ${factor.name} 晋级为${statusText(target)}。`);
    onDone();
  } catch (err) {
    onError(toMessage(err));
  }
}

function PanelHead({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="strategy-panel-title">
      <div>
        <h2>{title}</h2>
        <span>{hint}</span>
      </div>
    </div>
  );
}

function statusText(status: string): string {
  if (status === "candidate") return "候选";
  if (status === "validated") return "已验证";
  if (status === "production") return "生产";
  if (status === "rejected") return "淘汰";
  return status;
}

function metric(value?: number | null): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "--";
}

function returnPct(value?: number | null): string {
  return typeof value === "number" && Number.isFinite(value) ? formatPct(value * 100) : "--";
}

function toMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
