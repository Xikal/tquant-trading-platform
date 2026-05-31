import { useEffect, useMemo } from "react";
import { Button, Card, Col, Flex, Form, Input, Row, Space, Tag, Typography } from "antd";
import {
  factorMiningApi,
  type FactorDefinition,
  type FactorEvalResult,
  type FactorHypothesis,
  type FactorHealthItem,
} from "../../api/factorMining";
import type { AuthUser } from "../../types";
import { EmptyPlaceholder, ErrorBanner, SkeletonBlock } from "../../components/shared/Feedback";
import { isAdmin } from "../shared/strategyPermissions";
import { EvalResultCard } from "./EvalResultCard";
import { FactorActivationToggle } from "./FactorActivationToggle";
import { FactorHealthDashboard } from "./FactorHealthDashboard";
import { HypothesisPanel } from "./HypothesisPanel";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { AppForm, SubmitBar } from "../../ui/forms/AppForm";
import { useFactorMiningUiStore, type FactorDraft } from "../../stores/factorMiningUiStore";
import { useServerState } from "../../state/serverState";

const { TextArea } = Input;
const FACTOR_MINING_SERVER_KEYS = {
  factors: ["factor-mining", "factors"] as const,
  healthItems: ["factor-mining", "health-items"] as const,
  result: ["factor-mining", "result"] as const,
};

