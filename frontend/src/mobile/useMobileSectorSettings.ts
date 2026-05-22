import { appApi } from "../api/appClient";
import { useMobileUiStore } from "../stores/mobileUiStore";
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
  const open = useMobileUiStore((state) => state.sectorSettingsOpen);
  const excludedSectors = useMobileUiStore((state) => state.excludedSectors);
  const availableSectors = useMobileUiStore((state) => state.availableSectors);
  const saving = useMobileUiStore((state) => state.sectorSettingsSaving);
  const setOpen = useMobileUiStore((state) => state.setSectorSettingsOpen);
  const setExcludedSectors = useMobileUiStore((state) => state.setExcludedSectors);
  const setAvailableSectors = useMobileUiStore((state) => state.setAvailableSectors);
  const setSaving = useMobileUiStore((state) => state.setSectorSettingsSaving);

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
