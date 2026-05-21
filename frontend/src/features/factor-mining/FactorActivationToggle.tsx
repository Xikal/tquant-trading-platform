import { useState } from "react";
import { Switch } from "antd";
import { factorMiningApi } from "../../api/factorMining";

export function FactorActivationToggle({
  factorKey,
  active,
  onChange,
}: {
  factorKey: string;
  active: boolean;
  onChange: (active: boolean) => void;
}) {
  const [saving, setSaving] = useState(false);

  async function toggle() {
    setSaving(true);
    try {
      const result = await factorMiningApi.updateActivation(factorKey, !active);
      onChange(result.active);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Switch
      className="factor-activation"
      checked={active}
      loading={saving}
      checkedChildren="已接入评分"
      unCheckedChildren="未接入评分"
      onChange={() => void toggle()}
    />
  );
}
