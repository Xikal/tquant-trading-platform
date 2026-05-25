import { Alert, Button, Card, Checkbox, Flex, Input, Space, Typography } from "antd";
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
    <Card size="small" title="1. 生成因子假设" extra={<Typography.Text type="secondary">输入研究方向，选择假设后合成代码。</Typography.Text>}>
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <Flex gap={8} align="center" wrap>
          <Input style={{ flex: "1 1 280px" }} value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="例如：分时 VWAP 折价、涨停后缩量洗盘" />
          <Checkbox checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)}>
            使用 deepseek-v4-flash
          </Checkbox>
          <Button type="primary" onClick={() => void generate()} loading={loading === "generate"} disabled={!topic.trim()}>
            {loading === "generate" ? "生成中" : "生成假设"}
          </Button>
        </Flex>
        {error ? <Alert type="warning" showIcon message={error} /> : null}
        <Space direction="vertical" size={8} style={{ width: "100%", maxHeight: 360, overflowY: "auto" }}>
        {items.map((item) => (
          <Card key={item.factor_key} size="small">
            <Flex justify="space-between" gap={12} align="center" wrap>
              <Space direction="vertical" size={2} style={{ flex: "1 1 260px" }}>
                <Typography.Text strong>{item.factor_name}</Typography.Text>
                <Typography.Text>{item.hypothesis}</Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>字段：{item.data_deps.join("、") || "默认日线字段"}</Typography.Text>
              </Space>
              <Button type="default" onClick={() => void synthesize(item)} loading={loading === item.factor_key}>
                {loading === item.factor_key ? "合成中" : "合成代码"}
              </Button>
            </Flex>
          </Card>
        ))}
        </Space>
      </Space>
    </Card>
  );
}

function toMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