export function FactorMiningTab({ currentUser }: { currentUser: AuthUser }) {
  const admin = isAdmin(currentUser);
  const selectedKey = useFactorMiningUiStore((state) => state.selectedKey);
  const draft = useFactorMiningUiStore((state) => state.draft);
  const [factors, setFactors] = useServerState<FactorDefinition[]>(FACTOR_MINING_SERVER_KEYS.factors, []);
  const [healthItems, setHealthItems] = useServerState<FactorHealthItem[]>(FACTOR_MINING_SERVER_KEYS.healthItems, []);
  const activation = useFactorMiningUiStore((state) => state.activation);
  const [result, setResult] = useServerState<FactorEvalResult | null>(FACTOR_MINING_SERVER_KEYS.result, null);
  const loading = useFactorMiningUiStore((state) => state.loading);
  const error = useFactorMiningUiStore((state) => state.error);
  const setSelectedKey = useFactorMiningUiStore((state) => state.setSelectedKey);
  const setDraft = useFactorMiningUiStore((state) => state.setDraft);
  const setActivation = useFactorMiningUiStore((state) => state.setActivation);
  const setLoading = useFactorMiningUiStore((state) => state.setLoading);
  const setError = useFactorMiningUiStore((state) => state.setError);
  const selected = useMemo(() => factors.find((item) => item.factor_key === selectedKey), [factors, selectedKey]);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading("load");
    setError("");
    try {
      const [list, health] = await Promise.all([factorMiningApi.listFactors(), factorMiningApi.getHealth()]);
      setFactors(list.items ?? []);
      setHealthItems(health.items ?? []);
      if (!useFactorMiningUiStore.getState().selectedKey) setSelectedKey(list.items?.[0]?.factor_key || "");
      const productionKeys = (list.items ?? []).filter((item) => item.status === "production").map((item) => item.factor_key);
      const activePairs = await Promise.allSettled(productionKeys.map(async (key) => [key, (await factorMiningApi.getActivation(key)).active] as const));
      setActivation(Object.fromEntries(activePairs.flatMap((item) => item.status === "fulfilled" ? [item.value] : [])));
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setLoading("");
    }
  }

  async function createDraftFactor() {
    setLoading("create");
    setError("");
    try {
      const created = await factorMiningApi.createFactor({
        factor_key: draft.key,
        name: draft.name,
        hypothesis: draft.hypothesis,
        formula_code: draft.code,
        data_deps: ["close_price", "volume", "amount"],
        direction: "higher_better",
        category: "price",
        source: "llm_generated",
      });
      setFactors((current) => [created, ...current.filter((item) => item.factor_key !== created.factor_key)]);
      setSelectedKey(created.factor_key);
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setLoading("");
    }
  }

  async function evaluateSelected() {
    if (!selected) return;
    setLoading("evaluate");
    setError("");
    try {
      const response = await factorMiningApi.evaluateFactor(selected.factor_key, {
        holding_days: 5,
        limit_symbols: 500,
        min_cross_section: 20,
      });
      setResult(response.result);
      setFactors((current) => current.map((item) => item.factor_key === selected.factor_key ? response.factor : item));
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setLoading("");
    }
  }

  async function promoteSelected(target: "validated" | "production") {
    if (!selected || !admin) return;
    setLoading(`promote-${target}`);
    setError("");
    try {
      const updated = await factorMiningApi.promoteFactor(selected.factor_key, target, "前端因子实验室人工审批");
      setFactors((current) => current.map((item) => item.factor_key === updated.factor_key ? updated : item));
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setLoading("");
    }
  }

  function handleCodeReady(hypothesis: FactorHypothesis, code: string) {
    setDraft({
      key: hypothesis.factor_key,
      name: hypothesis.factor_name,
      hypothesis: hypothesis.hypothesis,
      code,
    });
  }

  const currentResult = result ?? selected?.eval_result;

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Card size="small">
        <Flex align="start" justify="space-between" gap={16} wrap>
          <Space direction="vertical" size={2}>
            <Typography.Title level={4} style={{ margin: 0 }}>因子实验室</Typography.Title>
            <Typography.Text type="secondary">生成假设、合成代码、跑 IC / Walk-forward 评估。未通过生产门槛的因子不会进入策略评分。</Typography.Text>
          </Space>
          <Button type="default" onClick={() => void load()} loading={loading === "load"}>
            {loading === "load" ? "刷新中" : "刷新"}
          </Button>
        </Flex>
      </Card>
      {error ? <ErrorBanner message={`因子实验室错误：${error}`} /> : null}
      {loading === "load" ? <SkeletonBlock rows={4} title /> : null}
      {loading !== "load" ? (
        <Row gutter={[12, 12]}>
          <Col xs={24} xl={13}>
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <HypothesisPanel onCodeReady={handleCodeReady} />
            <DraftFactorEditor
              draft={draft}
              loading={loading === "create"}
              onChange={setDraft}
              onCreate={createDraftFactor}
            />
            </Space>
          </Col>
          <Col xs={24} xl={11}>
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <FactorLibraryList
              factors={factors}
              selectedKey={selectedKey}
              activation={activation}
              admin={admin}
              onSelect={setSelectedKey}
              onActivationChange={(key, active) => setActivation((current) => ({ ...current, [key]: active }))}
            />
            <EvalResultCard result={currentResult} />
            <Flex gap={8} wrap>
              <Button type="primary" onClick={() => void evaluateSelected()} disabled={!selected} loading={loading === "evaluate"}>
                {loading === "evaluate" ? "评估中" : "评估因子"}
              </Button>
              <Button type="default" onClick={() => void promoteSelected("validated")} disabled={!admin || !selected} loading={loading === "promote-validated"}>
                晋级候选
              </Button>
              <Button type="default" onClick={() => void promoteSelected("production")} disabled={!admin || !selected} loading={loading === "promote-production"}>
                晋级生产
              </Button>
            </Flex>
            <FactorHealthDashboard items={healthItems} />
            </Space>
          </Col>
        </Row>
      ) : null}
    </Space>
  );
}

