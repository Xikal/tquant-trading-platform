import { useCallback, useEffect, useMemo, useState } from "react";

import { quantParametersApi, type QuantParameterSet } from "../../api/quantParameters";
import { NumberField } from "../../components/shared/FormFields";
import { SettingCard } from "./WorkspaceComponents";

type FieldSpec = {
  path: string;
  label: string;
  min: number;
  max: number;
  step?: string;
};

const FIELD_SPECS: FieldSpec[] = [
  { path: "ml.training.cv_folds", label: "交叉验证折数", min: 2, max: 20 },
  { path: "ml.training.min_train_samples", label: "最低训练样本", min: 20, max: 1000000 },
  { path: "ml.training.xgb_n_estimators", label: "XGBoost 树数量", min: 10, max: 2000 },
  { path: "ml.training.xgb_max_depth", label: "XGBoost 深度", min: 1, max: 20 },
  { path: "ml.training.xgb_learning_rate", label: "XGBoost 学习率", min: 0.001, max: 1, step: "0.001" },
  { path: "ml.training.lgb_n_estimators", label: "LightGBM 树数量", min: 10, max: 2000 },
  { path: "ml.training.lgb_max_depth", label: "LightGBM 深度", min: 1, max: 20 },
  { path: "ml.training.lgb_learning_rate", label: "LightGBM 学习率", min: 0.001, max: 1, step: "0.001" },
];

export function QuantParameterMlCard({ adminTokenError }: { adminTokenError: string }) {
  const [current, setCurrent] = useState<QuantParameterSet | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    const response = await quantParametersApi.current("low_buy");
    setCurrent(response);
    setDraft(Object.fromEntries(FIELD_SPECS.map((field) => [field.path, String(getNested(response.params, field.path) ?? "")])));
  }, []);

  useEffect(() => {
    void load().catch((exc: unknown) => setError(exc instanceof Error ? exc.message : "参数加载失败"));
  }, [load]);

  const fieldError = useMemo(() => {
    if (!current) return "";
    for (const field of FIELD_SPECS) {
      const value = Number(draft[field.path]);
      if (!Number.isFinite(value) || value < field.min || value > field.max) {
        return `${field.label}必须在 ${field.min} - ${field.max} 之间`;
      }
    }
    return "";
  }, [current, draft]);

  const save = async () => {
    if (!current || adminTokenError || fieldError) return;
    setLoading(true);
    setSaved(false);
    setError("");
    try {
      const params = structuredCloneSafe(current.params);
      for (const field of FIELD_SPECS) {
        setNested(params, field.path, Number(draft[field.path]));
      }
      await quantParametersApi.create({
        version: `ml-training-${Date.now()}`,
        name: "ML 训练参数调整",
        scope: "low_buy",
        params,
        description: "系统配置页调整 ML 训练与交叉验证参数。",
        activate: true,
      });
      setSaved(true);
      await load();
    } catch (exc: unknown) {
      setError(exc instanceof Error ? exc.message : "保存失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SettingCard title="ML 训练参数" button="保存 ML 参数" onSave={() => void save()} loading={loading} saved={saved} disabled={Boolean(adminTokenError || fieldError || !current)}>
      <p className="muted">控制模型训练样本量、K-fold 验证和树模型参数。修改后新训练任务生效，不会改变历史模型。</p>
      {FIELD_SPECS.map((field) => (
        <NumberField
          key={field.path}
          label={field.label}
          min={field.min}
          max={field.max}
          step={field.step ?? "1"}
          value={draft[field.path] ?? ""}
          onChange={(event) => setDraft((values) => ({ ...values, [field.path]: event.target.value }))}
        />
      ))}
      {adminTokenError || fieldError || error ? <span className="tq-field__error">{adminTokenError || fieldError || error}</span> : null}
    </SettingCard>
  );
}

function getNested(source: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((value, key) => (isRecord(value) ? value[key] : undefined), source);
}

function setNested(source: Record<string, unknown>, path: string, value: number) {
  const parts = path.split(".");
  let cursor: Record<string, unknown> = source;
  for (const key of parts.slice(0, -1)) {
    if (!isRecord(cursor[key])) cursor[key] = {};
    cursor = cursor[key] as Record<string, unknown>;
  }
  cursor[parts[parts.length - 1]] = value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function structuredCloneSafe<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
