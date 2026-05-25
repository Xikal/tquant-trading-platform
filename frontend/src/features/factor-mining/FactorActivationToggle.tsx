import { Switch } from "antd";
import { factorMiningApi } from "../../api/factorMining";
import { useFactorMiningUiStore } from "../../stores/factorMiningUiStore";

export function FactorActivationToggle({
  factorKey,
  active,
  onChange,
}: {
  factorKey: string;
  active: boolean;
  onChange: (active: boolean) => void;
}) {
  const saving = useFactorMiningUiStore((state) => Boolean(state.activationSaving[factorKey]));
  const setSaving = useFactorMiningUiStore((state) => state.setActivationSaving);

  async function toggle() {
    setSaving(factorKey, true);
    try {
      const result = await factorMiningApi.updateActivation(factorKey, !active);
      onChange(result.active);
    } finally {
      setSaving(factorKey, false);
    }
  }

  return (
    <Switch
      style={{ minWidth: 108 }}
      checked={active}
      loading={saving}
      checkedChildren="已接入评分"
      unCheckedChildren="未接入评分"
      onChange={() => void toggle()}
    />
  );
}
