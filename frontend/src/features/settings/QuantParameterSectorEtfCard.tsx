import { useCallback, useEffect, useMemo } from "react";
import type { CSSProperties } from "react";
import { Checkbox } from "antd";

import { quantParametersApi } from "../../api/quantParameters";
import { NumberField } from "../../components/shared/FormFields";
import { SettingCard } from "../workspace-shared/WorkspaceComponents";
import { getNested, setNested, structuredCloneSafe, type QuantFieldSpec } from "./quantParameterCardUtils";
import { useSettingsUiStore } from "../../stores/settingsUiStore";

const ETF_FIELD_SPECS: QuantFieldSpec[] = [
  { path: "market.sector_etf_t0.paper_auto_max_orders", label: "每轮最多委托", min: 0, max: 10 },
  { path: "market.sector_etf_t0.paper_auto_cash_pct", label: "单笔可用资金", min: 0, max: 1, step: "0.01", suffix: "比例" },
  { path: "market.sector_etf_t0.paper_auto_min_confidence", label: "最低置信度", min: 0, max: 100 },
  { path: "market.sector_etf_t0.paper_auto_min_edge_pct", label: "最低预期价差", min: 0, max: 10, step: "0.1", suffix: "%" },
  { path: "market.sector_etf_t0.paper_auto_take_profit_pct", label: "止盈线", min: 0, max: 10, step: "0.1", suffix: "%" },
  { path: "market.sector_etf_t0.paper_auto_stop_loss_pct", label: "止损线", min: -10, max: 0, step: "0.1", suffix: "%" },
];

const INLINE_CHECKBOX_FIELD_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
  minWidth: 0,
};

const INLINE_FIELD_LABEL_STYLE: CSSProperties = {
  color: "#62708a",
  fontSize: 12,
  fontWeight: 700,
};

const INLINE_FIELD_ERROR_STYLE: CSSProperties = {
  color: "#b91c1c",
  fontSize: 12,
};

export function QuantParameterSectorEtfCard({ adminTokenError }: { adminTokenError: string }) {
  const card = useSettingsUiStore((state) => state.quantCards.sectorEtf);
  const setCard = useSettingsUiStore((state) => state.setQuantCard);
  const { current, draft, enabled, loading, saved, error } = card;

  const load = useCallback(async () => {
    setCard("sectorEtf", { error: "" });
    const response = await quantParametersApi.current("low_buy");
    setCard("sectorEtf", {
      current: response,
      enabled: Boolean(getNested(response.params, "market.sector_etf_t0.paper_auto_enabled") ?? true),
      draft: Object.fromEntries(ETF_FIELD_SPECS.map((field) => [field.path, String(getNested(response.params, field.path) ?? "")])),
    });
  }, [setCard]);

  useEffect(() => {
    void load().catch((exc: unknown) => setCard("sectorEtf", { error: exc instanceof Error ? exc.message : "ETF 参数加载失败" }));
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
    setCard("sectorEtf", { loading: true, saved: false, error: "" });
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
      setCard("sectorEtf", { saved: true });
      await load();
    } catch (exc: unknown) {
      setCard("sectorEtf", { error: exc instanceof Error ? exc.message : "保存失败" });
    } finally {
      setCard("sectorEtf", { loading: false });
    }
  }

  return (
    <SettingCard className="sector-etf-params-card" title="行业 ETF T+0 自动交易" button="保存 ETF 参数" onSave={() => void save()} loading={loading} saved={saved} disabled={Boolean(adminTokenError || fieldError || !current)}>
      <p className="muted">控制模拟盘是否自动执行行业 ETF T+0 机会，以及单轮委托、置信度、价差、止盈止损门槛。</p>
      <label style={INLINE_CHECKBOX_FIELD_STYLE}>
        <span style={INLINE_FIELD_LABEL_STYLE}>自动执行</span>
        <Checkbox checked={enabled} onChange={(event) => setCard("sectorEtf", { enabled: event.target.checked })} />
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
          onChange={(event) => setCard("sectorEtf", { draft: { ...draft, [field.path]: event.target.value } })}
        />
      ))}
      {adminTokenError || fieldError || error ? <span style={INLINE_FIELD_ERROR_STYLE}>{adminTokenError || fieldError || error}</span> : null}
    </SettingCard>
  );
}
