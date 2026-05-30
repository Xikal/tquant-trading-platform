import { useEffect } from "react";
import { create } from "zustand";
import type { RitualIntensity, RitualPreference } from "./ritualTypes";

export const RITUAL_ENABLED_KEY = "tquant:ritual:enabled";
export const RITUAL_INTENSITY_KEY = "tquant:ritual:intensity";
export const RITUAL_CHANGE_EVENT = "tquant:ritual:changed";

const DEFAULT_PREFERENCE: RitualPreference = {
  enabled: true,
  intensity: "subtle",
};

interface RitualUiState extends RitualPreference {
  blessingOpen: boolean;
  drawCount: number;
  setEnabled: (enabled: boolean) => void;
  setIntensity: (intensity: RitualIntensity) => void;
  syncFromStorage: () => void;
  openBlessing: () => void;
  closeBlessing: () => void;
  drawLucky: () => void;
}

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readRitualPreference(): RitualPreference {
  const local = storage();
  if (!local) return DEFAULT_PREFERENCE;
  const enabledRaw = local.getItem(RITUAL_ENABLED_KEY);
  const intensityRaw = local.getItem(RITUAL_INTENSITY_KEY);
  return {
    enabled: enabledRaw == null ? DEFAULT_PREFERENCE.enabled : enabledRaw === "true",
    intensity: intensityRaw === "standard" ? "standard" : "subtle",
  };
}

export function writeRitualPreference(next: Partial<RitualPreference>): RitualPreference {
  const local = storage();
  const preference = { ...readRitualPreference(), ...next };
  if (local) {
    local.setItem(RITUAL_ENABLED_KEY, String(preference.enabled));
    local.setItem(RITUAL_INTENSITY_KEY, preference.intensity);
    window.dispatchEvent(new CustomEvent(RITUAL_CHANGE_EVENT, { detail: preference }));
  }
  return preference;
}

export const useRitualUiStore = create<RitualUiState>((set) => ({
  ...readRitualPreference(),
  blessingOpen: false,
  drawCount: 0,
  setEnabled: (enabled) => {
    const preference = writeRitualPreference({ enabled });
    set(preference);
  },
  setIntensity: (intensity) => {
    const preference = writeRitualPreference({ intensity });
    set(preference);
  },
  syncFromStorage: () => set(readRitualPreference()),
  openBlessing: () => set({ blessingOpen: true }),
  closeBlessing: () => set({ blessingOpen: false }),
  drawLucky: () => set((state) => ({ drawCount: state.drawCount + 1 })),
}));

export function dailyBlessingKey(dayKey: string, userId?: number | string): string {
  return `tquant:ritual:daily-blessing:${userId ?? "guest"}:${dayKey}`;
}

export function isDailyBlessingSeen(dayKey: string, userId?: number | string): boolean {
  return storage()?.getItem(dailyBlessingKey(dayKey, userId)) === "seen";
}

export function markDailyBlessingSeen(dayKey: string, userId?: number | string): void {
  storage()?.setItem(dailyBlessingKey(dayKey, userId), "seen");
}

export function useRitualPreference() {
  const enabled = useRitualUiStore((state) => state.enabled);
  const intensity = useRitualUiStore((state) => state.intensity);
  const setEnabled = useRitualUiStore((state) => state.setEnabled);
  const setIntensity = useRitualUiStore((state) => state.setIntensity);
  const syncFromStorage = useRitualUiStore((state) => state.syncFromStorage);

  useEffect(() => {
    function syncPreference() {
      syncFromStorage();
    }
    window.addEventListener("storage", syncPreference);
    window.addEventListener(RITUAL_CHANGE_EVENT, syncPreference);
    return () => {
      window.removeEventListener("storage", syncPreference);
      window.removeEventListener(RITUAL_CHANGE_EVENT, syncPreference);
    };
  }, [syncFromStorage]);

  return {
    enabled,
    intensity,
    setEnabled,
    setIntensity,
  };
}