function DraftFactorEditor({
  draft,
  loading,
  onChange,
  onCreate,
}: {
  draft: FactorDraft;
  loading: boolean;
  onChange: (draft: FactorDraft) => void;
  onCreate: () => void;
}) {
  return (
    <Card size="small" title="2. 因子代码草稿" extra={<Typography.Text type="secondary">可以人工调整后再保存到因子库。</Typography.Text>}>
      <AppForm onFinish={onCreate}>
        <Row gutter={12}>
          <Col xs={24} sm={12}>
            <Form.Item label="因子 Key" required>
              <Input value={draft.key} onChange={(event) => onChange({ ...draft, key: event.target.value })} placeholder="factor_key" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item label="因子名称" required>
              <Input value={draft.name} onChange={(event) => onChange({ ...draft, name: event.target.value })} placeholder="因子名称" />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item label="经济学假设">
          <TextArea value={draft.hypothesis} onChange={(event) => onChange({ ...draft, hypothesis: event.target.value })} placeholder="经济学假设" rows={3} />
        </Form.Item>
        <Form.Item label="因子代码" required>
          <TextArea value={draft.code} onChange={(event) => onChange({ ...draft, code: event.target.value })} placeholder="def compute_factor(bars):" rows={8} />
        </Form.Item>
        <SubmitBar submitText={loading ? "保存中" : "保存到因子库"} loading={loading} disabled={!draft.key.trim() || !draft.name.trim() || !draft.code.trim()} />
      </AppForm>
    </Card>
  );
}

function FactorLibraryList({
  factors,
  selectedKey,
  activation,
  admin,
  onSelect,
  onActivationChange,
}: {
  factors: FactorDefinition[];
  selectedKey: string;
  activation: Record<string, boolean>;
  admin: boolean;
  onSelect: (key: string) => void;
  onActivationChange: (key: string, active: boolean) => void;
}) {
  if (!factors.length) {
    return <EmptyPlaceholder title="暂无因子" description="先生成假设并保存代码草稿。" />;
  }
  return (
    <Card size="small" title="因子库" extra={<Typography.Text type="secondary">{factors.length} 个因子</Typography.Text>}>
      <VirtualGrid<FactorDefinition>
        rowKey="factor_key"
        dataSource={factors}
        onRow={(factor) => ({
          onClick: () => onSelect(factor.factor_key),
        })}
        scroll={{ x: 760, y: 360 }}
        columns={[
          {
            title: "因子",
            dataIndex: "name",
            render: (_value, factor) => (
              <Button type="text" onClick={() => onSelect(factor.factor_key)} style={{ height: "auto", padding: 0, textAlign: "left" }}>
                <Space direction="vertical" size={0} style={{ alignItems: "flex-start" }}>
                  <Space size={4}>
                    <Typography.Text strong>{factor.name}</Typography.Text>
                    {selectedKey === factor.factor_key ? <Tag color="blue">已选择</Tag> : null}
                  </Space>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>{factor.factor_key}</Typography.Text>
                </Space>
              </Button>
            ),
          },
          {
            title: "状态",
            dataIndex: "status",
            render: (status) => <Tag color={statusColor(status)}>{statusText(status)}</Tag>,
          },
          {
            title: "IC",
            render: (_value, factor) => `${((factor.eval_result?.ic_mean ?? 0) * 100).toFixed(2)}%`,
            align: "right",
          },
          {
            title: "方向",
            dataIndex: "direction",
            render: (direction) => direction === "higher_better" ? "越高越好" : "越低越好",
          },
          {
            title: "接入评分",
            render: (_value, factor) => admin && factor.status === "production" ? (
              <FactorActivationToggle
                factorKey={factor.factor_key}
                active={Boolean(activation[factor.factor_key])}
                onChange={(active) => onActivationChange(factor.factor_key, active)}
              />
            ) : "--",
          },
        ]}
      />
    </Card>
  );
}

function statusText(status: string): string {
  if (status === "production") return "生产";
  if (status === "validated") return "候选";
  if (status === "rejected") return "已拒绝";
  if (status === "archived") return "归档";
  return "研究";
}

function statusColor(status: string): string {
  if (status === "production") return "green";
  if (status === "validated") return "blue";
  if (status === "rejected") return "red";
  if (status === "archived") return "default";
  return "gold";
}

function toMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
