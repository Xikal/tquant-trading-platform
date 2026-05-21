import { useState } from "react";
import { appApi } from "../api/appClient";
import type { MobileTab } from "./mobileTypes";

export function useMobileSectorSettings({
  activeTab,
  refreshActiveTab,
  loadMobilePlaybook,
  strategyFilter,
}: {
  activeTab: MobileTab;
  refreshActiveTab: () => Promise<unknown> | unknown;
  loadMobilePlaybook: (strategy: string, force?: boolean) => Promise<unknown> | unknown;
  strategyFilter: string;
}) {
  const [open, setOpen] = useState(false);
  const [excludedSectors, setExcludedSectors] = useState<string[]>([]);
  const [availableSectors, setAvailableSectors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  async function openSectorSettings() {
    setOpen(true);
    try {
      const payload = await appApi.getSectorExclusions();
      setExcludedSectors(payload.excluded_sectors);
      setAvailableSectors(payload.available_sectors);
    } catch {
      setAvailableSectors([]);
    }
  }

  async function saveSectorSettings(nextExcluded: string[]) {
    try {
      setSaving(true);
      const payload = await appApi.updateSectorExclusions(nextExcluded);
      setExcludedSectors(payload.excluded_sectors);
      setAvailableSectors(payload.available_sectors);
      await refreshActiveTab();
      if (activeTab === "low_buy") {
        await loadMobilePlaybook(strategyFilter, true);
      }
      return true;
    } finally {
      setSaving(false);
    }
  }

  return {
    availableSectors,
    closeSectorSettings: () => setOpen(false),
    excludedSectors,
    open,
    openSectorSettings,
    saveSectorSettings,
    saving,
  };
}
