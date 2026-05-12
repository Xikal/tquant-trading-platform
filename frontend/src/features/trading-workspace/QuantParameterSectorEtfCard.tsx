import { useCallback, useEffect, useMemo, useState } from "react";

import { quantParametersApi, type QuantParameterSet } from "../../api/quantParameters";
import { NumberField } from "../../components/shared/FormFields";
import { SettingCard } from "./WorkspaceComponents";
import { getNested, setNested, structuredCloneSafe, type QuantFieldSpec } from "./quantParameterCardUtils";

const ETF_FIELD_SPECS: QuantFieldSpec[] = [
  { path: "market.sector_etf_t0.paper_auto_max_orders", label: "每轮最多委托", min: 0, max: 10 },
  { path: "market.sector_etf_t0.paper_auto_cash_pct", label: "单笔可用资金", min: 0, max: 1, step: "0.01", suffix: "比例" },
  { path: "market.sector_etf_t0.paper_auto_min_confidence", label: "最低置信度", min: 0, max: 100 },
  { path: "market.sector_etf_t0.paper_auto_min_edge_pct", label: "最低预期价差", min: 0, max: 10, step: "0.1", suffix: "%" },
  { path: "market.sector_etf_t0.paper_auto_take_profit_pct", label: "止盈线", min: 0, max: 10, step: "0.1", suffix: "%" },
  { path: "market.sector_etf_t0.paper_auto_stop_loss_pct", label: "止损线", min: -10, max: 0, step: "0.1", suffix: "%" },
];

export function QuantParameterSectorEtfCard({ adminTokenError }: { adminTokenError: string }) {
  const [current, setCurrent] = useState<QuantParameterSet | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    const response = await quantParametersApi.current("low_buy");
    setCurrent(response);
    setEnabled(Boolean(getNested(response.params, "market.sector_etf_t0.paper_auto_enabled") ?? true));
    setDraft(Object.fromEntries(ETF_FIELD_SPECS.map((field) => [field.path, String(getNested(response.params, field.path) ?? "")])));
  }, []);

  useEffect(() => {
    void load().catch((exc: unknown) => setError(exc instanceof Error ? exc.message : "ETF 参数加载失败"));
  }, [load]);

  const fieldError = useMemo(() => {
    if (!current) return "";
    for (const field of ETF_FIELD_SPECS) {
      const value = Number(draft[field.path]);
      if (!Number.isFinite(value) || value < field.min || value > field.max) {
        return `${field.label}必须在 ${field.min} - ${field.max} 之间`;
      }
    }
    return "";
  }, [current, draft]);

  async function save() {
    if (!current || adminTokenError || fieldError) return;
    setLoading(true);
    setSaved(false);
    setError("");
    try {
      const params = structuredCloneSafe(current.params);
      for (const field of ETF_FIELD_SPECS) {
        setNested(params, field.path, Number(draft[field.path]));
      }
      setNested(params, "market.sector_etf_t0.paper_auto_enabled", enabled);
      await quantParametersApi.create({
        version: `sector-etf-t0-${Date.now()}`,
        name: "行业 ETF T+0 自动交易参数",
        scope: "low_buy",
        params,
        description: "系统配置页调整行业 ETF T+0 自动交易门槛。",
        activate: true,
      });
      setSaved(true);
      await load();
    } catch (exc: unknown) {
      setError(exc instanceof Error ? exc.message : "保存失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <SettingCard title="行业 ETF T+0 自动交易" button="保存 ETF 参数" onSave={() => void save()} loading={loading} saved={saved} disabled={Boolean(adminTokenError || fieldError || !current)}>
      <p className="muted">控制模拟盘是否自动执行行业 ETF T+0 机会，以及单轮委托、置信度、价差、止盈止损门槛。</p>
      <label className="tq-field tq-checkbox-field">
        <span className="tq-field__label">自动执行</span>
        <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
        <span>{enabled ? "已启用" : "已关闭"}</span>
      </label>
      {ETF_FIELD_SPECS.map((field) => (
        <NumberField
          key={field.path}
          label={field.label}
          min={field.min}
          max={field.max}
          step={field.step ?? "1"}
          suffix={field.suffix}
          value={draft[field.path] ?? ""}
          onChange={(event) => setDraft((values) => ({ ...values, [field.path]: event.target.value }))}
        />
      ))}
      {adminTokenError || fieldError || error ? <span className="tq-field__error">{adminTokenError || fieldError || error}</span> : null}
    </SettingCard>
  );
}
