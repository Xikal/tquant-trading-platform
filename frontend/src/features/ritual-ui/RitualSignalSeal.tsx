import { ritualSealCopy } from "./ritualCopy";
import { useRitualPreference } from "./ritualState";

interface RitualSignalSealProps {
  enabled?: boolean;
  signalState?: string;
  riskLevel?: string;
  compact?: boolean;
}

export function RitualSignalSeal({ enabled, signalState, riskLevel, compact = false }: RitualSignalSealProps) {
  const preference = useRitualPreference();
  const visible = enabled ?? preference.enabled;
  if (!visible) return null;
  const copy = ritualSealCopy(signalState, riskLevel);
  return (
    <span
      className={`ritual-signal-seal tone-${copy.tone}${compact ? " is-compact" : ""}`}
      title={copy.detail}
      data-testid="ritual-signal-seal"
    >
      {copy.label}
    </span>
  );
}
