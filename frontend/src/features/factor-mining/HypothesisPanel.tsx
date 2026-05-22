import { Button, Checkbox, Input } from "antd";
import { factorMiningApi, type FactorHypothesis } from "../../api/factorMining";
import { useFactorMiningUiStore } from "../../stores/factorMiningUiStore";

export function HypothesisPanel({
  onCodeReady,
}: {
  onCodeReady: (hypothesis: FactorHypothesis, code: string) => void;
}) {
  const topic = useFactorMiningUiStore((state) => state.hypothesisTopic);
  const useLlm = useFactorMiningUiStore((state) => state.useLlm);
  const items = useFactorMiningUiStore((state) => state.hypothesisItems);
  const loading = useFactorMiningUiStore((state) => state.hypothesisLoading);
  const error = useFactorMiningUiStore((state) => state.hypothesisError);
  const setTopic = useFactorMiningUiStore((state) => state.setHypothesisTopic);
  const setUseLlm = useFactorMiningUiStore((state) => state.setUseLlm);
  const setItems = useFactorMiningUiStore((state) => state.setHypothesisItems);
  const setLoading = useFactorMiningUiStore((state) => state.setHypothesisLoading);
  const setError = useFactorMiningUiStore((state) => state.setHypothesisError);

  async function generate() {
    setLoading("generate");
    setError("");
    try {
      const result = await factorMiningApi.generateHypotheses({ topic, count: 20, use_llm: useLlm });
      setItems(result.items ?? []);
      if (result.warning) setError(result.warning);
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setLoading("");
    }
  }

  async function synthesize(item: FactorHypothesis) {
    setLoading(item.factor_key);
    setError("");
    try {
      const result = await factorMiningApi.synthesizeCode(item, useLlm);
      onCodeReady(item, result.formula_code);
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setLoading("");
    }
  }

  return (
    <section className="factor-hypothesis-panel">
      <div className="factor-section-title">
        <h3>1. 生成因子假设</h3>
        <span>输入研究方向，系统生成候选假设，再选择一个合成代码。</span>
      </div>
      <div className="factor-topic-row">
        <Input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="例如：分时 VWAP 折价、涨停后缩量洗盘" />
        <Checkbox checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)}>
          使用 deepseek-v4-flash
        </Checkbox>
        <Button type="primary" onClick={() => void generate()} loading={loading === "generate"} disabled={!topic.trim()}>
          {loading === "generate" ? "生成中" : "生成假设"}
        </Button>
      </div>
      {error ? <p className="factor-inline-error">{error}</p> : null}
      <div className="factor-hypothesis-list">
        {items.map((item) => (
          <article key={item.factor_key}>
            <div>
              <strong>{item.factor_name}</strong>
              <span>{item.hypothesis}</span>
              <small>字段：{item.data_deps.join("、") || "默认日线字段"}</small>
            </div>
            <Button type="default" onClick={() => void synthesize(item)} loading={loading === item.factor_key}>
              {loading === item.factor_key ? "合成中" : "合成代码"}
            </Button>
          </article>
        ))}
      </div>
    </section>
  );
}

function toMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
