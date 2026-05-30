import { Tag } from "antd";
import { ritualCalendarHint, ritualFortuneText } from "./ritualCopy";
import type { RitualMarketTone } from "./ritualTypes";
import { useRitualPreference } from "./ritualState";

interface RitualFortuneStripProps {
  enabled?: boolean;
  marketTone?: RitualMarketTone;
  compact?: boolean;
  showCalendarHint?: boolean;
}

export function RitualFortuneStrip({
  enabled,
  marketTone = "unknown",
  compact = false,
  showCalendarHint = false,
}: RitualFortuneStripProps) {
  const preference = useRitualPreference();
  const visible = enabled ?? preference.enabled;
  if (!visible) return null;
  const hint = ritualCalendarHint();
  return (
    <div className={`ritual-fortune-strip tone-${marketTone}${compact ? " is-compact" : ""}`} data-testid="ritual-fortune-strip">
      <span className="ritual-fortune-mark" aria-hidden="true">红</span>
      <span>今日红运：{ritualFortuneText(marketTone)}</span>
      {showCalendarHint ? <Tag color="gold">宜 {hint.good}；忌 {hint.avoid}</Tag> : null}
    </div>
  );
}
