import { Segmented, Switch } from "antd";
import { SettingCard } from "../workspace-shared/WorkspaceComponents";
import { useRitualPreference } from "./ritualState";
import type { RitualIntensity } from "./ritualTypes";

export function RitualSettingsCard() {
  const ritual = useRitualPreference();
  return (
    <SettingCard
      title="红运仪式感"
      button="已保存本机偏好"
      loading={false}
      saved
      onSave={() => undefined}
    >
      <div className="ritual-settings-card">
        <label>
          <span>红运视觉层</span>
          <Switch checked={ritual.enabled} onChange={ritual.setEnabled} />
        </label>
        <label>
          <span>强度</span>
          <Segmented<RitualIntensity>
            size="small"
            value={ritual.intensity}
            options={[
              { label: "克制", value: "subtle" },
              { label: "标准", value: "standard" },
            ]}
            onChange={ritual.setIntensity}
          />
        </label>
        <p className="hint">仅控制视觉寓意，不参与策略计算、排序、回测、交易和风控。</p>
      </div>
    </SettingCard>
  );
}
