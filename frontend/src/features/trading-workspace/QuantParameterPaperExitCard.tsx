import { useCallback, useEffect, useMemo, useState } from "react";

import { quantParametersApi, type QuantParameterSet } from "../../api/quantParameters";
import { NumberField } from "../../components/shared/FormFields";
import { SettingCard } from "./WorkspaceComponents";
import { getNested, setNested, structuredCloneSafe, type QuantFieldSpec } from "./quantParameterCardUtils";

const PAPER_EXIT_FIELDS: QuantFieldSpec[] = [
  { path: "paper.dynamic_exit.hard_stop_loss_pct", label: "硬止损线", min: -20, max: 0, step: "0.1", suffix: "%" },
  { path: "paper.dynamic_exit.first_take_profit_pct", label: "第一止盈线", min: 0, max: 20, step: "0.1", suffix: "%" },
  { path: "paper.dynamic_exit.first_take_profit_sell_ratio", label: "第一止盈比例", min: 0, max: 1, step: "0.05", suffix: "比例" },
  { path: "paper.dynamic_exit.protect_profit_trigger_pct", label: "利润保护触发", min: 0, max: 20, step: "0.1", suffix: "%" },
  { path: "paper.dynamic_exit.protect_profit_sell_ratio", label: "保护减仓比例", min: 0, max: 1, step: "0.05", suffix: "比例" },
  { path: "paper.dynamic_exit.take_profit_pct", label: "常规止盈线", min: 0, max: 30, step: "0.1", suffix: "%" },
  { path: "paper.dynamic_exit.take_profit_sell_ratio", label: "常规止盈比例", min: 0, max: 1, step: "0.05", suffix: "比例" },
  { path: "paper.dynamic_exit.strong_take_profit_pct", label: "强止盈线", min: 0, max: 50, step: "0.1", suffix: "%" },
  { path: "paper.dynamic_exit.strong_take_profit_sell_ratio", label: "强止盈比例", min: 0, max: 1, step: "0.05", suffix: "比例" },
  { path: "paper.dynamic_exit.wash_buffer_profit_pct", label: "洗盘容忍收益", min: 0, max: 10, step: "0.1", suffix: "%" },
  { path: "paper.dynamic_exit.wash_pullback_loss_floor_pct", label: "洗盘最大浮亏", min: -10, max: 0, step: "0.1", suffix: "%" },
  { path: "paper.dynamic_exit.wash_volume_ratio_max", label: "洗盘缩量上限", min: 0, max: 2, step: "0.05", suffix: "倍" },
  { path: "paper.dynamic_exit.no_volume_take_profit_pct", label: "无量冲高止盈线", min: 0, max: 20, step: "0.1", suffix: "%" },
  { path: "paper.dynamic_exit.no_volume_release_ratio", label: "无量判定阈值", min: 0, max: 2, step: "0.05", suffix: "倍" },
  { path: "paper.dynamic_exit.no_volume_take_profit_sell_ratio", label: "无量止盈比例", min: 0, max: 1, step: "0.05", suffix: "比例" },
  { path: "paper.dynamic_exit.high_pullback_ratio", label: "冲高回落保护", min: 0, max: 1, step: "0.05", suffix: "比例" },
  { path: "paper.dynamic_exit.min_net_profit_pct", label: "最低净收益门槛", min: 0, max: 5, step: "0.1", suffix: "%" },
  { path: "paper.dynamic_exit.smart_t_add_cash_pct", label: "洗盘加仓资金", min: 0, max: 0.3, step: "0.01", suffix: "比例" },
  { path: "paper.dynamic_exit.smart_t_add_max_position_pct", label: "加仓后单票上限", min: 0.05, max: 0.5, step: "0.01", suffix: "比例" },
  { path: "paper.dynamic_exit.smart_t_expected_rebound_pct", label: "做T预期反抽", min: 0, max: 8, step: "0.1", suffix: "%" },
  { path: "paper.dynamic_exit.weak_hold_exit_days", label: "未转强退出天数", min: 1, max: 20, step: "1", suffix: "天" },
  { path: "paper.dynamic_exit.time_exit_min_return_pct", label: "时间退出最低收益", min: 0, max: 20, step: "0.1", suffix: "%" },
];

export function QuantParameterPaperExitCard({ adminTokenError }: { adminTokenError: string }) {
  const [current, setCurrent] = useState<QuantParameterSet | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    const response = await quantParametersApi.current("low_buy");
    setCurrent(response);
    setDraft(Object.fromEntries(PAPER_EXIT_FIELDS.map((field) => [field.path, String(getNested(response.params, field.path) ?? "")])));
  }, []);

  useEffect(() => {
    void load().catch((exc: unknown) => setError(exc instanceof Error ? exc.message : "动态退出参数加载失败"));
  }, [load]);

  const fieldError = useMemo(() => {
    if (!current) return "";
    for (const field of PAPER_EXIT_FIELDS) {
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
      for (const field of PAPER_EXIT_FIELDS) {
        setNested(params, field.path, Number(draft[field.path]));
      }
      await quantParametersApi.create({
        version: `paper-dynamic-exit-${Date.now()}`,
        name: "模拟盘动态止盈止损参数",
        scope: "low_buy",
        params,
        description: "系统配置页调整模拟盘自动退出、利润保护和时间退出门槛。",
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
    <SettingCard title="模拟盘动态止盈止损" button="保存动态退出参数" onSave={() => void save()} loading={loading} saved={saved} disabled={Boolean(adminTokenError || fieldError || !current)}>
      <p className="muted">控制自动交易持仓的硬止损、冲高无量分批止盈、利润保护和洗盘容忍，避免利润大幅回吐，同时防止固定止损卖在缩量洗盘低点。</p>
      {PAPER_EXIT_FIELDS.map((field) => (
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
