import { ritualCloseBagText } from "./ritualCopy";
import { useRitualPreference } from "./ritualState";

interface RitualCloseBagProps {
  enabled?: boolean;
  visible?: boolean;
  compact?: boolean;
}

export function RitualCloseBag({ enabled, visible = true, compact = false }: RitualCloseBagProps) {
  const preference = useRitualPreference();
  const shouldRender = visible && (enabled ?? preference.enabled);
  if (!shouldRender) return null;
  return (
    <div className={`ritual-close-bag${compact ? " is-compact" : ""}`} data-testid="ritual-close-bag">
      <span className="ritual-close-bag-label">今日收盘福袋</span>
      <strong>{ritualCloseBagText()}</strong>
      <span>仅作视觉寓意，不替代正式复盘。</span>
    </div>
  );
}
