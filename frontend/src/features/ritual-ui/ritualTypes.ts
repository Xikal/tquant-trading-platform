export type RitualMarketTone = "strong" | "neutral" | "weak" | "unknown";

export type RitualIntensity = "subtle" | "standard";

export interface RitualPreference {
  enabled: boolean;
  intensity: RitualIntensity;
}

export interface RitualSealCopy {
  label: string;
  detail: string;
  tone: RitualMarketTone | "danger";
}
