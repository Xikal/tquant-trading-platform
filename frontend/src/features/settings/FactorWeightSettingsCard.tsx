import type { CSSProperties } from "react";
import { InputNumber } from "antd";
import type { FactorWeightsResponse } from "../../types";
import { SettingCard } from "../workspace-shared/WorkspaceComponents";

const FACTOR_WEIGHT_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
};

const FACTOR_WEIGHT_ITEM_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  padding: 8,
  border: "1px solid var(--line)",
  borderRadius: 8,
  background: "#f8fafc",
};

const FACTOR_WEIGHT_NAME_STYLE: CSSProperties = {
  overflow: "hidden",
  color: "var(--text)",
  fontSize: 11,
  fontWeight: 800,
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const FACTOR_WEIGHT_META_STYLE: CSSProperties = {
  overflow: "hidden",
  color: "var(--muted)",
  fontSize: 10,
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const FACTOR_STATUS_STYLE: CSSProperties = {
  ...FACTOR_WEIGHT_META_STYLE,
  display: "inline-flex",
  width: "fit-content",
  maxWidth: "100%",
  padding: "2px 6px",
  borderRadius: 999,
  fontWeight: 900,
};

const FULL_WIDTH_STYLE: CSSProperties = {
  width: "100%",
};

export function FactorWeightSettingsCard({
  factorWeights,
  factorDraft,
  loading,
  saved,
  disabled,
  onSave,
  onDraftChange,
}: {
  factorWeights: FactorWeightsResponse | null;
  factorDraft: Record<string, string>;
  loading: boolean;
  saved: boolean;
  disabled: boolean;
  onSave: () => void | Promise<void>;
  onDraftChange: (draft: Record<string, string>) => void;
}) {
  return (
    <SettingCard className="factor-weight-card" title="因子权重" button="保存因子权重" onSave={onSave} loading={loading} saved={saved} disabled={disabled}>
      {factorWeights ? (
        <div style={FACTOR_WEIGHT_GRID_STYLE}>
          {factorWeights.factors.map((factor) => (
            <label key={factor.name} style={FACTOR_WEIGHT_ITEM_STYLE}>
              <span style={FACTOR_WEIGHT_NAME_STYLE}>{factor.name}</span>
              <InputNumber
                stringMode
                style={FULL_WIDTH_STYLE}
                value={factorDraft[factor.name] ?? String(factorWeights.weights[factor.name] ?? factor.weight)}
                onChange={(value) => onDraftChange({ ...factorDraft, [factor.name]: value == null ? "" : String(value) })}
              />
              <small style={FACTOR_WEIGHT_META_STYLE}>{factor.data_dependencies.join(" / ") || "基础因子"}</small>
              <small style={FACTOR_STATUS_STYLE}>{factor.status_text || factor.status}</small>
            </label>
          ))}
        </div>
      ) : <p className="hint">填写管理令牌后点击刷新配置，即可加载因子权重。未加载时不会影响策略运行。</p>}
    </SettingCard>
  );
}
