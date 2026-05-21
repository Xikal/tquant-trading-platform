import { useEffect, useMemo, useState } from "react";
import { Button, Input } from "antd";
import {
  factorMiningApi,
  type FactorDefinition,
  type FactorEvalResult,
  type FactorHealthItem,
  type FactorHypothesis,
} from "../../api/factorMining";
import type { AuthUser } from "../../types";
import { EmptyPlaceholder, ErrorBanner, SkeletonBlock } from "../../components/shared/Feedback";
import { isAdmin } from "../strategy/strategyPermissions";
import { EvalResultCard } from "./EvalResultCard";
import { FactorActivationToggle } from "./FactorActivationToggle";
import { FactorHealthDashboard } from "./FactorHealthDashboard";
import { HypothesisPanel } from "./HypothesisPanel";

const { TextArea } = Input;

export function FactorMiningTab({ currentUser }: { currentUser: AuthUser }) {
  const [factors, setFactors] = useState<FactorDefinition[]>([]);
  const [healthItems, setHealthItems] = useState<FactorHealthItem[]>([]);
  const [activation, setActivation] = useState<Record<string, boolean>>({});
  const [selectedKey, setSelectedKey] = useState("");
  const [draft, setDraft] = useState({ key: "", name: "", hypothesis: "", code: "" });
  const [result, setResult] = useState<FactorEvalResult | null>(null);
  const [loading, setLoading] = useState("load");
  const [error, setError] = useState("");
  const admin = isAdmin(currentUser);
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
      setSelectedKey((current) => current || list.items?.[0]?.factor_key || "");
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
    <div className="factor-mining-tab">
      <section className="factor-hero">
        <div>
          <h2>因子实验室</h2>
          <p>生成假设、合成代码、跑 IC / Walk-forward 评估。未通过生产门槛的因子不会进入策略评分。</p>
        </div>
        <Button type="default" onClick={() => void load()} loading={loading === "load"}>
          {loading === "load" ? "刷新中" : "刷新"}
        </Button>
      </section>
      {error ? <ErrorBanner message={`因子实验室错误：${error}`} /> : null}
      {loading === "load" ? <SkeletonBlock rows={4} title /> : null}
      {loading !== "load" ? (
        <div className="factor-mining-grid">
          <div className="factor-left">
            <HypothesisPanel onCodeReady={handleCodeReady} />
            <DraftFactorEditor
              draft={draft}
              loading={loading === "create"}
              onChange={setDraft}
              onCreate={createDraftFactor}
            />
          </div>
          <div className="factor-right">
            <FactorLibraryList
              factors={factors}
              selectedKey={selectedKey}
              activation={activation}
              admin={admin}
              onSelect={setSelectedKey}
              onActivationChange={(key, active) => setActivation((current) => ({ ...current, [key]: active }))}
            />
            <EvalResultCard result={currentResult} />
            <div className="factor-actions">
              <Button type="primary" onClick={() => void evaluateSelected()} disabled={!selected} loading={loading === "evaluate"}>
                {loading === "evaluate" ? "评估中" : "评估因子"}
              </Button>
              <Button type="default" onClick={() => void promoteSelected("validated")} disabled={!admin || !selected} loading={loading === "promote-validated"}>
                晋级候选
              </Button>
              <Button type="default" onClick={() => void promoteSelected("production")} disabled={!admin || !selected} loading={loading === "promote-production"}>
                晋级生产
              </Button>
            </div>
            <FactorHealthDashboard items={healthItems} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function DraftFactorEditor({
  draft,
  loading,
  onChange,
  onCreate,
}: {
  draft: { key: string; name: string; hypothesis: string; code: string };
  loading: boolean;
  onChange: (draft: { key: string; name: string; hypothesis: string; code: string }) => void;
  onCreate: () => void;
}) {
  return (
    <section className="factor-draft-editor">
      <div className="factor-section-title">
        <h3>2. 因子代码草稿</h3>
        <span>可以人工调整后再保存到因子库。</span>
      </div>
      <div className="factor-draft-fields">
        <Input value={draft.key} onChange={(event) => onChange({ ...draft, key: event.target.value })} placeholder="factor_key" />
        <Input value={draft.name} onChange={(event) => onChange({ ...draft, name: event.target.value })} placeholder="因子名称" />
      </div>
      <TextArea value={draft.hypothesis} onChange={(event) => onChange({ ...draft, hypothesis: event.target.value })} placeholder="经济学假设" rows={3} />
      <TextArea value={draft.code} onChange={(event) => onChange({ ...draft, code: event.target.value })} placeholder="def compute_factor(bars):" rows={8} />
      <Button type="primary" onClick={onCreate} loading={loading} disabled={!draft.key.trim() || !draft.name.trim() || !draft.code.trim()}>
        {loading ? "保存中" : "保存到因子库"}
      </Button>
    </section>
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
    <section className="factor-library-list">
      <div className="factor-section-title">
        <h3>因子库</h3>
        <span>{factors.length} 个因子</span>
      </div>
      {factors.map((factor) => (
        <article key={factor.factor_key} className={selectedKey === factor.factor_key ? "active" : ""}>
          <Button type="text" onClick={() => onSelect(factor.factor_key)}>
            <strong>{factor.name}</strong>
            <span>{factor.factor_key}</span>
            <small>{statusText(factor.status)} · IC {((factor.eval_result?.ic_mean ?? 0) * 100).toFixed(2)}%</small>
          </Button>
          {admin && factor.status === "production" ? (
            <FactorActivationToggle
              factorKey={factor.factor_key}
              active={Boolean(activation[factor.factor_key])}
              onChange={(active) => onActivationChange(factor.factor_key, active)}
            />
          ) : null}
        </article>
      ))}
    </section>
  );
}

function statusText(status: string): string {
  if (status === "production") return "生产";
  if (status === "validated") return "候选";
  if (status === "rejected") return "已拒绝";
  if (status === "archived") return "归档";
  return "研究";
}

function toMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
